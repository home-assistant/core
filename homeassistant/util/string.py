"""String related helper methods for various modules."""
from __future__ import annotations

import slugify as unicode_slug


def slugify(text: str | None, *, separator: str = "_") -> str:
    """Slugify a given text."""
    if text == "" or text is None:
        return ""
    slug = unicode_slug.slugify(text, separator=separator)
    return "unknown" if slug == "" else slug
