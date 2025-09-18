"""Jinja2 extension for regular expression functions."""

from __future__ import annotations

from functools import lru_cache
import re
from typing import TYPE_CHECKING, Any

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment

# Module-level regex cache shared across all instances
_regex_cache = lru_cache(maxsize=128)(re.compile)


class RegexExtension(BaseTemplateExtension):
    """Jinja2 extension for regular expression functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the regex extension."""

        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "regex_match",
                    self.regex_match,
                    as_filter=True,
                ),
                TemplateFunction(
                    "regex_search",
                    self.regex_search,
                    as_filter=True,
                ),
                # Register tests with different names
                TemplateFunction(
                    "match",
                    self.regex_match,
                    as_test=True,
                ),
                TemplateFunction(
                    "search",
                    self.regex_search,
                    as_test=True,
                ),
                TemplateFunction(
                    "regex_replace",
                    self.regex_replace,
                    as_filter=True,
                ),
                TemplateFunction(
                    "regex_findall",
                    self.regex_findall,
                    as_filter=True,
                ),
                TemplateFunction(
                    "regex_findall_index",
                    self.regex_findall_index,
                    as_filter=True,
                ),
            ],
        )

    def regex_match(self, value: Any, find: str = "", ignorecase: bool = False) -> bool:
        """Match value using regex."""
        if not isinstance(value, str):
            value = str(value)
        flags = re.IGNORECASE if ignorecase else 0
        return bool(_regex_cache(find, flags).match(value))

    def regex_replace(
        self,
        value: Any = "",
        find: str = "",
        replace: str = "",
        ignorecase: bool = False,
    ) -> str:
        """Replace using regex."""
        if not isinstance(value, str):
            value = str(value)
        flags = re.IGNORECASE if ignorecase else 0
        result = _regex_cache(find, flags).sub(replace, value)
        return str(result)

    def regex_search(
        self, value: Any, find: str = "", ignorecase: bool = False
    ) -> bool:
        """Search using regex."""
        if not isinstance(value, str):
            value = str(value)
        flags = re.IGNORECASE if ignorecase else 0
        return bool(_regex_cache(find, flags).search(value))

    def regex_findall_index(
        self, value: Any, find: str = "", index: int = 0, ignorecase: bool = False
    ) -> str:
        """Find all matches using regex and then pick specific match index."""
        return self.regex_findall(value, find, ignorecase)[index]

    def regex_findall(
        self, value: Any, find: str = "", ignorecase: bool = False
    ) -> list[str]:
        """Find all matches using regex."""
        if not isinstance(value, str):
            value = str(value)
        flags = re.IGNORECASE if ignorecase else 0
        return _regex_cache(find, flags).findall(value)
