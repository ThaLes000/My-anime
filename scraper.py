import http.cookiejar
import json
import re
import html
import urllib.error
import urllib.parse
import urllib.request


TITLE = "MegaSource Anime"
VERSION = "1.1.0"
DESCRIPTION = "Anime stream scraper"

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
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
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
        with _opener.open(request, timeout=25) as response:
            return (
                response.status,
                response.geturl(),
                response.read().decode("utf-8", errors="replace"),
            )

    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""

        return exc.code, exc.geturl(), body

    except Exception:
        return 0, url, ""


def _clean(value):
    if not value:
        return ""

    value = html.unescape(value)

    replacements = {
        "\\/": "/",
        "\\u0026": "&",
        "\\x26": "&",
        "\\u003d": "=",
        "\\u003f": "?",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    value = value.replace("&quot;", '"')
    value = value.replace("&#39;", "'")

    return re.sub(r"\s+", " ", value).strip()


def _normalize(value):
    value = _clean(value).lower()
    value = value.replace("-", " ")
    value = value.replace("_", " ")

    value = re.sub(
        r"[^\w\s\u0600-\u06ff]",
        " ",
        value,
        flags=re.UNICODE,
    )

    return re.sub(r"\s+", " ", value).strip()


def _absolute(url, base):
    url = _clean(url)

    if not url:
        return ""

    return urllib.parse.urljoin(base, url)


def _origin(url):
    parsed = urllib.parse.urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return ""

    return parsed.scheme + "://" + parsed.netloc


def _parse_media_id(media_id):
    media_id = _clean(media_id)

    match = re.match(
        r"^(tt\d+):(\d+):(\d+)$",
        media_id,
        re.I,
    )

    if match:
        return (
            match.group(1),
            match.group(2),
            match.group(3),
        )

    match = re.search(
        r"(tt\d+).*?(\d+).*?(\d+)",
        media_id,
        re.I,
    )

    if match:
        return (
            match.group(1),
            match.group(2),
            match.group(3),
        )

    return None, None, None


def get_anime_name(imdb_id):
    url = (
        CINEMETA_URL
        + "/meta/series/"
        + urllib.parse.quote(imdb_id, safe="")
        + ".json"
    )

    status, _, body = _request(url)

    if status != 200:
        return None

    try:
        data = json.loads(body)
    except Exception:
        return None

    meta = data.get("meta") or {}

    candidates = [
        meta.get("name"),
        meta.get("originalName"),
        meta.get("original_title"),
        meta.get("title"),
    ]

    for value in candidates:
        if value:
            return _clean(str(value))

    return None


def _extract_search_results(body, base):
    results = []

    patterns = [
        re.compile(
            r'<a\b[^>]*href=["\']([^"\']*?/anime/[^"\']+)["\'][^>]*>'
            r'([\s\S]*?)'
            r'</a>',
            re.I,
        ),
        re.compile(
            r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>'
            r'([\s\S]*?)'
            r'</a>',
            re.I,
        ),
    ]

    for pattern in patterns:
        for match in pattern.finditer(body):
            href = _clean(match.group(1))

            if "/anime/" not in href.lower():
                continue

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

            absolute = _absolute(href, base)

            if not absolute:
                continue

            item = {
                "title": title,
                "url": absolute,
            }

            if item not in results:
                results.append(item)

        if results:
            break

    return results


def search_anime(name):
    if not name:
        return None

    query = urllib.parse.urlencode({
        "s": name
    })

    search_url = (
        BASE_URL.rstrip("/")
        + "/?"
        + query
    )

    status, final_url, body = _request(
        search_url,
        referer=BASE_URL.rstrip("/") + "/",
    )

    if status != 200:
        return None

    results = _extract_search_results(
        body,
        final_url,
    )

    if not results:
        return None

    wanted = _normalize(name)

    for result in results:
        if _normalize(result["title"]) == wanted:
            return result["url"]

    for result in results:
        current = _normalize(result["title"])

        if wanted in current or current in wanted:
            return result["url"]

    return results[0]["url"]


def get_episode_url(anime_url, episode_number):
    status, final_url, body = _request(
        anime_url,
        referer=BASE_URL.rstrip("/") + "/",
    )

    if status != 200:
        return None

    try:
        target = int(episode_number)
    except Exception:
        return None

    episode_pattern = re.compile(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>'
        r'([\s\S]*?)'
        r'</a>',
        re.I,
    )

    for match in episode_pattern.finditer(body):
        href = _clean(match.group(1))

        if "/episodes/" not in href.lower():
            continue

        content = match.group(2)

        text = re.sub(
            r"<[^>]+>",
            " ",
            content,
        )

        text = _clean(text)

        number_match = re.search(
            r"(?:الحلقة|episode|ep\.?)\s*0*(\d+)",
            text,
            re.I,
        )

        if not number_match:
            continue

        try:
            number = int(number_match.group(1))
        except Exception:
            continue

        if number == target:
            return _absolute(
                href,
                final_url,
            )

    return None


def _extract_urls(body):
    body = html.unescape(body)

    for old, new in (
        ("\\/", "/"),
        ("\\u0026", "&"),
        ("\\x26", "&"),
        ("\\u003d", "="),
        ("\\u003f", "?"),
    ):
        body = body.replace(old, new)

    urls = []

    patterns = [
        r'<iframe\b[^>]*\bsrc\s*=\s*["\']([^"\']+)["\']',
        r'data-watch\s*=\s*["\']([^"\']+)["\']',
        r'data-src\s*=\s*["\']([^"\']+)["\']',
        r'data-embed\s*=\s*["\']([^"\']+)["\']',
        r'data-url\s*=\s*["\']([^"\']+)["\']',
        r'<video\b[^>]*\bsrc\s*=\s*["\']([^"\']+)["\']',
    ]

    for pattern in patterns:
        for match in re.finditer(
            pattern,
            body,
            re.I,
        ):
            value = _clean(match.group(1))

            if value and value not in urls:
                urls.append(value)

    return urls


def get_iframe_urls(episode_url):
    status, final_url, body = _request(
        episode_url,
        referer=BASE_URL.rstrip("/") + "/",
    )

    if status != 200:
        return []

    urls = _extract_urls(body)

    results = []

    for url in urls:
        absolute = _absolute(
            url,
            final_url,
        )

        if not absolute:
            continue

        if absolute not in results:
            results.append(absolute)

    return results


def _extract_m3u8(body, base_url):
    body = html.unescape(body)

    for old, new in (
        ("\\/", "/"),
        ("\\u0026", "&"),
        ("\\x26", "&"),
        ("\\u003d", "="),
        ("\\u003f", "?"),
    ):
        body = body.replace(old, new)

    patterns = [
        r'<source\b[^>]*\bsrc\s*=\s*["\']([^"\']+\.m3u8(?:\?[^"\']*)?)["\']',

        r'\bsrc\s*=\s*["\']([^"\']+\.m3u8(?:\?[^"\']*)?)["\']',

        r'\bfile\s*:\s*["\']([^"\']+\.m3u8(?:\?[^"\']*)?)["\']',

        r'\bfile\s*=\s*["\']([^"\']+\.m3u8(?:\?[^"\']*)?)["\']',

        r'["\'](https?://[^"\']+\.m3u8(?:\?[^"\']*)?)["\']',

        r'(https?://[^\s"\'<>\\]+\.m3u8(?:\?[^\s"\'<>\\]*)?)',

        r'(//[^\s"\'<>\\]+\.m3u8(?:\?[^\s"\'<>\\]*)?)',

        r'["\']([^"\']*\.m3u8(?:\?[^"\']*)?)["\']',
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            body,
            re.I,
        )

        if not match:
            continue

        value = _clean(match.group(1))

        if not value:
            continue

        if value.startswith("//"):
            parsed = urllib.parse.urlparse(
                base_url
            )

            value = parsed.scheme + ":" + value

        if ".m3u8" not in value.lower():
            continue

        return _absolute(
            value,
            base_url,
        )

    return None


def get_m3u8_from_url(url, referer):
    origin = _origin(url)

    status, final_url, body = _request(
        url,
        referer=referer,
        origin=origin,
    )

    if status != 200:
        return None

    return _extract_m3u8(
        body,
        final_url,
    )


def resolve_stream(episode_url):
    iframe_urls = get_iframe_urls(
        episode_url
    )

    for iframe_url in iframe_urls:
        m3u8 = get_m3u8_from_url(
            iframe_url,
            episode_url,
        )

        if m3u8:
            return {
                "url": m3u8,
                "referer": iframe_url,
                "origin": _origin(iframe_url),
            }

    m3u8 = get_m3u8_from_url(
        episode_url,
        BASE_URL.rstrip("/") + "/",
    )

    if m3u8:
        return {
            "url": m3u8,
            "referer": episode_url,
            "origin": _origin(episode_url),
        }

    return None


def series(imdb_id, season, episode):
    anime_name = get_anime_name(
        imdb_id
    )

    if not anime_name:
        return {}

    anime_url = search_anime(
        anime_name
    )

    if not anime_url:
        return {}

    episode_url = get_episode_url(
        anime_url,
        episode,
    )

    if not episode_url:
        return {}

    stream = resolve_stream(
        episode_url
    )

    if not stream:
        return {}

    return {
        "url": stream["url"],
        "User-Agent": USER_AGENT,
        "Referer": stream["referer"],
        "Origin": stream["origin"],
    }


def get_streams(
    media_type,
    media_id,
    config=None,
):
    if media_type != "series":
        return []

    imdb_id, season, episode = _parse_media_id(
        media_id
    )

    if not imdb_id or not episode:
        return []

    try:
        episode_number = int(episode)
    except Exception:
        return []

    info = series(
        imdb_id,
        season or "1",
        episode_number,
    )

    if not info:
        return []

    stream_url = info.get("url")

    if not stream_url:
        return []

    return [
        {
            "name": TITLE,
            "title": "Episode " + str(episode_number),
            "url": stream_url,
            "behaviorHints": {
                "notMyMetadata": True,
                "notWebReady": True,
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
