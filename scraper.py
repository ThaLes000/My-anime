import http.cookiejar
import json
import re
import html
import urllib.error
import urllib.parse
import urllib.request


TITLE = "MegaSource Anime"
VERSION = "2.0.0"
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


# ---------------------------------------------------------
# HTTP
# ---------------------------------------------------------

def _request(url, referer=None, origin=None):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
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
                response.read().decode(
                    "utf-8",
                    errors="replace",
                ),
            )

    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode(
                "utf-8",
                errors="replace",
            )
        except Exception:
            body = ""

        return exc.code, body

    except Exception:
        return 0, ""


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

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

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def _strip_html(value):
    if not value:
        return ""

    value = re.sub(
        r"<script\b[^>]*>[\s\S]*?</script>",
        " ",
        value,
        flags=re.I,
    )

    value = re.sub(
        r"<style\b[^>]*>[\s\S]*?</style>",
        " ",
        value,
        flags=re.I,
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    return _clean(value)


def _normalize(value):
    value = _strip_html(value).lower()

    value = value.replace("-", " ")
    value = value.replace("_", " ")

    value = re.sub(
        r"[^\w\s\u0600-\u06ff]",
        " ",
        value,
        flags=re.UNICODE,
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def _absolute(url, base):
    url = _clean(url)

    if not url:
        return ""

    return urllib.parse.urljoin(
        base,
        url,
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


# ---------------------------------------------------------
# MegaSource media_id
# ---------------------------------------------------------

def _parse_media_id(media_id):
    if not media_id:
        return None, None, None

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


# ---------------------------------------------------------
# Cinemeta
# ---------------------------------------------------------

def get_anime_metadata(imdb_id):
    if not imdb_id:
        return None

    url = (
        CINEMETA_URL
        + "/meta/series/"
        + urllib.parse.quote(
            imdb_id,
            safe="",
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

    meta = data.get("meta") or {}

    names = [
        meta.get("name"),
        meta.get("originalName"),
        meta.get("original_title"),
        meta.get("title"),
    ]

    for name in names:
        name = _clean(name)

        if name:
            return {
                "name": name,
                "meta": meta,
            }

    return None


# ---------------------------------------------------------
# Site search
# ---------------------------------------------------------

def search_anime(name):
    if not name:
        return None

    search_url = (
        BASE_URL.rstrip("/")
        + "/?s="
        + urllib.parse.quote(
            name,
            safe="",
        )
    )

    status, body = _request(
        search_url,
        referer=BASE_URL.rstrip("/") + "/",
    )

    if status != 200 or not body:
        return None

    candidates = []

    # Primary WordPress-style result
    pattern = re.compile(
        r'<a\b[^>]*href=["\']'
        r'([^"\']+)'
        r'["\'][^>]*>'
        r'([\s\S]*?)'
        r'</a>',
        re.I,
    )

    for match in pattern.finditer(body):

        href = _clean(match.group(1))

        if "/anime/" not in href.lower():
            continue

        content = match.group(2)

        title = _strip_html(content)

        if not title:
            continue

        url = _absolute(
            href,
            search_url,
        )

        if not url:
            continue

        candidates.append(
            {
                "title": title,
                "url": url,
            }
        )

    if not candidates:
        return None

    wanted = _normalize(name)

    # Exact match
    for candidate in candidates:

        current = _normalize(
            candidate["title"]
        )

        if current == wanted:
            return candidate["url"]

    # Contains match
    for candidate in candidates:

        current = _normalize(
            candidate["title"]
        )

        if (
            wanted in current
            or current in wanted
        ):
            return candidate["url"]

    # Token similarity
    wanted_words = set(
        wanted.split()
    )

    best_url = None
    best_score = 0

    for candidate in candidates:

        current = _normalize(
            candidate["title"]
        )

        current_words = set(
            current.split()
        )

        if not current_words:
            continue

        score = len(
            wanted_words & current_words
        )

        if score > best_score:
            best_score = score
            best_url = candidate["url"]

    if best_url:
        return best_url

    return candidates[0]["url"]


# ---------------------------------------------------------
# Episode extraction
# ---------------------------------------------------------

def get_episode_url(
    anime_url,
    episode_number,
):
    if not anime_url:
        return None

    try:
        target = int(
            episode_number
        )
    except Exception:
        return None

    status, body = _request(
        anime_url,
        referer=BASE_URL.rstrip("/") + "/",
    )

    if status != 200 or not body:
        return None

    # We specifically target anchors pointing
    # to /episodes/ pages.
    anchors = re.finditer(
        r'<a\b[^>]*href=["\']'
        r'([^"\']*/episodes/[^"\']*)'
        r'["\'][^>]*>'
        r'([\s\S]*?)'
        r'</a>',
        body,
        re.I,
    )

    for match in anchors:

        href = _clean(
            match.group(1)
        )

        content = match.group(2)

        visible_text = _strip_html(
            content
        )

        episode_match = re.search(
            r"(?:الحلقة|episode|ep\.?)"
            r"\s*0*(\d+)",
            visible_text,
            re.I,
        )

        if not episode_match:
            continue

        try:
            number = int(
                episode_match.group(1)
            )
        except Exception:
            continue

        if number == target:
            return _absolute(
                href,
                anime_url,
            )

    # Secondary fallback:
    # inspect every /episodes/ href and its nearby
    # HTML for the requested number.
    episode_slug = str(target).zfill(2)

    fallback = re.search(
        r'href=["\']'
        r'([^"\']*/episodes/[^"\']*'
        + re.escape(episode_slug)
        + r'[^"\']*)'
        r'["\']',
        body,
        re.I,
    )

    if fallback:
        return _absolute(
            fallback.group(1),
            anime_url,
        )

    return None


# ---------------------------------------------------------
# UPNS iframe
# ---------------------------------------------------------

def get_iframe_url(
    episode_url,
):
    if not episode_url:
        return None

    status, body = _request(
        episode_url,
        referer=BASE_URL.rstrip("/") + "/",
    )

    if status != 200 or not body:
        return None

    iframe_matches = re.finditer(
        r"<iframe\b"
        r"[^>]*\bsrc\s*=\s*"
        r"""["']([^"']+)["']""",
        body,
        re.I,
    )

    generic = []

    for match in iframe_matches:

        src = _absolute(
            match.group(1),
            episode_url,
        )

        if not src:
            continue

        generic.append(src)

        # Prefer the UPNS player we have already
        # confirmed contains the HLS source.
        if "upns.online" in src.lower():
            return src

    if generic:
        return generic[0]

    return None


# ---------------------------------------------------------
# M3U8 extraction
# ---------------------------------------------------------

def get_m3u8(
    iframe_url,
    episode_url,
):
    if not iframe_url:
        return None

    status, body = _request(
        iframe_url,
        referer=episode_url,
        origin=_origin(iframe_url),
    )

    if status != 200 or not body:
        return None

    # Decode HTML / escaped JavaScript.
    body = html.unescape(body)

    for old, new in (
        ("\\/", "/"),
        ("\\u0026", "&"),
        ("\\x26", "&"),
        ("\\u003d", "="),
        ("\\u003f", "?"),
    ):
        body = body.replace(
            old,
            new,
        )

    patterns = [

        # <source src="...m3u8">
        r'<source\b[^>]*\bsrc\s*=\s*'
        r"""["']([^"']+\.m3u8(?:\?[^"']*)?)["']""",

        # src="...m3u8"
        r'\bsrc\s*=\s*'
        r"""["']([^"']+\.m3u8(?:\?[^"']*)?)["']""",

        # quoted absolute URL
        r"""["'](https?://[^"'<>]+\.m3u8(?:\?[^"'<>]*)?)["']""",

        # unquoted absolute URL
        r"""(https?://[^\s"'<>]+\.m3u8(?:\?[^\s"'<>]*)?)""",

        # protocol-relative
        r"""(//[^\s"'<>]+\.m3u8(?:\?[^\s"'<>]*)?)""",

        # relative URL
        r"""["']([^"']*\.m3u8(?:\?[^"']*)?)["']""",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            body,
            re.I,
        )

        if not match:
            continue

        stream_url = _clean(
            match.group(1)
        )

        if not stream_url:
            continue

        if stream_url.startswith("//"):
            parsed = urllib.parse.urlparse(
                iframe_url
            )

            stream_url = (
                parsed.scheme
                + ":"
                + stream_url
            )

        stream_url = _absolute(
            stream_url,
            iframe_url,
        )

        if ".m3u8" in stream_url.lower():
            return stream_url

    return None


# ---------------------------------------------------------
# Full series resolver
# ---------------------------------------------------------

def series(
    imdb_id,
    season,
    episode,
):
    metadata = get_anime_metadata(
        imdb_id
    )

    if not metadata:
        return {}

    anime_name = metadata["name"]

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

    iframe_url = get_iframe_url(
        episode_url
    )

    if not iframe_url:
        return {}

    m3u8_url = get_m3u8(
        iframe_url,
        episode_url,
    )

    if not m3u8_url:
        return {}

    return {
        "url": m3u8_url,
        "User-Agent": USER_AGENT,
        "Referer": iframe_url,
        "Origin": _origin(
            iframe_url
        ),
    }


# ---------------------------------------------------------
# MegaSource entry point
# ---------------------------------------------------------

def get_streams(
    media_type,
    media_id,
    config=None,
):
    if media_type != "series":
        return []

    imdb_id, season, episode = (
        _parse_media_id(
            media_id
        )
    )

    if not imdb_id or not episode:
        return []

    try:
        episode_number = int(
            episode
        )
    except Exception:
        return []

    info = series(
        imdb_id,
        season or "1",
        episode_number,
    )

    if not info:
        return []

    stream_url = info.get(
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
