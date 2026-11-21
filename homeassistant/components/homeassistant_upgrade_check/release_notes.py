"""Release note parsing for the Home Assistant Upgrade Check integration.

Stand-in for release notes published as JSON next to the posts, like the alerts
feed: until then, core turns the posts' markdown source into that same format.
"""

from collections.abc import Iterable
import re
from typing import Any

# Format of the release notes JSON; consumers skip categories they do not know.
FORMAT = 1
# Bump when the parser's output changes, so cached releases are parsed again.
INDEX_FORMAT = 9
CATEGORIES = ("breaking", "noteworthy", "quality_scale", "removed")

# 2026-11-04-release-202611.markdown is /blog/2026/11/04/release-202611/.
POST_FILE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})-(release-(\d{4})(\d{1,2}))\.markdown$"
)
# Every reference-style link definition pointing at an integration page.
# Platform pages such as /integrations/sensor.rest/ belong to the part after the dot.
LINKDEF = re.compile(
    r"^\[([^\]]+)\]:\s*/integrations/(?:[a-z0-9_]+\.)?([a-z0-9_]+)", re.MULTILINE
)
# A reference-style link in the text, such as [Philips Hue].
REFERENCE = re.compile(r"\[([^\]@#]+)\](?![:(])")
INLINE = re.compile(r"\]\(/integrations/(?:[a-z0-9_]+\.)?([a-z0-9_]+)")
# Pre-2026 posts link the docs inline: ([documentation](/integrations/x))
INLINE_DOC = re.compile(r"\(\[documentation\]\(/integrations/([a-z0-9_]+)")
ANY_LINKDEF = re.compile(r"^\[([^\]]+)\]:\s*(\S+)\s*$", re.MULTILINE)
# [@user] credits and [#123] or [frontend#123] pull requests.
AUTHOR = re.compile(r"\[@([^\]]+)\]")
PR = re.compile(r"\[(\w*)#(\d+)\]")
SITE = "https://www.home-assistant.io"
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


def summary(text: str) -> str:
    """Return the first sentence of cleaned markdown as one plain line."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\*\*|`", "", text)
    text = " ".join(text.split())
    m = re.match(r"(.+?[.!?])(?:\s|$)", text)
    return m.group(1) if m else text


def parse_version(value: str) -> tuple[int, int]:
    """Reduce 2026.9 or 2026.9.2 to (year, month); patch releases share the post."""
    year, month = value.split(".")[:2]
    return int(year), int(month)


def post_index(names: Iterable[str], notes_url: str) -> list[dict[str, str]]:
    """Return the releases index for the release posts among file names.

    Each release's notes are its post's markdown, at notes_url with the file name.
    """
    found = []
    for name in names:
        if not (m := POST_FILE.match(name)):
            continue
        year, month, day, slug, release_year, release_month = m.groups()
        found.append(
            (
                (int(release_year), int(release_month)),
                {
                    "version": f"{int(release_year)}.{int(release_month)}",
                    "released": f"{year}-{month}-{day}",
                    "url": f"{SITE}/blog/{year}/{month}/{day}/{slug}/",
                    "notes": notes_url.format(name=name),
                },
            )
        )
    return [release for _, release in sorted(found, key=lambda f: f[0])]


def releases_between(
    index: list[dict[str, Any]], after: tuple[int, int], upto: tuple[int, int]
) -> list[dict[str, Any]]:
    """Releases of an index after the running and up to the target, oldest first."""
    return sorted(
        (r for r in index if after < parse_version(r["version"]) <= upto),
        key=lambda r: parse_version(r["version"]),
    )


def _slug(text: str) -> str:
    """Reduce a title to the characters an item ID allows."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _prs(text: str) -> list[dict[str, Any]]:
    """Pull requests credited in a fragment, in order, de-duplicated."""
    return [
        {"repo": repo or "core", "number": int(number)}
        for repo, number in dict.fromkeys(PR.findall(text))
    ]


def parse_release(post: str, release: dict[str, Any]) -> dict[str, Any]:
    """Turn one release post into its release notes, given its index entry."""
    names = dict(LINKDEF.findall(post))
    links = {
        name: SITE + url if url.startswith("/") else url
        for name, url in ANY_LINKDEF.findall(post)
    }
    since = f"{release['version']}.0"

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
        # Both kinds of link can be mixed; the first one is the subject.
        found = [
            (m.start(), names[m.group(1)])
            for m in REFERENCE.finditer(text)
            if m.group(1) in names
        ]
        found += [(m.start(), m.group(1)) for m in INLINE.finditer(text)]
        return list(dict.fromkeys(domain for _, domain in sorted(found)))

    def title(bullet: str) -> str:
        """The bold name a list item starts with, such as **[MQTT]**."""
        m = re.match(r"- \*\*\[?([^\]*]+)", bullet)
        return m.group(1) if m else bullet[2:60]

    items: list[dict[str, Any]] = []
    ids: set[str] = set()

    def add(item_id: str, category: str, **fields: Any) -> None:
        """Add an item; IDs are unique within a release."""
        unique, n = item_id, 1
        while unique in ids:
            n += 1
            unique = f"{item_id}-{n}"
        ids.add(unique)
        if text := fields.get("text"):
            fields["summary"] = summary(text)
        items.append({"id": unique, "category": category, "since": since, **fields})

    # Removed integrations have no docs page left to link to, so their domain
    # is guessed from the name; published release notes carry the real one.
    removed: dict[str, str] = {}
    for b in bullets(section("Farewell to the following")):
        removed[title(b)] = re.sub(r"\W+", "_", title(b).lower()).strip("_")

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
        prs = _prs(body)
        add(
            f"{prs[0]['repo']}-{prs[0]['number']}"
            if prs
            else f"breaking-{_slug(block_title)}",
            "breaking",
            title=block_title,
            domains=doc,
            mentions=[d for d in refs(body) if d not in doc],
            # Without a docs page the subject is unknown: it concerns everyone.
            scope="integration" if doc else "system",
            text=clean(body, links),
            prs=prs,
            authors=list(dict.fromkeys(AUTHOR.findall(body))),
        )

    for b in bullets(section("Noteworthy improvements to existing integrations")):
        d = refs(b)
        # First link is the subject; others are only mentioned.
        add(
            f"noteworthy-{d[0] if d else _slug(title(b))}",
            "noteworthy",
            title=title(b),
            domains=d[:1],
            mentions=d[1:],
            scope="integration",
            text=clean(b[2:], links),
            prs=_prs(b),
            authors=list(dict.fromkeys(AUTHOR.findall(b))),
        )

    tier = None
    for line in section("Integration quality scale achievements").splitlines():
        if heading := re.match(r"- \*\*\d+ integrations? reached (\w+)", line):
            # A key, not display text; the frontend translates it.
            tier = heading.group(1).lower()
        elif tier and (entry := re.match(r"\s+- \[([^\]]+)\]", line)):
            d = refs(line)
            add(
                f"quality-scale-{d[0] if d else _slug(entry.group(1))}-{tier}",
                "quality_scale",
                title=entry.group(1),
                domains=d,
                scope="integration",
                tier=tier,
                # "[X], thanks to [@a] and [@b]": GitHub usernames.
                authors=AUTHOR.findall(line),
            )

    for b in bullets(section("Farewell to the following")):
        name = title(b)
        add(
            f"removed-{removed[name]}",
            "removed",
            title=name,
            domains=[removed[name]],
            scope="integration",
            # The links in the bullet point to replacements, not to what was removed.
            replaced_by=refs(b),
            text=clean(b[2:], links),
        )

    return {
        "format": FORMAT,
        "version": release["version"],
        "released": release["released"],
        "url": release["url"],
        "items": items,
    }
