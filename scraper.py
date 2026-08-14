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


BASE_URL = "https://nxxhentai.net/"

CINEMETA_URL = (
    "https://v3-cinemeta.strem.io"
)


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)


logging.basicConfig(
    level=logging.INFO,
    format="[MegaSource] %(message)s"
)

logger = logging.getLogger(
    "MegaSource"
)


_cookiejar = http.cookiejar.CookieJar()

_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(
        _cookiejar
    )
)


# ============================================================
# HTTP
# ============================================================

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
            "en-US,en;q=0.9"
    }

    if referer:
        headers["Referer"] = referer

    if origin:
        headers["Origin"] = origin

    if ajax:
        headers["X-Requested-With"] = (
            "XMLHttpRequest"
        )

    body = None

    if method.upper() == "POST":

        if isinstance(data, dict):

            body = urllib.parse.urlencode(
                data
            ).encode("utf-8")

            headers["Content-Type"] = (
                "application/x-www-form-urlencoded"
            )

        elif data:

            body = data

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method
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

    except urllib.error.HTTPError as error:

        try:

            text = error.read().decode(
                "utf-8",
                errors="replace"
            )

        except Exception:

            text = ""

        return (
            error.code,
            text
        )

    except Exception as error:

        logger.info(
            "Request error %s : %s",
            url,
            error
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
        "\\u003F",
        "?"
    )

    value = value.replace(
        "\\u003D",
        "="
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
        value
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

    parts = media_id.split(
        ":"
    )

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
        logger.info(
            "Search failed: %s",
            status
        )
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

        if any(
            path in full.lower()
            for path in (
                "/anime/",
                "/show/",
                "/tv/",
                "/series/"
            )
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

            logger.info(
                "Exact match: %s",
                item["url"]
            )

            return item["url"]

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

    logger.info(
        "Anime page: %s",
        anime_url
    )

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

            episode_url = _absolute(
                href,
                anime_url
            )

            logger.info(
                "Episode found: %s",
                episode_url
            )

            return episode_url

    logger.info(
        "Episode not found: %s",
        episode_number
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

        logger.info(
            "Episode HTML failed: %s",
            status
        )

        return []

    return extract_dooplayer_data(
        body
    )


def select_players(
    players
):

    priority = [
        "streamhg",
        "hgcloud",
        "hg cloud",
        "nxxplayer",
        "doodstream",
        "fastserver"
    ]

    selected = []

    for name in priority:

        for player in players:

            title = _normalize(
                player.get(
                    "title",
                    ""
                )
            )

            if name in title:

                if player not in selected:

                    selected.append(
                        player
                    )

    for player in players:

        if player not in selected:

            selected.append(
                player
            )

    logger.info(
        "Player order: %s",
        selected
    )

    return selected


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
        origin=_origin(BASE_URL),
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
            "Invalid DooPlayer JSON"
        )

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
# DIRECT MEDIA EXTRACTION
# ============================================================

def _find_media_in_text(
    body,
    base_url
):

    if not body:
        return None

    body = html.unescape(
        body
    )

    body = body.replace(
        "\\/",
        "/"
    )

    body = body.replace(
        "\\u0026",
        "&"
    )

    patterns = [

        r'https?://[^"\'<>\s]+\.m3u8(?:\?[^"\'<>\s]*)?',

        r'https?://[^"\'<>\s]+\.mp4(?:\?[^"\'<>\s]*)?',

        r'<source[^>]+src=["\']([^"\']+)["\']',

        r'<video[^>]+src=["\']([^"\']+)["\']',

        r'["\']file["\']\s*:\s*["\']([^"\']+)',

        r'["\']source["\']\s*:\s*["\']([^"\']+)',

        r'["\']url["\']\s*:\s*["\']([^"\']+)',

        r'(?:file|src|source|url)'
        r'\s*=\s*["\']([^"\']+)'
    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            body,
            re.I
        )

        if not isinstance(
            matches,
            list
        ):
            matches = [matches]

        for match in matches:

            if isinstance(
                match,
                tuple
            ):

                url = match[0]

            else:

                url = match

            url = _clean(
                url
            )

            if not url:
                continue

            if url.startswith(
                "blob:"
            ):
                continue

            if (
                ".m3u8" in url.lower()
                or ".mp4" in url.lower()
            ):

                url = _absolute(
                    url,
                    base_url
                )

                logger.info(
                    "Media found: %s",
                    url
                )

                return url

    return None


def extract_media_url(
    player_url,
    referer
):

    if not player_url:
        return None

    logger.info(
        "Scanning player: %s",
        player_url
    )

    status, body = _request(
        player_url,
        referer=referer,
        origin=_origin(player_url),
        ajax=True
    )

    if status != 200 or not body:

        logger.info(
            "Player request failed: %s",
            status
        )

        return None

    media = _find_media_in_text(
        body,
        player_url
    )

    if media:
        return media

    logger.info(
        "No direct media in player"
    )

    return None


# ============================================================
# IFRAME FALLBACK
# ============================================================

def get_iframe_urls(
    episode_url
):

    status, body = _request(
        episode_url,
        referer=BASE_URL + "/"
    )

    if status != 200 or not body:
        return []

    body = html.unescape(
        body
    )

    body = body.replace(
        "\\/",
        "/"
    )

    matches = re.findall(
        r'<iframe\b[^>]*'
        r'(?:src|data-src)=["\']([^"\']+)["\']',
        body,
        re.I
    )

    urls = []

    for value in matches:

        url = _absolute(
            value,
            episode_url
        )

        if not url:
            continue

        if url not in urls:

            urls.append(
                url
            )

    logger.info(
        "Iframe URLs: %s",
        urls
    )

    return urls


def extract_iframe_media(
    iframe_url,
    episode_url
):

    if not iframe_url:
        return None

    logger.info(
        "Trying iframe: %s",
        iframe_url
    )

    status, body = _request(
        iframe_url,
        referer=episode_url,
        origin=_origin(iframe_url),
        ajax=False
    )

    if status != 200 or not body:
        return None

    media = _find_media_in_text(
        body,
        iframe_url
    )

    if media:
        return {
            "url": media,
            "referer": iframe_url,
            "origin": _origin(
                iframe_url
            ),
            "player": "Iframe HLS"
        }

    return None


# ============================================================
# PLAYER PIPELINE
# ============================================================

def get_stream_from_players(
    players,
    episode_url
):

    players = select_players(
        players
    )

    for player in players:

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

        media = extract_media_url(
            embed,
            episode_url
        )

        if media:

            return {
                "url": media,

                "referer": embed,

                "origin": _origin(
                    embed
                ),

                "player": (
                    player.get(
                        "title"
                    )
                    or
                    "Anime Stream"
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

    # --------------------------------------------------------
    # 1. IMDb -> Cinemeta
    # --------------------------------------------------------

    title = get_anime_name(
        imdb_id
    )

    if not title:

        logger.info(
            "No title from Cinemeta"
        )

        return None

    # --------------------------------------------------------
    # 2. Search site
    # --------------------------------------------------------

    anime_url = search_anime(
        title
    )

    if not anime_url:

        logger.info(
            "Anime not found"
        )

        return None

    # --------------------------------------------------------
    # 3. Find episode
    # --------------------------------------------------------

    episode_url = get_episode_url(
        anime_url,
        episode
    )

    if not episode_url:

        logger.info(
            "Episode not found"
        )

        return None

    # --------------------------------------------------------
    # 4. DooPlayer path
    # --------------------------------------------------------

    players = get_episode_players(
        episode_url
    )

    if players:

        result = get_stream_from_players(
            players,
            episode_url
        )

        if result:

            logger.info(
                "DooPlayer stream succeeded"
            )

            return result

    # --------------------------------------------------------
    # 5. Iframe fallback
    # --------------------------------------------------------

    logger.info(
        "DooPlayer failed; trying iframe fallback"
    )

    iframe_urls = get_iframe_urls(
        episode_url
    )

    for iframe_url in iframe_urls:

        result = extract_iframe_media(
            iframe_url,
            episode_url
        )

        if result:

            logger.info(
                "Iframe stream succeeded"
            )

            return result

    # --------------------------------------------------------
    # 6. Nothing found
    # --------------------------------------------------------

    logger.info(
        "No playable stream found"
    )

    return None


# ============================================================
# MOVIE
# ============================================================

def movie(
    imdb_id
):

    return None


# ============================================================
# MEGASOURCE ENTRY POINT
# ============================================================

def get_streams(
    media_type,
    media_id,
    config=None
):

    logger.info(
        "get_streams type=%s id=%s",
        media_type,
        media_id
    )

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
        ""
    )

    origin = result.get(
        "origin",
        ""
    )

    player_name = result.get(
        "player"
    ) or "Anime Stream"

    logger.info(
        "RETURNING STREAM %s",
        stream_url
    )

    return [
        {
            "name": TITLE,

            "title": player_name,

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
