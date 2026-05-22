"""Checker for invalid MDI icon references.

Validates that ``mdi:`` icon references in integration code and
``icons.json`` files refer to icons that actually exist in the
Material Design Icons set.

- ``E7409``: MDI icon reference not found in Python code
- ``E7410``: MDI icon reference not found in icons.json
"""

import re

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.generated.mdi_icons import MDI_ICONS
from pylint_home_assistant.helpers.icons import collect_mdi_icons, load_icons
from pylint_home_assistant.helpers.module_info import parse_module

# Matches strings that look like intentional icon name attempts
# (letters, digits, hyphens, underscores). Rejects format templates
# (%s, {}, {name}), empty names, and other dynamic patterns.
_LOOKS_LIKE_ICON_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*[a-zA-Z0-9]$")


class MdiIconsChecker(BaseChecker):
    """Checker for invalid MDI icon references."""

    name = "home_assistant_mdi_icons"
    priority = -1
    msgs = {
        "E7409": (
            "MDI icon '%s' does not exist in the Material Design Icons set",
            "home-assistant-mdi-icon-not-found",
            "Used when an integration references an MDI icon in Python "
            "code that does not exist. Check the icon name at "
            "https://pictogrammers.com/library/mdi/",
        ),
        "E7410": (
            "MDI icon '%s' in icons.json does not exist in the "
            "Material Design Icons set",
            "home-assistant-mdi-icon-json-not-found",
            "Used when an integration's icons.json references an MDI "
            "icon that does not exist. Check the icon name at "
            "https://pictogrammers.com/library/mdi/",
        ),
    }
    options = ()

    _in_integration: bool
    _checked_icons_json: set[str]

    def open(self) -> None:
        """Initialize per-run state."""
        self._checked_icons_json = set()

    def visit_module(self, node: nodes.Module) -> None:
        """Check icons.json and track integration context."""
        parsed = parse_module(node.name)
        self._in_integration = parsed is not None
        if parsed is None:
            return

        # Only check icons.json once per integration
        if parsed.domain in self._checked_icons_json:
            return
        self._checked_icons_json.add(parsed.domain)

        icons_data = load_icons(node)
        if icons_data is None:
            return

        mdi_refs = collect_mdi_icons(icons_data)
        for icon_ref in sorted(mdi_refs):
            icon_name = icon_ref[4:]  # Strip "mdi:" prefix
            if icon_name not in MDI_ICONS:
                self.add_message(
                    "home-assistant-mdi-icon-json-not-found",
                    node=node,
                    args=(icon_ref,),
                )

    def visit_const(self, node: nodes.Const) -> None:
        """Check string constants for invalid MDI icon references."""
        if not self._in_integration:
            return

        if not isinstance(node.value, str):
            return

        if not node.value.startswith("mdi:"):
            return

        icon_name = node.value[4:]  # Strip "mdi:" prefix

        # Only check names that look like intentional icon name attempts.
        # This skips f-string fragments, format templates (%s, {}),
        # partial names, and other dynamic patterns.
        if not _LOOKS_LIKE_ICON_NAME.match(icon_name):
            return

        if icon_name not in MDI_ICONS:
            self.add_message(
                "home-assistant-mdi-icon-not-found",
                node=node,
                args=(node.value,),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(MdiIconsChecker(linter))
