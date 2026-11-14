"""Release note parsing for the Home Assistant Upgrade Check integration.

Stand-in for release metadata published next to the release notes, like the
alerts feed: until then, core parses the posts' markdown source itself.
"""

from collections.abc import Iterable
import re
from typing import Any

# 2026-11-04-release-202611.markdown is /blog/2026/11/04/release-202611/.
POST_FILE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})-(release-(\d{4})(\d{1,2}))\.markdown$"
)
# Every reference-style link definition pointing at an integration page.
# Platform pages such as /integrations/sensor.rest/ belong to the part after the dot.
LINKDEF = re.compile(
    r"^\[([^\]]+)\]:\s*/integrations/(?:[a-z0-9_]+\.)?([a-z0-9_]+)", re.MULTILINE
)
INLINE = re.compile(r"\]\(/integrations/(?:[a-z0-9_]+\.)?([a-z0-9_]+)")
# Pre-2026 posts link the docs inline: ([documentation](/integrations/x))
INLINE_DOC = re.compile(r"\(\[documentation\]\(/integrations/([a-z0-9_]+)")
ANY_LINKDEF = re.compile(r"^\[([^\]]+)\]:\s*(\S+)\s*$", re.MULTILINE)
SITE = "https://www.home-assistant.io"
# Bump when the shape of an index changes, so cached indexes are rebuilt.
INDEX_FORMAT = 6
LIQUID = re.compile(r"{%\s*(\w+)\s*(.*?)\s*%}")
QUOTED_OR_WORD = re.compile(r'"([^"]*)"|(\S+)')


def _liquid(m: re.Match[str]) -> str:
    """Replace a Liquid tag with the text it renders on the website."""
    tag, args = m.group(1), m.group(2)
    if tag == "term":
        # {% term entity %}, {% term "binary sensor" "binary sensors" %}: last arg shows.
        words = [a or b for a, b in QUOTED_OR_WORD.findall(args)]
        return words[-1] if words else ""
    if tag == "my":
        title = re.search(r'title="([^"]*)"', args)
        return title.group(1) if title else ""
    # icon, tip/note wrappers, raw: drop the tag, keep any content between.
    return ""


def clean(text: str, links: dict[str, str]) -> str:
    """Turn a release-note fragment into plain markdown that renders anywhere."""
    text = ANY_LINKDEF.sub("", text)
    # Credit lines: ([@user] - [#123]) ([X documentation])
    text = re.sub(r"^\(\[@.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*Thanks, \[@[^!]*!", "", text)
    text = LIQUID.sub(_liquid, text)
    text = re.sub(r"<abbr [^>]*>([^<]*)</abbr>", r"\1", text)
    # Reference links lose their definitions above; inline them.
    text = re.sub(
        r"\[([^\]]+)\](?![(:\]])",
        lambda m: (
            f"[{m.group(1)}]({links[m.group(1)]})"
            if m.group(1) in links
            else m.group(0)
        ),
        text,
    )
    text = re.sub(r"\]\((/[^)]*)\)", rf"]({SITE}\1)", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_version(value: str) -> tuple[int, int]:
    """Reduce 2026.9 or 2026.9.2 to (year, month); patch releases share the post."""
    year, month = value.split(".")[:2]
    return int(year), int(month)


def release_posts(
    names: Iterable[str], after: tuple[int, int], upto: tuple[int, int]
) -> list[tuple[str, str, str]]:
    """Release posts after the running and up to the target release, oldest first.

    Each is the release's version, the post's file name and its URL on the website.
    """
    found = []
    for name in names:
        if not (m := POST_FILE.match(name)):
            continue
        year, month, day, slug, release_year, release_month = m.groups()
        release = (int(release_year), int(release_month))
        if after < release <= upto:
            url = f"{SITE}/blog/{year}/{month}/{day}/{slug}/"
            found.append((release, name, url))
    return [(f"{y}.{mo}", name, url) for (y, mo), name, url in sorted(found)]


def index_post(post: str, version: str, url: str) -> dict[str, Any]:
    """Turn one release post into a per-domain index."""
    names = dict(LINKDEF.findall(post))
    links = {
        name: SITE + url if url.startswith("/") else url
        for name, url in ANY_LINKDEF.findall(post)
    }

    def section(heading: str) -> str:
        """Body of a section up to the next heading of the same or higher level."""
        if not (m := re.search(rf"^(#+) {re.escape(heading)}\s*$", post, re.MULTILINE)):
            return ""
        rest = post[m.end() :]
        end = re.search(rf"^#{{1,{len(m.group(1))}}} ", rest, re.MULTILINE)
        return rest[: end.start()] if end else rest

    def bullets(body: str) -> list[str]:
        """Top-level list items, each with its continuation lines."""
        return [b for b in re.split(r"\n(?=- )", body) if b.startswith("- ")]

    def refs(text: str) -> list[str]:
        """Domains referenced as [Name] or inline links, in order, de-duplicated."""
        found = [
            names[n] for n in re.findall(r"\[([^\]@#]+)\](?![:(])", text) if n in names
        ]
        found += INLINE.findall(text)
        return list(dict.fromkeys(found))

    def title(bullet: str) -> str:
        """The bold name a list item starts with, such as **[MQTT]**."""
        m = re.match(r"- \*\*\[?([^\]*]+)", bullet)
        return m.group(1) if m else bullet[2:60]

    index: dict[str, Any] = {
        "version": version,
        "url": url,
        "breaking": [],
        "noteworthy": [],
        "quality_scale": [],
        "removed": [],
    }

    for b in bullets(section("Noteworthy improvements to existing integrations")):
        d = refs(b)
        # First link is the subject; others are only mentioned.
        index["noteworthy"].append(
            {
                "title": title(b),
                "domains": d[:1],
                "mentions": d[1:],
                "text": clean(b[2:], links),
            }
        )

    tier = None
    for line in section("Integration quality scale achievements").splitlines():
        if m := re.match(r"- \*\*\d+ integrations? reached (\w+)", line):
            # A key, not display text; the frontend translates it.
            tier = m.group(1).lower()
        elif tier and (m := re.match(r"\s+- \[([^\]]+)\]", line)):
            index["quality_scale"].append(
                {
                    "title": m.group(1),
                    "domains": refs(line),
                    "tier": tier,
                    # "[X], thanks to [@a] and [@b]": GitHub usernames.
                    "credits": re.findall(r"\[@([^\]]+)\]", line),
                }
            )

    # Removed integrations have no docs page left to link to, so their domain
    # is guessed from the name; published metadata would carry the real one.
    removed: dict[str, str] = {}
    for b in bullets(section("Farewell to the following")):
        # The links in the bullet point to replacements, not to what was removed.
        name = title(b)
        removed[name] = re.sub(r"\W+", "_", name.lower()).strip("_")
        index["removed"].append(
            {
                "title": name,
                "domains": [removed[name]],
                "replacements": refs(b),
                "text": clean(b[2:], links),
            }
        )

    for m in re.finditer(
        r'{% details "([^"]+)" %}(.*?){% enddetails %}',
        section("Backward-incompatible changes"),
        re.DOTALL,
    ):
        block_title, body = m.groups()
        # "[x docs]" is what hass-release generates; "[X documentation]" is hand-written.
        # Some posts define these links after the block, so resolve post-wide.
        doc = [
            names[n]
            for n in re.findall(r"\[([^\]]+)\]", body)
            if n.endswith((" documentation", " docs")) and n in names
        ]
        doc = list(dict.fromkeys(doc + INLINE_DOC.findall(body)))
        # Some blocks have no doc link; the title is often the integration's name.
        if not doc and (by_title := names.get(block_title) or removed.get(block_title)):
            doc = [by_title]
        prs = re.findall(r"\[#(\d+)\]:", body) + re.findall(r"\[(\w+#\d+)\]:", body)
        index["breaking"].append(
            {
                "title": block_title,
                "domains": doc,
                "mentions": [d for d in refs(body) if d not in doc],
                "global": not doc,
                "text": clean(body, links),
                "prs": prs,
            }
        )

    return index
