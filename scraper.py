"""
MegaSource Anime
================

Protocol:
    TITLE, VERSION, DESCRIPTION

    get_streams(
        media_type: str,
        media_id: str,
        config: dict | None
    ) -> list[dict]

Supports:
    movie
    series

Flow:
    IMDb ID
        |
    Cinemeta
        |
    Site search
        |
    Episode page
        |
    DooPlayer data-post/data-nume
        |
    DooPlayer API
        |
    embed_url
        |
    m3u8/mp4
        |
    MegaSource stream
"""

import http.cookiejar
import json
import logging
import re
import html
import urllib.error
import urllib.parse
import urllib.request


TITLE = "MegaSource Anime"
VERSION = "2.1.0"
DESCRIPTION = "DooPlayer anime scraper"


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)


BASE_URL = "https://nxxhentai.net/"

CINEMETA_URL = (
    "https://v3-cinemeta.strem.io"
)


logging.basicConfig(
    level=logging.INFO
)

logger = logging.getLogger(
    "MegaSource Anime"
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
    headers=None
):

    request_headers = {

        "User-Agent": USER_AGENT,

        "Accept": (
            "application/json,"
            "text/html,"
            "*/*"
        ),

        "Accept-Language":
            "en-US,en;q=0.9"

    }


    if referer:
        request_headers["Referer"] = referer


    if origin:
        request_headers["Origin"] = origin


    if headers:
        request_headers.update(
            headers
        )


    body = None


    if method == "POST":

        if isinstance(data, dict):

            body = urllib.parse.urlencode(
                data
            ).encode(
                "utf-8"
            )

        elif data:

            body = data



    req = urllib.request.Request(

        url,

        data=body,

        headers=request_headers,

        method=method
    )


    try:

        with _opener.open(
            req,
            timeout=20
        ) as response:


            return (

                response.status,

                response.read()
                .decode(
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
            "Request failed %s : %s",
            url,
            exc
        )

        return (

            0,

            ""

        )





def _clean(value):

    if not value:
        return ""


    value = html.unescape(
        value
    )


    value = value.replace(
        "\\/",
        "/"
    )


    value = value.replace(
        "\\u0026",
        "&"
    )


    value = re.sub(
        r"\s+",
        " ",
        value
    )


    return value.strip()





def _absolute(
    url,
    base
):

    url = _clean(
        url
    )


    if not url:
        return ""


    return urllib.parse.urljoin(
        base,
        url
    )





def _origin(url):

    parsed = urllib.parse.urlparse(
        url
    )


    if not parsed.scheme:
        return ""


    if not parsed.netloc:
        return ""


    return (
        parsed.scheme
        + "://"
        + parsed.netloc
    )





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


    value = re.sub(

        r"\s+",

        " ",

        value

    )


    return value.strip()





def _parse_media_id(media_id):

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
        "Cinemeta request: %s",
        url
    )


    status, body = _request(
        url
    )


    if status != 200:

        logger.info(
            "Cinemeta failed status=%s",
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


    name = (

        meta.get("name")

        or meta.get("originalName")

        or meta.get("title")

    )


    name = _clean(
        name
    )


    logger.info(
        "Anime title: %s",
        name
    )


    return name





def search_anime(name):

    if not name:
        return None



    query = urllib.parse.urlencode(
        {
            "s": name
        }
    )


    url = (
        BASE_URL.rstrip("/")
        + "/?"
        + query
    )


    logger.info(
        "Search URL: %s",
        url
    )


    status, body = _request(

        url,

        referer=BASE_URL + "/"

    )


    if status != 200:

        logger.info(
            "Search failed status=%s",
            status
        )

        return None



    results = []



    pattern = re.compile(

        r'<a\b[^>]*href=["\']'
        r'([^"\']+)'
        r'["\'][^>]*>'
        r'([\s\S]*?)'
        r'</a>',

        re.I

    )



    for match in pattern.finditer(
        body
    ):


        href = _clean(
            match.group(1)
        )


        content = match.group(2)



        title = re.sub(

            r"<[^>]+>",

            " ",

            content

        )


        title = _clean(
            title
        )


        if not title:

            continue



        full_url = _absolute(

            href,

            BASE_URL

        )


        if (
            "/anime/" in full_url.lower()
            or "/tv/" in full_url.lower()
        ):


            results.append(

                {

                    "title": title,

                    "url": full_url

                }

            )



    logger.info(
        "Search results found: %s",
        len(results)
    )



    if not results:

        return None



    wanted = _normalize(
        name
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
        "Fallback first result: %s",
        results[0]["url"]
    )


    return results[0]["url"]





def get_episode_url(
    anime_url,
    episode_number
):

    logger.info(
        "Opening anime page: %s",
        anime_url
    )


    status, body = _request(

        anime_url,

        referer=BASE_URL + "/"

    )


    if status != 200:

        logger.info(
            "Anime page failed status=%s",
            status
        )

        return None



    try:

        target = int(
            episode_number
        )

    except Exception:

        return None



    blocks = re.findall(

        r'<a\b[^>]*href=["\']'
        r'([^"\']+)'
        r'["\'][^>]*>'
        r'([\s\S]*?)'
        r'</a>',

        body,

        re.I

    )



    for href, content in blocks:


        if (
            "/episodes/" 
            not in href.lower()
        ):

            continue



        text = re.sub(

            r"<[^>]+>",

            " ",

            content

        )


        text = _clean(
            text
        )



        match = re.search(

            r"(?:الحلقة|episode|ep\.?)"
            r"\s*0*(\d+)",

            text,

            re.I

        )



        if not match:

            continue



        try:

            current = int(
                match.group(1)
            )

        except Exception:

            continue



        if current == target:


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
def extract_players(episode_html):

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


        post_id = match.group(
            1
        )


        nume = match.group(
            2
        )


        block = match.group(
            3
        )


        title_match = re.search(

            r'<span[^>]*class=["\']title["\'][^>]*>'
            r'([^<]+)',

            block,

            re.I

        )


        title = ""


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
        "DooPlayer players found: %s",
        players
    )


    return players





def get_episode_players(
    episode_url
):

    logger.info(
        "Extracting players from: %s",
        episode_url
    )


    status, body = _request(

        episode_url,

        referer=BASE_URL + "/"

    )


    if status != 200:

        logger.info(
            "Episode HTML failed status=%s",
            status
        )

        return []


    return extract_players(
        body
    )





def get_player_embed(
    post_id,
    nume
):

    url = (

        BASE_URL.rstrip("/")

        + "/wp-json/dooplayer/v2/"

        + str(post_id)

        + "/tv/"

        + str(nume)

    )


    logger.info(
        "DooPlayer API: %s",
        url
    )


    status, body = _request(

        url,

        referer=BASE_URL + "/"

    )


    if status != 200:

        logger.info(

            "DooPlayer API failed status=%s",

            status

        )

        return None



    try:

        data = json.loads(
            body
        )

    except Exception:

        logger.info(
            "DooPlayer invalid JSON"
        )

        return None



    embed = data.get(
        "embed_url"
    )


    if not embed:

        logger.info(
            "No embed_url returned"
        )

        return None



    logger.info(
        "Embed URL: %s",
        embed
    )


    return _clean(
        embed
    )





PLAYER_PRIORITY = [

    "streamhg",

    "nxxplayer",

    "doodstream",

    "fastserver",

    "nxxhosting"

]





def sort_players(players):

    def score(player):

        name = _normalize(
            player.get(
                "title",
                ""
            )
        )


        for index, item in enumerate(
            PLAYER_PRIORITY
        ):

            if item in name:

                return index


        return 99



    return sorted(
        players,
        key=score
    )





def extract_media_url(
    player_url,
    referer
):

    if not player_url:

        return None



    logger.info(
        "Extracting media from: %s",
        player_url
    )


    status, body = _request(

        player_url,

        referer=referer,

        origin=_origin(player_url)

    )


    if status != 200:

        logger.info(
            "Player request failed status=%s",
            status
        )

        return None



    body = html.unescape(
        body
    )


    body = body.replace(
        "\\/",
        "/"
    )



    patterns = [

        # HLS

        r'https?://[^"\'>\s]+\.m3u8(?:\?[^"\'>\s]*)?',


        # MP4

        r'https?://[^"\'>\s]+\.mp4(?:\?[^"\'>\s]*)?',


        # JSON file/source/url

        r'["\'](?:file|source|url)["\']\s*:\s*["\']([^"\']+)',


        # Javascript variable

        r'(?:file|src|source)\s*=\s*["\']([^"\']+)'

    ]



    for pattern in patterns:


        match = re.search(

            pattern,

            body,

            re.I

        )


        if match:


            url = _clean(

                match.group(1)

                if match.groups()

                else match.group(0)

            )


            if url:

                logger.info(

                    "Media URL found: %s",

                    url

                )


                return url



    logger.info(
        "No media URL found"
    )


    return None





def get_stream_from_players(
    players,
    episode_url
):

    players = sort_players(
        players
    )


    logger.info(
        "Player priority order: %s",
        players
    )



    for player in players:


        logger.info(

            "Trying player: %s",

            player

        )



        embed = get_player_embed(

            player["post_id"],

            player["nume"]

        )


        if not embed:

            continue



        stream = extract_media_url(

            embed,

            episode_url

        )


        if not stream:

            continue



        return {

            "url": stream,

            "referer": embed,

            "origin": _origin(embed),

            "player": player.get(
                "title",
                ""
            )

        }



    return None
def series(
    imdb_id,
    season,
    episode
):

    anime_name = get_anime_name(
        imdb_id
    )


    if not anime_name:

        logger.info(
            "No anime name from Cinemeta"
        )

        return None



    anime_url = search_anime(
        anime_name
    )


    if not anime_url:

        logger.info(
            "Anime search failed"
        )

        return None



    episode_url = get_episode_url(

        anime_url,

        episode

    )


    if not episode_url:

        logger.info(
            "Episode URL not found"
        )

        return None



    players = get_episode_players(
        episode_url
    )


    if not players:

        logger.info(
            "No DooPlayer players found"
        )

        return None



    stream = get_stream_from_players(

        players,

        episode_url

    )


    if not stream:

        logger.info(
            "No working player found"
        )

        return None



    return stream





def movie(
    imdb_id
):

    return None





def get_streams(
    media_type,
    media_id,
    config=None
):


    imdb_id, season, episode = _parse_media_id(
        media_id
    )



    if not imdb_id:

        return []



    info = None



    if media_type == "series":


        if not season or not episode:

            return []


        try:

            season = int(
                season
            )

            episode = int(
                episode
            )

        except Exception:

            return []



        info = series(

            imdb_id,

            season,

            episode

        )



    elif media_type == "movie":


        info = movie(
            imdb_id
        )



    if not info:

        return []



    stream_url = info.get(
        "url"
    )


    if not stream_url:

        return []



    player_name = info.get(
        "player",
        ""
    )



    return [

        {

            "name": TITLE,


            "title": (

                player_name

                if player_name

                else "Anime"

            ),


            "url": stream_url,


            "behaviorHints": {


                "notMyMetadata": True,


                "notWebReady": True,


                "proxyHeaders": {


                    "request": {


                        "User-Agent": USER_AGENT,


                        "Referer": info.get(

                            "referer",

                            BASE_URL + "/"

                        ),


                        "Origin": info.get(

                            "origin",

                            BASE_URL

                        )

                    }

                }

            }

        }

    ]
