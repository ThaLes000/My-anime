import http.cookiejar
import json
import logging
import html
import re
import urllib.error
import urllib.parse
import urllib.request


TITLE = "MegaSource Anime"
VERSION = "3.1.0"
DESCRIPTION = "WordPress DooPlayer Anime Provider"


BASE_URL = "https://الموقع.net/"

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

        "Accept":
            "text/html,application/xhtml+xml,"
            "application/json,text/plain,*/*",

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
            ).encode(
                "utf-8"
            )

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
                response.read()
                .decode(
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

    return re.sub(
        r"\s+",
        " ",
        value
    ).strip()


def _absolute(
    url,
    base
):

    return urllib.parse.urljoin(
        base,
        _clean(url)
    )


def _origin(url):

    try:

        parsed = urllib.parse.urlparse(
            url
        )

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


        if any(
            path in full.lower()
            for path in [
                "/anime/",
                "/show/",
                "/tv/",
                "/series/"
            ]
        ):

            results.append(
                {
                    "title": text,
                    "url": full
                }
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


        if match:

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
        "Players: %s",
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
            "Episode page failed %s",
            status
        )

        return []


    return extract_dooplayer_data(
        body
    )



def select_players(
    players
):

    # لا نعتمد على رقم ثابت
    # نجرب المشغلات كلها بالترتيب الموجود

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

                selected.append(
                    player
                )


    # إضافة أي مشغل لم يتم اختياره
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


    return _clean(
        embed
    )



def extract_media_url(
    player_url,
    referer
):

    if not player_url:

        return None


    logger.info(
        "Scanning: %s",
        player_url
    )


    status, body = _request(
        player_url,
        referer=referer,
        origin=_origin(player_url),
        ajax=True
    )


    if status != 200 or not body:

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


        for match in matches:


            url = match


            if isinstance(
                match,
                tuple
            ):

                url = match[0]


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
                ".m3u8" in url
                or ".mp4" in url
            ):

                logger.info(
                    "Media found: %s",
                    url
                )

                return url



    # بحث احتياطي داخل كل الروابط

    urls = re.findall(
        r'https?://[^\s"\'<>]+',
        body
    )


    for url in urls:

        url = _clean(
            url
        )


        if (
            ".m3u8" in url
            or ".mp4" in url
        ):

            logger.info(
                "Fallback media: %s",
                url
            )

            return url



    return None
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
            player["post_id"],
            player["nume"],
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

                "origin": _origin(embed),

                "player": (
                    player.get(
                        "title",
                        "Anime Stream"
                    )
                )

            }


    return None



def series(
    imdb_id,
    season,
    episode
):

    logger.info(
        "START %s S%s E%s",
        imdb_id,
        season,
        episode
    )


    title = get_anime_name(
        imdb_id
    )


    if not title:

        return None


    anime_url = search_anime(
        title
    )


    if not anime_url:

        return None


    episode_url = get_episode_url(
        anime_url,
        episode
    )


    if not episode_url:

        return None


    players = get_episode_players(
        episode_url
    )


    if not players:

        return None


    return get_stream_from_players(
        players,
        episode_url
    )



def movie(
    imdb_id
):

    return None



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



    return [

        {

            "name": TITLE,


            "title": (

                result.get(
                    "player"
                )
                or
                "Anime Stream"

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
                            result.get(
                                "referer",
                                ""
                            ),


                        "Origin":
                            result.get(
                                "origin",
                                ""
                            )

                    }

                }

            }

        }

    ]
