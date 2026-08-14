import http.cookiejar
import json
import logging
import html
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

BASE_URL = "https://nxxhentai.net/"
CINEMETA_URL = "https://v3-cinemeta.strem.io"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)


# ============================================================
# HTTP
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
        "Accept-Language": "en-US,en;q=0.9",
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
                "application/x-www-form-urlencoded"
            )

        elif data is not None:

            body = data

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method.upper()
    )

    try:

        with _opener.open(
            request,
            timeout=timeout
        ) as response:

            return (
                response.status,
                response.read().decode(
                    "utf-8",
                    errors="replace"
                )
            )

    except urllib.error.HTTPError as exc:

        try:

            body = exc.read().decode(
                "utf-8",
                errors="replace"
            )

        except Exception:

            body = ""

        return (
            exc.code,
            body
        )

    except Exception as exc:

        logger.info(
            "Request failed: %s : %s",
            url,
            exc
        )

        return (
            0,
            ""
        )


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
        "\\u003A",
        ":"
    )

    value = value.replace(
        "\\u002F",
        "/"
    )

    value = value.replace(
        "&amp;",
        "&"
    )

    return re.sub(
        r"\s+",
        " ",
        value
    ).strip()


def _absolute(
    url,
    base
):

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


def _parse_media_id(
    media_id
):

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

def get_anime_name(
    imdb_id
):

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
        return None

    try:

        data = json.loads(
            body
        )

    except Exception:

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

    return title


# ============================================================
# SITE SEARCH
# ============================================================

def search_anime(
    title
):

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
        referer=BASE_URL + "/"
    )

    if status != 200:
        return None

    results = []

    links = re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>'
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

        full = _absolute(
            href,
            BASE_URL
        )

        low = full.lower()

        if (
            "/anime/" in low
            or "/show/" in low
            or "/tv/" in low
            or "/series/" in low
        ):

            results.append(
                {
                    "title": text,
                    "url": full
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

    for item in results:

        if _normalize(
            item["title"]
        ) == wanted:

            return item["url"]

    for item in results:

        current = _normalize(
            item["title"]
        )

        if (
            wanted in current
            or current in wanted
        ):

            return item["url"]

    return results[0]["url"]


# ============================================================
# EPISODE
# ============================================================

def get_episode_url(
    anime_url,
    episode_number
):

    status, body = _request(
        anime_url,
        referer=BASE_URL + "/"
    )

    if status != 200:
        return None

    try:

        target = int(
            episode_number
        )

    except Exception:

        return None

    links = re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>'
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

        match = re.search(
            r"(?:episode|ep|الحلقة)"
            r"\s*[- ]?0*(\d+)",
            text,
            re.I
        )

        if not match:

            match = re.search(
                r"[-_/](\d{1,3})(?:[-_/]|$)",
                href
            )

        if not match:
            continue

        try:

            number = int(
                match.group(1)
            )

        except Exception:

            continue

        if number == target:

            return _absolute(
                href,
                anime_url
            )

    return None


# ============================================================
# DOOPLAYER
# ============================================================

def extract_dooplayer_data(
    episode_html
):

    players = []

    pattern = re.compile(
        r'<li\b'
        r'[^>]*data-post=["\'](\d+)["\']'
        r'[^>]*data-nume=["\'](\d+)["\']'
        r'[^>]*>'
        r'([\s\S]*?)'
        r'</li>',
        re.I
    )

    for match in pattern.finditer(
        episode_html
    ):

        post_id = match.group(1)
        nume = match.group(2)
        block = match.group(3)

        title = ""

        title_match = re.search(
            r'class=["\']title["\']'
            r'[^>]*>([^<]+)',
            block,
            re.I
        )

        if title_match:

            title = _clean(
                title_match.group(1)
            )

        players.append(
            {
                "post_id": post_id,
                "nume": nume,
                "title": title
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
        referer=BASE_URL + "/"
    )

    if status != 200:
        return []

    return extract_dooplayer_data(
        body
    )


# ============================================================
# PLAYER SELECTION
# ============================================================

TARGET_PLAYERS = [
    "streamhg",
    "hgcloud",
    "hg cloud",
    "stream hg",
]


def select_players(
    players
):

    selected = []
    others = []

    for player in players:

        name = _normalize(
            player.get(
                "title",
                ""
            )
        )

        if any(
            target in name
            for target in TARGET_PLAYERS
        ):

            selected.append(
                player
            )

        else:

            others.append(
                player
            )

    # StreamHG first.
    # Other players remain as fallback.
    selected.extend(
        others
    )

    # If absolutely nothing matched,
    # try nume=5, which was observed
    # as a StreamHG option in the previous
    # version of the scraper.
    if not selected:

        for player in players:

            if str(
                player.get("nume")
            ) == "5":

                selected.append(
                    player
                )

    logger.info(
        "Player order: %s",
        selected
    )

    return selected


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
        + str(post_id)
        + "/tv/"
        + str(nume)
    )

    logger.info(
        "DooPlayer API: %s",
        api_url
    )

    status, body = _request(
        api_url,
        referer=referer,
        origin=BASE_URL,
        ajax=True
    )

    if status != 200:
        return None

    try:

        data = json.loads(
            body
        )

    except Exception:

        return None

    embed = (
        data.get("embed_url")
        or data.get("embed")
        or data.get("url")
    )

    if not embed:
        return None

    embed = _clean(
        embed
    )

    logger.info(
        "Embed: %s",
        embed
    )

    return embed


# ============================================================
# URL EXTRACTION
# ============================================================

def _looks_like_media_url(
    url
):

    low = url.lower()

    return (
        ".m3u8" in low
        or ".mp4" in low
    )


def _extract_urls(
    text,
    base
):

    found = []

    if not text:
        return found

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

    # Direct media URLs.
    patterns = [

        r'https?://[^"\'<>\s]+?\.m3u8(?:\?[^"\'<>\s]*)?',

        r'https?://[^"\'<>\s]+?\.mp4(?:\?[^"\'<>\s]*)?',

        r'["\'](?:file|source|src|url|hls|hls_direct)["\']'
        r'\s*:\s*["\']([^"\']+)["\']',

        r'(?:file|source|src|url|hls|hls_direct)'
        r'\s*=\s*["\']([^"\']+)["\']',

    ]

    for pattern in patterns:

        for match in re.finditer(
            pattern,
            text,
            re.I
        ):

            if match.groups():

                value = match.group(1)

            else:

                value = match.group(0)

            value = _clean(
                value
            )

            value = _absolute(
                value,
                base
            )

            if (
                value
                and _looks_like_media_url(value)
                and value not in found
            ):

                found.append(
                    value
                )

    return found


def _extract_iframes(
    text,
    base
):

    results = []

    if not text:
        return results

    iframe_pattern = re.compile(
        r'<iframe\b[^>]*'
        r'(?:src|data-src|data-url)'
        r'=["\']([^"\']+)["\']',
        re.I
    )

    for match in iframe_pattern.finditer(
        text
    ):

        url = _absolute(
            match.group(1),
            base
        )

        if (
            url
            and url not in results
        ):

            results.append(
                url
            )

    # Also inspect common JS assignments.
    js_pattern = re.compile(
        r'(?:iframe|embed|player|src|url)'
        r'\s*[:=]\s*["\']([^"\']+)["\']',
        re.I
    )

    for match in js_pattern.finditer(
        text
    ):

        url = _absolute(
            match.group(1),
            base
        )

        if (
            url
            and (
                "http://" in url
                or "https://" in url
            )
            and url not in results
        ):

            results.append(
                url
            )

    return results


# ============================================================
# PLAYER SCANNER
# ============================================================

def scan_player(
    player_url,
    referer,
    depth=0,
    visited=None
):

    if visited is None:
        visited = set()

    if not player_url:
        return None

    if depth > 3:
        return None

    if player_url in visited:
        return None

    visited.add(
        player_url
    )

    logger.info(
        "Scanning player depth=%s: %s",
        depth,
        player_url
    )

    status, body = _request(
        player_url,
        referer=referer,
        origin=_origin(player_url),
        ajax=False,
        timeout=25
    )

    if status != 200 or not body:
        return None

    # --------------------------------------------------------
    # 1. Direct media URL
    # --------------------------------------------------------

    media_urls = _extract_urls(
        body,
        player_url
    )

    if media_urls:

        logger.info(
            "Direct media found: %s",
            media_urls[0]
        )

        return {
            "url": media_urls[0],
            "referer": player_url,
            "origin": _origin(player_url)
        }

    # --------------------------------------------------------
    # 2. Search explicitly for StreamRuby.
    # --------------------------------------------------------

    streamruby_candidates = []

    for match in re.finditer(
        r'https?://[^"\'<>\s]+',
        body,
        re.I
    ):

        candidate = _clean(
            match.group(0)
        )

        if (
            "streamruby" in candidate.lower()
            or ".m3u8" in candidate.lower()
        ):

            streamruby_candidates.append(
                candidate
            )

    for candidate in streamruby_candidates:

        if _looks_like_media_url(
            candidate
        ):

            return {
                "url": candidate,
                "referer": player_url,
                "origin": _origin(player_url)
            }

    # --------------------------------------------------------
    # 3. Follow iframe/embed URLs.
    # --------------------------------------------------------

    children = _extract_iframes(
        body,
        player_url
    )

    for child in children:

        result = scan_player(
            child,
            player_url,
            depth=depth + 1,
            visited=visited
        )

        if result:

            return result

    return None


def extract_media_url(
    player_url,
    referer
):

    result = scan_player(
        player_url,
        referer
    )

    if not result:
        logger.info(
            "No media URL found"
        )

        return None

    return result


# ============================================================
# PLAYER LOOP
# ============================================================

def get_stream_from_players(
    players,
    episode_url
):

    selected = select_players(
        players
    )

    for player in selected:

        logger.info(
            "Trying player: %s",
            player
        )

        embed = get_player_embed(
            player.get("post_id"),
            player.get("nume"),
            episode_url
        )

        if not embed:
            continue

        result = extract_media_url(
            embed,
            episode_url
        )

        if not result:
            continue

        return {
            "url": result.get("url"),
            "referer": result.get(
                "referer",
                embed
            ),
            "origin": result.get(
                "origin",
                _origin(embed)
            ),
            "player": player.get(
                "title",
                "Stream"
            )
        }

    return None


# ============================================================
# SERIES
# ============================================================

def series(
    imdb_id,
    season,
    episode
):

    logger.info(
        "START SERIES %s S%s E%s",
        imdb_id,
        season,
        episode
    )

    title = get_anime_name(
        imdb_id
    )

    if not title:
        logger.info(
            "No title"
        )
        return None

    anime_url = search_anime(
        title
    )

    if not anime_url:
        logger.info(
            "Anime not found"
        )
        return None

    episode_url = get_episode_url(
        anime_url,
        episode
    )

    if not episode_url:
        logger.info(
            "Episode not found"
        )
        return None

    players = get_episode_players(
        episode_url
    )

    if not players:
        logger.info(
            "No players"
        )
        return None

    return get_stream_from_players(
        players,
        episode_url
    )


# ============================================================
# MOVIE
# ============================================================

def movie(
    imdb_id
):

    # Project is currently anime-series only.
    return None


# ============================================================
# MEGASOURCE ENTRY POINT
# ============================================================

def get_streams(
    media_type,
    media_id,
    config=None
):

    if media_type != "series":
        return []

    imdb_id, season, episode = _parse_media_id(
        media_id
    )

    if not imdb_id:
        return []

    if not season:
        season = 1

    if not episode:
        episode = 1

    try:

        season = int(
            season
        )

        episode = int(
            episode
        )

    except Exception:

        return []

    result = series(
        imdb_id,
        season,
        episode
    )

    if not result:
        logger.info(
            "No stream result"
        )
        return []

    stream_url = result.get(
        "url"
    )

    if not stream_url:
        return []

    referer = result.get(
        "referer",
        BASE_URL + "/"
    )

    origin = result.get(
        "origin",
        BASE_URL
    )

    player_name = result.get(
        "player",
        ""
    )

    return [
        {
            "name": TITLE,

            "title": (
                player_name
                or "Anime Stream"
            ),

            "url": stream_url,

            "behaviorHints": {

                "notMyMetadata": True,

                "notWebReady": True,

                "proxyHeaders": {

                    "request": {

                        "User-Agent":
                            USER_AGENT,

                        "Referer":
                            referer,

                        "Origin":
                            origin

                    }

                }

            }

        }
    ]
