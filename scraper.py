import http.cookiejar
import json
import re
import html
import urllib.error
import urllib.parse
import urllib.request


TITLE = "MegaSource Anime"
VERSION = "2.0.0"
DESCRIPTION = "DooPlayer based anime scraper"


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)


BASE_URL = "https://nxxhentai.net/"
CINEMETA_URL = "https://v3-cinemeta.strem.io"


_cookiejar = http.cookiejar.CookieJar()

_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(_cookiejar)
)


def _request(url, referer=None, origin=None):

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": (
            "en-US,en;q=0.9"
        ),
    }


    if referer:
        headers["Referer"] = referer


    if origin:
        headers["Origin"] = origin


    req = urllib.request.Request(
        url,
        headers=headers,
        method="GET"
    )


    try:
        with _opener.open(
            req,
            timeout=25
        ) as response:

            return (
                response.status,
                response.read().decode(
                    "utf-8",
                    errors="replace"
                )
            )


    except urllib.error.HTTPError as e:

        try:
            body = e.read().decode(
                "utf-8",
                errors="replace"
            )

        except Exception:
            body = ""


        return (
            e.code,
            body
        )


    except Exception:

        return (
            0,
            ""
        )



def _clean(value):

    if not value:
        return ""


    value = html.unescape(value)

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



def _absolute(url, base):

    url = _clean(url)

    if not url:
        return ""


    return urllib.parse.urljoin(
        base,
        url
    )



def _origin(url):

    parsed = urllib.parse.urlparse(url)


    if not parsed.scheme or not parsed.netloc:
        return ""


    return (
        parsed.scheme
        + "://"
        + parsed.netloc
    )



def _normalize(value):

    value = _clean(value).lower()


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


    parts = media_id.split(":")


    if len(parts) >= 3:

        return (
            parts[0],
            parts[1],
            parts[2]
        )


    match = re.search(
        r"(tt\d+).*?[:/_-]+(\d+).*?[:/_-]+(\d+)",
        media_id,
        re.I
    )


    if match:

        return (
            match.group(1),
            match.group(2),
            match.group(3)
        )


    return (
        None,
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


    status, body = _request(url)


    if status != 200:
        return None


    try:
        data = json.loads(body)

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


    return _clean(name)
def search_anime(name):

    if not name:
        return None


    query = urllib.parse.urlencode({
        "s": name
    })


    url = (
        BASE_URL.rstrip("/")
        + "/?"
        + query
    )


    status, body = _request(
        url,
        referer=BASE_URL + "/"
    )


    if status != 200:
        return None



    results = []


    pattern = re.compile(
        r'<a\b[^>]*href=["\']([^"\']*?/anime/[^"\']*)["\'][^>]*>'
        r'([\s\S]*?)'
        r'</a>',
        re.I
    )


    for match in pattern.finditer(body):

        href = _clean(
            match.group(1)
        )

        content = match.group(2)


        title = re.sub(
            r"<[^>]+>",
            " ",
            content
        )


        title = _clean(title)


        if not title:
            continue


        results.append(
            {
                "title": title,
                "url": _absolute(
                    href,
                    url
                )
            }
        )



    if not results:
        return None



    wanted = _normalize(name)


    for item in results:

        if _normalize(item["title"]) == wanted:
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



def get_episode_url(anime_url, episode_number):

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



    blocks = re.findall(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>'
        r'([\s\S]*?)'
        r'</a>',
        body,
        re.I
    )



    for href, content in blocks:


        if "/episodes/" not in href.lower():
            continue



        text = re.sub(
            r"<[^>]+>",
            " ",
            content
        )


        text = _clean(text)



        match = re.search(
            r"(?:الحلقة|episode|ep\.?)\s*0*(\d+)",
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

            return _absolute(
                href,
                anime_url
            )



    return None




def get_player_post(episode_url):

    status, body = _request(
        episode_url,
        referer=BASE_URL + "/"
    )


    if status != 200:
        return None



    match = re.search(
        r'data-post=["\'](\d+)["\']',
        body,
        re.I
    )


    if not match:
        return None



    return match.group(1)
def get_player_embed(post_id, nume):

    url = (
        BASE_URL.rstrip("/")
        + f"/wp-json/dooplayer/v2/{post_id}/tv/{nume}"
    )


    status, body = _request(
        url,
        referer=BASE_URL + "/"
    )


    if status != 200:
        return None



    try:
        data = json.loads(body)

    except Exception:
        return None



    embed = data.get(
        "embed_url"
    )


    if not embed:
        return None



    return _clean(embed)




def extract_media_url(player_url, referer):

    if not player_url:
        return None



    origin = _origin(
        player_url
    )



    status, body = _request(
        player_url,
        referer=referer,
        origin=origin
    )


    if status != 200:
        return None



    body = html.unescape(
        body
    )


    body = body.replace(
        "\\/",
        "/"
    )


    patterns = [

        # HLS مباشر
        r'https?://[^"\'>\s]+\.m3u8(?:\?[^"\'>\s]*)?',


        # MP4 مباشر
        r'https?://[^"\'>\s]+\.mp4(?:\?[^"\'>\s]*)?',


        # روابط بدون امتداد واضحة
        r'https?://[^"\'>\s]+(?:token|expiry)[^"\'>\s]*'

    ]



    for pattern in patterns:

        match = re.search(
            pattern,
            body,
            re.I
        )


        if match:

            url = _clean(
                match.group(0)
            )


            if url:
                return url



    return None





def get_stream_from_players(post_id, episode_url):

    # الترتيب:
    # 4 = HGCloud
    # 1 = NxxPlayer
    # 3 = Playmogo
    # 2 = AbyssPlayer


    players = [
        4,
        1,
        3,
        2
    ]



    for nume in players:


        iframe = get_player_embed(
            post_id,
            nume
        )


        if not iframe:
            continue



        stream = extract_media_url(
            iframe,
            episode_url
        )


        if not stream:
            continue



        return {
            "url": stream,
            "referer": iframe,
            "origin": _origin(iframe)
        }



    return None
def series(imdb_id, season, episode):

    anime_name = get_anime_name(
        imdb_id
    )


    if not anime_name:
        return None



    anime_url = search_anime(
        anime_name
    )


    if not anime_url:
        return None



    episode_url = get_episode_url(
        anime_url,
        episode
    )


    if not episode_url:
        return None



    post_id = get_player_post(
        episode_url
    )


    if not post_id:
        return None



    stream = get_stream_from_players(
        post_id,
        episode_url
    )


    if not stream:
        return None



    return stream





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



    if not imdb_id or not episode:
        return []



    try:

        episode_number = int(
            episode
        )

    except Exception:

        return []



    result = series(
        imdb_id,
        season or "1",
        episode_number
    )



    if not result:
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
                "Episode "
                + str(episode_number)
            ),

            "url": stream_url,


            "behaviorHints": {

                "notMyMetadata": True,

                "notWebReady": True,


                "proxyHeaders": {

                    "request": {

                        "User-Agent": USER_AGENT,


                        "Referer": result.get(
                            "referer",
                            ""
                        ),


                        "Origin": result.get(
                            "origin",
                            ""
                        )
                    }
                }
            }
        }
    ]
