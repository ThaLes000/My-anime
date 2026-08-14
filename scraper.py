import http.cookiejar
import json
import re
import html
import urllib.error
import urllib.parse
import urllib.request


TITLE = "MegaSource Anime"
VERSION = "1.0.0"
DESCRIPTION = "Anime scraper"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)

# Put your real website domain here
BASE_URL = "https://nxxhentai.net"

CINEMETA_URL = "https://v3-cinemeta.strem.io"


_cookiejar = http.cookiejar.CookieJar()

_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(_cookiejar)
)


def _request(url, referer=None, origin=None):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    }

    if referer:
        headers["Referer"] = referer

    if origin:
        headers["Origin"] = origin

    request = urllib.request.Request(
        url,
        headers=headers,
        method="GET",
    )

    try:
        with _opener.open(request, timeout=15) as response:
            return (
                response.status,
                response.read().decode("utf-8", errors="replace"),
            )

    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""

        return exc.code, body

    except Exception:
        return 0, ""


def _clean(value):
    if not value:
        return ""

    value = html.unescape(value)
    value = value.replace("\\/", "/")
    value = value.replace("\\u0026", "&")
    value = value.replace("\\x26", "&")
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def _normalize(value):
    value = _clean(value)

    value = value.lower()
    value = value.replace("-", " ")
    value = value.replace("_", " ")

    value = re.sub(
        r"[^\w\s\u0600-\u06ff]",
        " ",
        value,
        flags=re.UNICODE,
    )

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def _absolute(url, base):
    url = _clean(url)

    if not url:
        return ""

    return urllib.parse.urljoin(base, url)


def _get_origin(url):
    parsed = urllib.parse.urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return ""

    return (
        parsed.scheme
        + "://"
        + parsed.netloc
    )


def get_anime_name(imdb_id):
    url = (
        CINEMETA_URL
        + "/meta/series/"
        + urllib.parse.quote(imdb_id, safe="")
        + ".json"
    )

    status, body = _request(url)

    if status != 200:
        print("DEBUG: Cinemeta HTTP status:", status)
        return None

    try:
        data = json.loads(body)
    except Exception as exc:
        print("DEBUG: Cinemeta JSON error:", exc)
        return None

    meta = data.get("meta") or {}

    name = (
        meta.get("name")
        or meta.get("originalName")
        or meta.get("original_title")
    )

    if not name:
        print("DEBUG: Cinemeta returned no anime name")
        return None

    return _clean(name)


def search_anime(name):
    query = urllib.parse.urlencode({
        "s": name
    })

    search_url = (
        BASE_URL.rstrip("/")
        + "/?"
        + query
    )

    print("DEBUG: Search URL:", search_url)

    status, body = _request(
        search_url,
        referer=BASE_URL.rstrip("/") + "/",
    )

    print("DEBUG: Search HTTP status:", status)

    if status != 200:
        return None

    results = []

    pattern = re.compile(
        r'<a\b'
        r'[^>]*href=["\']([^"\']*?/anime/[^"\']*)["\']'
        r'[^>]*>'
        r'([\s\S]*?)'
        r'</a>',
        re.I,
    )

    for match in pattern.finditer(body):
        href = _clean(match.group(1))
        content = match.group(2)

        title_match = re.search(
            r'<h[1-6]\b[^>]*>([\s\S]*?)</h[1-6]>',
            content,
            re.I,
        )

        if title_match:
            title = title_match.group(1)
        else:
            title = content

        title = re.sub(
            r"<[^>]+>",
            " ",
            title,
        )

        title = _clean(title)

        if not title:
            continue

        url = _absolute(
            href,
            search_url,
        )

        if not url:
            continue

        results.append({
            "title": title,
            "url": url,
        })

    print("DEBUG: Search results:", len(results))

    if not results:
        return None

    wanted = _normalize(name)

    for result in results:
        if _normalize(result["title"]) == wanted:
            return result["url"]

    for result in results:
        current = _normalize(result["title"])

        if (
            wanted in current
            or current in wanted
        ):
            return result["url"]

    return results[0]["url"]


def get_episode_url(anime_url, episode_number):
    status, body = _request(
        anime_url,
        referer=BASE_URL.rstrip("/") + "/",
    )

    print("DEBUG: Anime page HTTP status:", status)

    if status != 200:
        return None

    episode_number = int(episode_number)

    blocks = re.findall(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>'
        r'([\s\S]*?)'
        r'</a>',
        body,
        re.I,
    )

    candidates = []

    for href, content in blocks:

        if "/episodes/" not in href.lower():
            continue

        text = re.sub(
            r"<[^>]+>",
            " ",
            content,
        )

        text = _clean(text)

        number_match = re.search(
            r"(?:الحلقة|episode|ep\.?)\s*"
            r"0*([0-9]+)",
            text,
            re.I,
        )

        if not number_match:
            continue

        found_number = int(
            number_match.group(1)
        )

        if found_number != episode_number:
            continue

        episode_url = _absolute(
            href,
            anime_url,
        )

        if episode_url:
            candidates.append(
                episode_url
            )

    print(
        "DEBUG: Matching episode links:",
        len(candidates),
    )

    if candidates:
        return candidates[0]

    return None


def get_iframe_url(episode_url):
    status, body = _request(
        episode_url,
        referer=BASE_URL.rstrip("/") + "/",
    )

    print(
        "DEBUG: Episode page HTTP status:",
        status,
    )

    if status != 200:
        return None

    iframe_matches = re.findall(
        r"<iframe\b[^>]*\bsrc\s*=\s*"
        r"""["']([^"']+)["']""",
        body,
        re.I,
    )

    print(
        "DEBUG: Iframes found:",
        len(iframe_matches),
    )

    if not iframe_matches:
        return None

    for src in iframe_matches:

        src = _clean(src)

        if not src:
            continue

        iframe_url = _absolute(
            src,
            episode_url,
        )

        if iframe_url:
            return iframe_url

    return None


def get_m3u8(iframe_url, episode_url):
    origin = _get_origin(
        iframe_url
    )

    status, body = _request(
        iframe_url,
        referer=episode_url,
        origin=origin,
    )

    print(
        "DEBUG: Iframe HTTP status:",
        status,
    )

    if status != 200:
        return None

    body = _clean(body)

    patterns = [

        # <source src="...m3u8">
        r'<source\b[^>]*\bsrc\s*=\s*'
        r"""["']([^"']*\.m3u8(?:\?[^"']*)?)["']""",

        # src="...m3u8"
        r'\bsrc\s*=\s*'
        r"""["']([^"']*\.m3u8(?:\?[^"']*)?)["']""",

        # "https://...m3u8"
        r"""["'](https?://[^"']*\.m3u8(?:\?[^"']*)?)["']""",

        # Bare URL
        r"""(https?://[^\s"'<>\\]+\.m3u8(?:\?[^\s"'<>\\]*)?)""",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            body,
            re.I,
        )

        if not match:
            continue

        url = _clean(
            match.group(1)
        )

        if ".m3u8" not in url.lower():
            continue

        return _absolute(
            url,
            iframe_url,
        )

    print(
        "DEBUG: No m3u8 found in iframe HTML"
    )

    return None


def series(imdb_id, season, episode):

    print("=== DEBUG START ===")

    print(
        "DEBUG: IMDb ID:",
        imdb_id,
    )

    print(
        "DEBUG: Season:",
        season,
    )

    print(
        "DEBUG: Episode:",
        episode,
    )

    # 1. Get anime name
    anime_name = get_anime_name(
        imdb_id
    )

    print(
        "DEBUG: Anime name:",
        anime_name,
    )

    if not anime_name:
        print(
            "DEBUG FAIL: get_anime_name()"
        )
        return {}

    # 2. Search anime
    anime_url = search_anime(
        anime_name
    )

    print(
        "DEBUG: Anime URL:",
        anime_url,
    )

    if not anime_url:
        print(
            "DEBUG FAIL: search_anime()"
        )
        return {}

    # 3. Find episode
    episode_url = get_episode_url(
        anime_url,
        episode,
    )

    print(
        "DEBUG: Episode URL:",
        episode_url,
    )

    if not episode_url:
        print(
            "DEBUG FAIL: get_episode_url()"
        )
        return {}

    # 4. Find iframe
    iframe_url = get_iframe_url(
        episode_url
    )

    print(
        "DEBUG: Iframe URL:",
        iframe_url,
    )

    if not iframe_url:
        print(
            "DEBUG FAIL: get_iframe_url()"
        )
        return {}

    # 5. Find m3u8
    m3u8_url = get_m3u8(
        iframe_url,
        episode_url,
    )

    print(
        "DEBUG: M3U8 URL:",
        m3u8_url,
    )

    if not m3u8_url:
        print(
            "DEBUG FAIL: get_m3u8()"
        )
        return {}

    print(
        "=== DEBUG SUCCESS ==="
    )

    return {
        "url": m3u8_url,
        "User-Agent": USER_AGENT,
        "Referer": iframe_url,
        "Origin": _get_origin(
            iframe_url
        ),
    }


def get_streams(
    media_type,
    media_id,
    config=None
):

    print(
        "=== get_streams START ==="
    )

    print(
        "DEBUG media_type:",
        media_type,
    )

    print(
        "DEBUG media_id:",
        media_id,
    )

    if media_type != "series":

        print(
            "DEBUG FAIL: media_type"
        )

        return []

    parts = media_id.split(
        ":",
        2
    )

    print(
        "DEBUG parts:",
        parts,
    )

    if len(parts) != 3:

        print(
            "DEBUG FAIL: media_id format"
        )

        return []

    imdb_id = parts[0]
    season = parts[1]
    episode = parts[2]

    if not imdb_id or not episode:

        print(
            "DEBUG FAIL: missing IMDb or episode"
        )

        return []

    try:
        episode_number = int(
            episode
        )

    except ValueError:

        print(
            "DEBUG FAIL: invalid episode"
        )

        return []

    info = series(
        imdb_id,
        season,
        episode_number,
    )

    if not info:

        print(
            "DEBUG FAIL: series() returned {}"
        )

        return []

    stream_url = info.get(
        "url"
    )

    if not stream_url:

        print(
            "DEBUG FAIL: no stream URL"
        )

        return []

    print(
        "DEBUG STREAM:",
        stream_url,
    )

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

                "proxyHeaders": {

                    "request": {

                        "User-Agent": info.get(
                            "User-Agent",
                            USER_AGENT,
                        ),

                        "Referer": info.get(
                            "Referer",
                            "",
                        ),

                        "Origin": info.get(
                            "Origin",
                            "",
                        ),
                    }
                },
            },
        }
    ]
