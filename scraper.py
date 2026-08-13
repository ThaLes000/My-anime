import http.cookiejar
import json
import re
import html
import urllib.error
import urllib.parse
import urllib.request


TITLE = "MegaSource Anime Scraper"
VERSION = "1.0.0"
DESCRIPTION = "Anime stream scraper"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)

# Put your website domain here
BASE_URL = "https://Nxxhentai.net"

CINEMETA_URL = "https://v3-cinemeta.strem.io"


_cookiejar = http.cookiejar.CookieJar()

_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(_cookiejar)
)


def _request(url, method="GET", data=None, headers=None):
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
    }

    if headers:
        request_headers.update(headers)

    body = None

    if method == "POST":
        if isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode("utf-8")
        elif data is not None:
            body = data

    req = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )

    try:
        with _opener.open(req, timeout=20) as resp:
            return (
                resp.status,
                resp.read().decode("utf-8", errors="replace"),
            )

    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""

        return exc.code, body

    except Exception:
        return 0, ""


def get_anime_name(imdb_id):
    url = (
        CINEMETA_URL
        + "/meta/series/"
        + urllib.parse.quote(imdb_id)
        + ".json"
    )

    status, body = _request(url)

    if status != 200:
        return None

    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None

    meta = data.get("meta") or {}

    return (
        meta.get("name")
        or meta.get("originalName")
    )


def _normalize_text(value):
    if not value:
        return ""

    value = html.unescape(value)
    value = value.replace("-", " ")
    value = re.sub(r"\s+", " ", value)

    return value.strip().lower()


def search_anime(anime_name):
    query = urllib.parse.urlencode({
        "s": anime_name
    })

    search_url = (
        BASE_URL.rstrip("/")
        + "/?"
        + query
    )

    status, body = _request(
        search_url,
        headers={
            "Referer": BASE_URL + "/",
        },
    )

    if status != 200:
        return None

    pattern = re.compile(
        r'<a\b[^>]*href=["\']([^"\']*/anime/[^"\']+)["\'][^>]*>'
        r'(.*?)'
        r'</a>',
        re.I | re.S,
    )

    results = []

    for match in pattern.finditer(body):
        href = html.unescape(match.group(1))

        content = re.sub(
            r"<[^>]+>",
            " ",
            match.group(2),
        )

        title = html.unescape(content)
        title = re.sub(r"\s+", " ", title).strip()

        if not title:
            continue

        results.append({
            "url": urllib.parse.urljoin(
                search_url,
                href,
            ),
            "title": title,
        })

    if not results:
        return None

    wanted = _normalize_text(anime_name)

    for result in results:
        if _normalize_text(result["title"]) == wanted:
            return result["url"]

    for result in results:
        result_title = _normalize_text(result["title"])

        if (
            wanted in result_title
            or result_title in wanted
        ):
            return result["url"]

    return results[0]["url"]


def get_episode_url(anime_url, episode_number):
    status, body = _request(
        anime_url,
        headers={
            "Referer": BASE_URL + "/",
        },
    )

    if status != 200:
        return None

    li_pattern = re.compile(
        r'<li\b[^>]*class=["\'][^"\']*mark-[^"\']*["\'][^>]*>'
        r'(.*?)'
        r'</li>',
        re.I | re.S,
    )

    episode_patterns = [
        re.compile(
            r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>.*?'
            r'<div\b[^>]*class=["\'][^"\']*episodiotitle[^"\']*["\'][^>]*>'
            r'\s*(?:الحلقة|episode|ep\.?)\s*'
            + re.escape(str(episode_number))
            + r'\s*'
            r'</div>',
            re.I | re.S,
        ),

        re.compile(
            r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>.*?'
            r'(?:الحلقة|episode|ep\.?)\s*'
            + re.escape(str(episode_number))
            + r'\b.*?</a>',
            re.I | re.S,
        ),
    ]

    for li in li_pattern.finditer(body):
        block = li.group(1)

        for pattern in episode_patterns:
            match = pattern.search(block)

            if match:
                return urllib.parse.urljoin(
                    anime_url,
                    html.unescape(match.group(1)),
                )

    return None


def _get_origin(url):
    parsed = urllib.parse.urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return ""

    return (
        parsed.scheme
        + "://"
        + parsed.netloc
    )


def get_m3u8_from_episode(episode_url):
    status, body = _request(
        episode_url,
        headers={
            "Referer": BASE_URL + "/",
        },
    )

    if status != 200:
        return None, None

    iframe_match = re.search(
        r'<iframe\b[^>]*\bsrc=["\']([^"\']+)["\']',
        body,
        re.I | re.S,
    )

    if not iframe_match:
        return None, None

    iframe_url = html.unescape(
        iframe_match.group(1)
    )

    iframe_url = urllib.parse.urljoin(
        episode_url,
        iframe_url,
    )

    status, iframe_body = _request(
        iframe_url,
        headers={
            "Referer": episode_url,
            "Origin": _get_origin(iframe_url),
        },
    )

    if status != 200:
        return None, iframe_url

    iframe_body = html.unescape(iframe_body)

    m3u8_match = re.search(
        r'<source\b[^>]*\bsrc=["\']([^"\']*\.m3u8[^"\']*)["\']',
        iframe_body,
        re.I | re.S,
    )

    if not m3u8_match:
        m3u8_match = re.search(
            r'(["\'])([^"\']+\.m3u8(?:\?[^"\']*)?)\1',
            iframe_body,
            re.I | re.S,
        )

        if not m3u8_match:
            return None, iframe_url

        m3u8_url = m3u8_match.group(2)

    else:
        m3u8_url = m3u8_match.group(1)

    m3u8_url = urllib.parse.urljoin(
        iframe_url,
        m3u8_url,
    )

    return m3u8_url, iframe_url


def series(imdb_id, season, episode):
    anime_name = get_anime_name(imdb_id)

    if not anime_name:
        return {}

    anime_url = search_anime(anime_name)

    if not anime_url:
        return {}

    episode_url = get_episode_url(
        anime_url,
        int(episode),
    )

    if not episode_url:
        return {}

    m3u8_url, iframe_url = get_m3u8_from_episode(
        episode_url,
    )

    if not m3u8_url:
        return {}

    return {
        "url": m3u8_url,
        "User-Agent": USER_AGENT,
        "Referer": iframe_url,
        "Origin": _get_origin(iframe_url),
    }


def get_streams(media_type, media_id, config=None):
    imdb_id = media_id
    season = None
    episode = None

    if ":" in media_id:
        parts = media_id.split(":", 2)

        imdb_id = parts[0]
        season = parts[1]
        episode = parts[2]

    if media_type != "series":
        return []

    if not episode:
        return []

    info = series(
        imdb_id,
        season,
        int(episode),
    )

    if not info or not info.get("url"):
        return []

    return [
        {
            "name": TITLE,
            "title": "Episode " + str(episode),
            "url": info["url"],
            "behaviorHints": {
                "notMyMetadata": True,
                "proxyHeaders": {
                    "request": {
                        "User-Agent": info.get(
                            "User-Agent",
                            USER_AGENT,
                        ),
                        "Origin": info.get(
                            "Origin",
                            "",
                        ),
                        "Referer": info.get(
                            "Referer",
                            "",
                        ),
                    }
                },
            },
        }
    ]