"""Bosch Smart Home cloud maintenance / outage discovery.

Bosch announces planned maintenance in the community board "Wartungsarbeiten"
and active incidents in "Statusmeldungen". Both boards expose RSS feeds; this
module fetches them, parses the latest items, and surfaces a single best-match
announcement so the UI can show a specific reason ("Bosch-Wartung 07:00–10:00
MESZ") instead of a generic "unavailable" state when the cloud returns 5xx.

There is no machine-readable status API from Bosch — the iOS app reaches the
same conclusion by interpreting a 503 from /v11/video_inputs as maintenance.
The community RSS feeds are the only durable, public, structured channel.

Failover layers:
  1. Try each known RSS feed URL in order; first 200 OK with parseable items wins.
  2. If every RSS URL fails (HTTP error, DNS, parse error), fall back to scraping
     the board's HTML landing page for embedded item metadata.
  3. If every fetch fails, return None — the caller keeps its previously cached
     value, so a transient outage of the *community* site does not destroy the
     status of the camera cloud.
  4. Parsing tolerates RSS 2.0, Atom, and a minimal HTML extractor — a layout
     refresh on the Khoros community platform should not break detection.
"""

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import unescape
import logging
import re
from typing import Any
from xml.etree.ElementTree import Element as _ETElement  # type annotation only
from zoneinfo import ZoneInfo

import aiohttp
from defusedxml import ElementTree as ET  # XXE-safe drop-in for xml.etree.ElementTree

_LOGGER = logging.getLogger(__name__)

_BERLIN = ZoneInfo("Europe/Berlin")

# Boards Bosch uses for service status. Order = preference; first success wins.
# "Wartungsarbeiten" = planned maintenance, "Statusmeldungen" = active incidents.
RSS_FEEDS: tuple[str, ...] = (
    "https://community.bosch-smarthome.com/edswj98253/rss/board?board.id=Wartungsarbeiten",
    "https://community.bosch-smarthome.com/edswj98253/rss/board?board.id=Statusmeldungen",
)
HTML_FALLBACKS: tuple[str, ...] = (
    "https://community.bosch-smarthome.com/t5/wartungsarbeiten/bg-p/Wartungsarbeiten",
    "https://community.bosch-smarthome.com/t5/statusmeldungen/bg-p/Statusmeldungen",
)
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Date: 19.05.2026 / 19.5.2026 / 19. 5. 2026
_DATE_RE = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d{2})")
# Time range: "07:00 und 10:00 Uhr (MESZ)", "von 07:00 bis 10:00 Uhr", "07:00 – 10:00 Uhr"
_TIME_RANGE_RE = re.compile(
    r"(\d{1,2}):(\d{2})\s*(?:Uhr\s*)?"
    r"(?:bis|und|–|-|—|to)\s*"
    r"(\d{1,2}):(\d{2})\s*Uhr"
    r"(?:\s*\(?(MESZ|MEZ|CEST|CET)\)?)?",
    re.IGNORECASE,
)
# Camera-relevant keywords (lower-case match against title + summary).
_CAMERA_KEYWORDS: tuple[str, ...] = (
    "kamera",
    "kameras",
    "camera",
    "cameras",
    "video",
    "videos",
    "videostream",
    "stream",
    "cbs",
    "cloud",
    "backend",
    "infrastruktur",
)
# Items older than this are treated as historical context, never "scheduled".
_MAX_AGE = timedelta(days=14)


@dataclass(frozen=True)
class MaintenanceWindow:
    """Parsed maintenance/incident announcement from a Bosch community feed."""

    title: str
    link: str
    pub_date: datetime
    summary: str
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    source: str  # "rss:Wartungsarbeiten", "html:Statusmeldungen", etc.
    camera_relevant: bool

    def state(self, now: datetime | None = None) -> str:
        """Return one of: 'active' / 'scheduled' / 'past' / 'recent' / 'unknown'.

        - active: now is inside [start, end]
        - scheduled: now is before start AND start is within MAX_AGE in the future
        - past: end is before now (we still keep the item for context)
        - recent: no parseable window but pub_date is within MAX_AGE
        - unknown: no window AND pub_date is old / unparseable
        """
        moment = now or datetime.now(tz=UTC)
        if self.scheduled_start is not None and self.scheduled_end is not None:
            if moment < self.scheduled_start:
                return (
                    "scheduled"
                    if (self.scheduled_start - moment) <= _MAX_AGE
                    else "unknown"
                )
            if moment > self.scheduled_end:
                return "past"
            return "active"
        if (moment - self.pub_date) <= _MAX_AGE:
            return "recent"
        return "unknown"

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "link": self.link,
            "pub_date": self.pub_date.isoformat(),
            "summary": self.summary,
            "scheduled_start": (
                self.scheduled_start.isoformat() if self.scheduled_start else None
            ),
            "scheduled_end": (
                self.scheduled_end.isoformat() if self.scheduled_end else None
            ),
            "source": self.source,
            "camera_relevant": self.camera_relevant,
        }


def _strip_html(html_text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html_text)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def _is_camera_relevant(title: str, summary: str) -> bool:
    haystack = f"{title}\n{summary}".lower()
    return any(kw in haystack for kw in _CAMERA_KEYWORDS)


def _parse_window(
    text: str,
    pub_date: datetime,
) -> tuple[datetime | None, datetime | None]:
    """Extract (start, end) datetimes from German announcement text.

    Strategy: find first DD.MM.YYYY date and first HH:MM–HH:MM range. If only
    the time range is found, fall back to the pub_date's date — useful when the
    title contains the date in a separate field and the body only has times.
    Returns (None, None) if neither yields a usable window.
    """
    date_m = _DATE_RE.search(text)
    range_m = _TIME_RANGE_RE.search(text)
    if not range_m:
        return (None, None)
    if date_m:
        day, mon, year = (
            int(date_m.group(1)),
            int(date_m.group(2)),
            int(date_m.group(3)),
        )
    else:
        # Fall back to the pub date in Berlin time.
        pub_local = pub_date.astimezone(_BERLIN)
        day, mon, year = pub_local.day, pub_local.month, pub_local.year
    h1, m1, h2, m2 = (int(range_m.group(i)) for i in (1, 2, 3, 4))
    try:
        start = datetime(year, mon, day, h1, m1, tzinfo=_BERLIN)
        end = datetime(year, mon, day, h2, m2, tzinfo=_BERLIN)
    except ValueError:
        _LOGGER.debug(
            "Maintenance: invalid date/time components in text: %r", text[:160]
        )
        return (None, None)
    if end <= start:
        end += timedelta(days=1)
    return (start.astimezone(UTC), end.astimezone(UTC))


def _parse_pub_date(raw: str) -> datetime:
    """RFC 822 (RSS) and ISO 8601 (Atom) parser, falling back to 'now'."""
    raw = raw.strip()
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            continue
    return datetime.now(tz=UTC)


def _items_from_rss(root: _ETElement) -> Iterable[dict[str, str]]:
    # RSS 2.0
    for item in root.findall(".//item"):
        yield {
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "pub": (item.findtext("pubDate") or "").strip(),
            "desc": item.findtext("description") or "",
        }
    # Atom
    atom_ns = {"a": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//a:entry", atom_ns):
        link_el = entry.find("a:link", atom_ns)
        link = link_el.attrib.get("href", "") if link_el is not None else ""
        yield {
            "title": (
                entry.findtext("a:title", default="", namespaces=atom_ns) or ""
            ).strip(),
            "link": link,
            "pub": (
                entry.findtext("a:updated", default="", namespaces=atom_ns)
                or entry.findtext("a:published", default="", namespaces=atom_ns)
                or ""
            ).strip(),
            "desc": entry.findtext("a:summary", default="", namespaces=atom_ns)
            or entry.findtext("a:content", default="", namespaces=atom_ns)
            or "",
        }


def _board_label(url: str) -> str:
    m = re.search(r"board\.id=([^&]+)", url) or re.search(r"/bg-p/([^/?#]+)", url)
    return m.group(1) if m else "unknown"


def _parse_feed_body(body: bytes, source_url: str) -> MaintenanceWindow | None:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        _LOGGER.debug("Maintenance: RSS/Atom parse error from %s: %s", source_url, exc)
        return None
    label = _board_label(source_url)
    best: MaintenanceWindow | None = None
    for raw in _items_from_rss(root):
        title = raw["title"]
        if not title:
            continue
        pub_date = _parse_pub_date(raw["pub"])
        summary = _strip_html(raw["desc"])
        start, end = _parse_window(f"{title} {summary}", pub_date)
        cam = _is_camera_relevant(title, summary)
        candidate = MaintenanceWindow(
            title=title,
            link=raw["link"],
            pub_date=pub_date,
            summary=summary[:500],
            scheduled_start=start,
            scheduled_end=end,
            source=f"rss:{label}",
            camera_relevant=cam,
        )
        if best is None or _prefers(candidate, best):
            best = candidate
    return best


def _parse_html_fallback(body: bytes, source_url: str) -> MaintenanceWindow | None:
    """Extract a single best-match item from the rendered Khoros board page.

    Khoros pages include an embedded JSON-LD blob and structured anchors; we
    use the first article title + permalink + the surrounding text snippet as
    our minimum viable bundle.
    """
    text = body.decode("utf-8", errors="replace")
    # Find the first item link: /t5/<board>/<slug>/ba-p/<id>
    link_m = re.search(
        r'href="(/t5/[^"]+/ba-p/\d+)"[^>]*>\s*([^<]{6,200})</a>',
        text,
    )
    if not link_m:
        return None
    href = "https://community.bosch-smarthome.com" + link_m.group(1)
    title = _strip_html(link_m.group(2))
    # Snippet: the meta description carries a useful summary.
    desc_m = re.search(
        r'<meta\s+name="description"\s+content="([^"]{20,500})"',
        text,
        re.IGNORECASE,
    )
    summary = _strip_html(desc_m.group(1)) if desc_m else ""
    pub_date = datetime.now(tz=UTC)
    start, end = _parse_window(f"{title} {summary}", pub_date)
    return MaintenanceWindow(
        title=title,
        link=href,
        pub_date=pub_date,
        summary=summary[:500],
        scheduled_start=start,
        scheduled_end=end,
        source=f"html:{_board_label(source_url)}",
        camera_relevant=_is_camera_relevant(title, summary),
    )


def _prefers(a: MaintenanceWindow, b: MaintenanceWindow) -> bool:
    """Return True if a should win over b.

    Order:
      1. Active window beats everything.
      2. Scheduled window in the future beats past/recent/unknown.
      3. Camera-relevant beats unrelated.
      4. Newer pub_date wins.
    """
    s_a, s_b = a.state(), b.state()
    rank = {"active": 0, "scheduled": 1, "recent": 2, "past": 3, "unknown": 4}
    if rank[s_a] != rank[s_b]:
        return rank[s_a] < rank[s_b]
    if a.camera_relevant != b.camera_relevant:
        return a.camera_relevant
    return a.pub_date > b.pub_date


async def _fetch_one(
    session: aiohttp.ClientSession,
    url: str,
    *,
    timeout_s: float,
) -> tuple[int, bytes] | None:
    try:
        async with asyncio.timeout(timeout_s):
            async with session.get(url, headers={"User-Agent": _BROWSER_UA}) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Maintenance HTTP %s for %s", resp.status, url)
                    return None
                return (resp.status, await resp.read())
    except (TimeoutError, aiohttp.ClientError) as exc:
        _LOGGER.debug("Maintenance fetch error for %s: %s", url, exc)
        return None


async def async_fetch_maintenance(
    session: aiohttp.ClientSession,
    *,
    timeout_s: float = 8.0,
) -> MaintenanceWindow | None:
    """Fetch and parse the best-match maintenance/incident announcement.

    Returns None only when ALL primary and fallback sources fail — the
    coordinator keeps the last cached value rather than flipping state on a
    transient miss of the community site.
    """
    best: MaintenanceWindow | None = None
    for url in RSS_FEEDS:
        got = await _fetch_one(session, url, timeout_s=timeout_s)
        if got is None:
            continue
        parsed = _parse_feed_body(got[1], url)
        if parsed and (best is None or _prefers(parsed, best)):
            best = parsed
    if best is not None:
        return best
    # Every RSS feed failed → try the HTML board pages.
    for url in HTML_FALLBACKS:
        got = await _fetch_one(session, url, timeout_s=timeout_s)
        if got is None:
            continue
        parsed = _parse_html_fallback(got[1], url)
        if parsed and (best is None or _prefers(parsed, best)):
            best = parsed
    return best
