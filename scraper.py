import http.cookiejar
import html
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request


TITLE = "MegaSource Anime"
VERSION = "4.0.0"
DESCRIPTION = "WordPress DooPlayer Anime Provider"


# ============================================================
# CONFIG
# ============================================================

# ضع دومين موقعك هنا فقط.
BASE_URL = "https://nxxhentai.net/"

CINEMETA_URL = "https://v3-cinemeta.strem.io"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="[MegaSource] %(message)s"
)

logger = logging.getLogger("MegaSource")


# ============================================================
# HTTP SESSION
# ============================================================

_cookiejar = http.cookiejar.CookieJar()

_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(_cookiejar)
)


def _request(
    url,
    method="GET",
    data=None,
    referer=None,
    origin=None,
    ajax=False,
    timeout=20
):

    headers = {
        "User-Agent": USER_AGENT,

        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/json,text/plain,*/*"
        ),

        "Accept-Language":
            "en-US,en;q=0.9",

        "Connection":
            "keep-alive"
    }

    if referer:
        headers["Referer"] = referer

    if origin:
        headers["Origin"] = origin

    if ajax:
        headers["X-Requested-With"] = "XMLHttpRequest"

    body = None

    if method.upper() == "POST":

        if isinstance(data, dict):

            body = urllib.parse.urlencode(
                data
            ).encode("utf-8")

            headers["Content-Type"] = (
                "application/x-www-form-urlencoded; "
                "charset=UTF-8"
            )

        elif data is not None:

            body = data

    try:

        request = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method=method.upper()
        )

        with _opener.open(
            request,
            timeout=timeout
        ) as response:

            text = response.read().decode(
                "utf-8",
                errors="replace"
            )

            return response.status, text

    except urllib.error.HTTPError as exc:

        try:
            text = exc.read().decode(
                "utf-8",
                errors="replace"
            )
        except Exception:
            text = ""

        logger.info(
            "HTTP %s: %s",
            exc.code,
            url
        )

        return exc.code, text

    except Exception as exc:

        logger.info(
            "Request error: %s",
            exc
        )

        return 0, ""


# ============================================================
# HELPERS
# ============================================================

def _clean(value):

    if not value:
        return ""

    value = html.unescape(
        str(value)
    )

    value = value.replace(
        "\\/",
        "/"
    )

    value = value.replace(
        "\\u0026",
        "&"
    )

    value = value.replace(
        "\\u003d",
        "="
    )

    value = value.replace(
        "\\u003f",
        "?"
    )

    return re.sub(
        r"\s+",
        " ",
        value
    ).strip()


def _absolute(url, base):

    url = _clean(url)

    if not url:
        return ""

    return urllib.parse.urljoin(
        base,
        url
    )


def _origin(url):

    try:

        parsed = urllib.parse.urlparse(
            url
        )

        if not parsed.scheme or not parsed.netloc:
            return ""

        return (
            parsed.scheme
            + "://"
            + parsed.netloc
        )

    except Exception:

        return ""


def _normalize(value):

    value = _clean(
        value
    ).lower()

    value = value.replace(
        "-",
        " "
    )

    value = value.replace(
        "_",
        " "
    )

    value = re.sub(
        r"[^\w\s\u0600-\u06ff]",
        " ",
        value,
        flags=re.UNICODE
    )

    return re.sub(
        r"\s+",
        " ",
        value
    ).strip()


def _parse_media_id(media_id):

    media_id = _clean(
        media_id
    )

    parts = media_id.split(":")

    if len(parts) >= 3:

        return (
            parts[0],
            parts[1],
            parts[2]
        )

    return (
        media_id,
        None,
        None
    )


# ============================================================
# CINEMETA
# ============================================================

def get_anime_name(imdb_id):

    if not imdb_id:
        return None

    url = (
        CINEMETA_URL
        + "/meta/series/"
        + urllib.parse.quote(
            imdb_id,
            safe=""
        )
        + ".json"
    )

    logger.info(
        "Cinemeta: %s",
        url
    )

    status, body = _request(
        url,
        timeout=15
    )

    if status != 200:
        logger.info(
            "Cinemeta failed: %s",
            status
        )
        return None

    try:

        data = json.loads(
            body
        )

    except Exception:

        logger.info(
            "Cinemeta returned invalid JSON"
        )

        return None

    meta = data.get(
        "meta",
        {}
    )

    title = (
        meta.get("name")
        or meta.get("originalName")
        or meta.get("title")
    )

    title = _clean(
        title
    )

    logger.info(
        "Anime title: %s",
        title
    )

    return title or None


# ============================================================
# SITE SEARCH
# ============================================================

def search_anime(title):

    if not title:
        return None

    url = (
        BASE_URL.rstrip("/")
        + "/?"
        + urllib.parse.urlencode(
            {
                "s": title
            }
        )
    )

    logger.info(
        "Search: %s",
        url
    )

    status, body = _request(
        url,
        referer=BASE_URL.rstrip("/") + "/"
    )

    if status != 200:
        logger.info(
            "Search failed: %s",
            status
        )
        return None

    results = []

    links = re.findall(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>'
        r'([\s\S]*?)'
        r'</a>',
        body,
        re.I
    )

    for href, content in links:

        text = re.sub(
            r"<[^>]+>",
            " ",
            content
        )

        text = _clean(
            text
        )

        if not text:
            continue

        full_url = _absolute(
            href,
            BASE_URL
        )

        lower_url = full_url.lower()

        if any(
            marker in lower_url
            for marker in (
                "/anime/",
                "/show/",
                "/tv/",
                "/series/"
            )
        ):

            results.append(
                {
                    "title": text,
                    "url": full_url
                }
            )

    logger.info(
        "Search results: %s",
        len(results)
    )

    if not results:
        return None

    wanted = _normalize(
        title
    )

    # Exact
    for item in results:

        if _normalize(
            item["title"]
        ) == wanted:

            logger.info(
                "Exact match: %s",
                item["url"]
            )

            return item["url"]

    # Partial
    for item in results:

        current = _normalize(
            item["title"]
        )

        if (
            wanted in current
            or current in wanted
        ):

            logger.info(
                "Partial match: %s",
                item["url"]
            )

            return item["url"]

    # Fallback
    logger.info(
        "Fallback result: %s",
        results[0]["url"]
    )

    return results[0]["url"]


# ============================================================
# EPISODE
# ============================================================

def get_episode_url(
    anime_url,
    episode_number
):

    if not anime_url:
        return None

    try:

        target = int(
            episode_number
        )

    except Exception:

        return None

    logger.info(
        "Anime page: %s",
        anime_url
    )

    status, body = _request(
        anime_url,
        referer=BASE_URL.rstrip("/") + "/"
    )

    if status != 200:
        logger.info(
            "Anime page failed: %s",
            status
        )
        return None

    candidates = []

    links = re.findall(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>'
        r'([\s\S]*?)'
        r'</a>',
        body,
        re.I
    )

    for href, content in links:

        text = re.sub(
            r"<[^>]+>",
            " ",
            content
        )

        text = _clean(
            text
        )

        full_url = _absolute(
            href,
            anime_url
        )

        # الحلقة من النص
        match = re.search(
            r"(?:episode|ep|الحلقة)"
            r"\s*[-_. ]*0*(\d+)",
            text,
            re.I
        )

        number = None

        if match:

            try:
                number = int(
                    match.group(1)
                )
            except Exception:
                number = None

        # الحلقة من الرابط
        if number is None:

            match = re.search(
                r"(?:episode|ep|الحلقة)"
                r"[-_/ ]*0*(\d+)",
                full_url,
                re.I
            )

            if match:

                try:
                    number = int(
                        match.group(1)
                    )
                except Exception:
                    number = None

        if number is None:

            match = re.search(
                r"[-_/](\d{1,3})(?:[-_/]|$)",
                full_url
            )

            if match:

                try:
                    number = int(
                        match.group(1)
                    )
                except Exception:
                    number = None

        if number == target:

            candidates.append(
                full_url
            )

    if candidates:

        logger.info(
            "Episode found: %s",
            candidates[0]
        )

        return candidates[0]

    logger.info(
        "Episode %s not found",
        target
    )

    return None


# ============================================================
# DOOPLAYER EXTRACTION
# ============================================================

def extract_dooplayer_data(
    episode_html
):

    players = []

    # Standard DooPlayer
    pattern = re.compile(
        r'<li\b'
        r'[^>]*data-post=["\']([^"\']+)["\']'
        r'[^>]*data-nume=["\']([^"\']+)["\']'
        r'[^>]*>'
        r'([\s\S]*?)'
        r'</li>',
        re.I
    )

    for match in pattern.finditer(
        episode_html
    ):

        post_id = _clean(
            match.group(1)
        )

        nume = _clean(
            match.group(2)
        )

        block = match.group(3)

        title = ""

        title_match = re.search(
            r'class=["\'][^"\']*\btitle\b[^"\']*["\']'
            r'[^>]*>'
            r'([\s\S]*?)'
            r'</',
            block,
            re.I
        )

        if title_match:

            title = re.sub(
                r"<[^>]+>",
                " ",
                title_match.group(1)
            )

            title = _clean(
                title
            )

        players.append(
            {
                "post_id": post_id,
                "nume": nume,
                "title": title
            }
        )

    # Some themes use div/button/a instead of li
    if not players:

        generic_pattern = re.compile(
            r'(?:data-post=["\']([^"\']+)["\'])'
            r'[^>]*'
            r'(?:data-nume=["\']([^"\']+)["\'])'
            r'[^>]*'
            r'(?:data-server=["\']([^"\']*)["\'])?',
            re.I
        )

        for match in generic_pattern.finditer(
            episode_html
        ):

            players.append(
                {
                    "post_id": _clean(
                        match.group(1)
                    ),
                    "nume": _clean(
                        match.group(2)
                    ),
                    "title": _clean(
                        match.group(3)
                    )
                }
            )

    logger.info(
        "DooPlayer players: %s",
        players
    )

    return players


def get_episode_players(
    episode_url
):

    status, body = _request(
        episode_url,
        referer=BASE_URL.rstrip("/") + "/"
    )

    if status != 200:

        logger.info(
            "Episode request failed: %s",
            status
        )

        return []

    return extract_dooplayer_data(
        body
    )


# ============================================================
# PLAYER SELECTION
# ============================================================

PLAYER_PRIORITY = [
    "streamhg",
    "hgcloud",
    "hg cloud",
    "nxxplayer",
    "nxxhosting",
    "fastserver",
    "doodstream"
]


def select_players(players):

    def score(player):

        title = _normalize(
            player.get(
                "title",
                ""
            )
        )

        for index, target in enumerate(
            PLAYER_PRIORITY
        ):

            if _normalize(target) in title:

                return index

        return 999

    ordered = sorted(
        players,
        key=score
    )

    logger.info(
        "Player order: %s",
        ordered
    )

    return ordered


# ============================================================
# DOOPLAYER API
# ============================================================

def get_player_embed(
    post_id,
    nume,
    referer
):

    api_url = (
        BASE_URL.rstrip("/")
        + "/wp-json/dooplayer/v2/"
        + urllib.parse.quote(
            str(post_id),
            safe=""
        )
        + "/tv/"
        + urllib.parse.quote(
            str(nume),
            safe=""
        )
    )

    logger.info(
        "DooPlayer API: %s",
        api_url
    )

    status, body = _request(
        api_url,
        referer=referer,
        origin=BASE_URL.rstrip("/"),
        ajax=True
    )

    if status != 200:

        logger.info(
            "DooPlayer API failed: %s",
            status
        )

        return None

    try:

        data = json.loads(
            body
        )

    except Exception:

        logger.info(
            "DooPlayer returned invalid JSON"
        )

        return None

    if isinstance(data, dict):

        embed = (
            data.get("embed_url")
            or data.get("embed")
            or data.get("url")
        )

        if embed:

            embed = _clean(
                embed
            )

            logger.info(
                "Embed: %s",
                embed
            )

            return embed

    return None


# ============================================================
# MEDIA EXTRACTION
# ============================================================

def _extract_urls_from_text(
    text,
    base_url
):

    text = html.unescape(
        text
    )

    text = text.replace(
        "\\/",
        "/"
    )

    text = text.replace(
        "\\u0026",
        "&"
    )

    found = []

    # Direct m3u8
    patterns = [

        r'https?://[^"\'<>\s]+?\.m3u8(?:\?[^"\'<>\s]*)?',

        r'["\'](?:src|file|source|url)["\']'
        r'\s*:\s*["\']([^"\']+\.m3u8[^"\']*)',

        r'(?:src|file|source|url)'
        r'\s*=\s*["\']([^"\']+\.m3u8[^"\']*)',

        r'<source\b[^>]*src=["\']'
        r'([^"\']+)["\']'
        r'[^>]*type=["\']application/vnd\.apple\.mpegurl["\']',

        r'<source\b[^>]*src=["\']'
        r'([^"\']+\.m3u8[^"\']*)["\']',

        r'https?:\\/\\/[^"\'<>\s]+?'
        r'\\.m3u8(?:\?[^"\'<>\s]*)?'
    ]

    for pattern in patterns:

        for match in re.finditer(
            pattern,
            text,
            re.I
        ):

            value = (
                match.group(1)
                if match.groups()
                else match.group(0)
            )

            value = _clean(
                value
            )

            if not value:
                continue

            value = _absolute(
                value,
                base_url
            )

            if value and value not in found:

                found.append(
                    value
                )

    return found


def _extract_mp4_urls(
    text,
    base_url
):

    text = html.unescape(
        text
    )

    text = text.replace(
        "\\/",
        "/"
    )

    patterns = [

        r'https?://[^"\'<>\s]+?\.mp4(?:\?[^"\'<>\s]*)?',

        r'["\'](?:src|file|source|url)["\']'
        r'\s*:\s*["\']([^"\']+\.mp4[^"\']*)',

        r'(?:src|file|source|url)'
        r'\s*=\s*["\']([^"\']+\.mp4[^"\']*)',

        r'<source\b[^>]*src=["\']'
        r'([^"\']+\.mp4[^"\']*)'
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.I
        )

        if match:

            value = (
                match.group(1)
                if match.groups()
                else match.group(0)
            )

            value = _clean(
                value
            )

            if value:

                return _absolute(
                    value,
                    base_url
                )

    return None


# ============================================================
# PLAYER HTML
# ============================================================

def extract_media_url(
    player_url,
    referer
):

    if not player_url:
        return None

    logger.info(
        "Opening player: %s",
        player_url
    )

    player_origin = _origin(
        player_url
    )

    status, body = _request(
        player_url,
        referer=referer,
        origin=player_origin,
        ajax=False,
        timeout=25
    )

    if status != 200:

        logger.info(
            "Player failed: %s",
            status
        )

        return None

    # --------------------------------------------------------
    # 1. Direct HLS in HTML
    # --------------------------------------------------------

    m3u8_urls = _extract_urls_from_text(
        body,
        player_url
    )

    if m3u8_urls:

        logger.info(
            "M3U8 found: %s",
            m3u8_urls[0]
        )

        return m3u8_urls[0]

    # --------------------------------------------------------
    # 2. MP4 fallback
    # --------------------------------------------------------

    mp4 = _extract_mp4_urls(
        body,
        player_url
    )

    if mp4:

        logger.info(
            "MP4 found: %s",
            mp4
        )

        return mp4

    # --------------------------------------------------------
    # 3. Search escaped JSON/HTML again
    # --------------------------------------------------------

    decoded = html.unescape(
        body
    )

    decoded = decoded.replace(
        "\\/",
        "/"
    )

    decoded = decoded.replace(
        "\\u0026",
        "&"
    )

    m3u8_urls = _extract_urls_from_text(
        decoded,
        player_url
    )

    if m3u8_urls:

        logger.info(
            "M3U8 found after decoding: %s",
            m3u8_urls[0]
        )

        return m3u8_urls[0]

    # -----------------------------------------