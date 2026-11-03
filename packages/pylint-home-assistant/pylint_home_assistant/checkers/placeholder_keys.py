"""Checker for translation placeholder keys.

Placeholder keys refer to the ``{name}`` placeholders in ``strings.json``,
not to config keys, so constants such as ``CONF_*`` should not be used.
Integrations that reuse a placeholder in many places can opt in to a
dedicated constant (``PLACEHOLDER_*``) or enum (``*Placeholder``).

- ``C7459``: Placeholder key is a constant not dedicated to placeholders
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

_PLACEHOLDER_KEYWORDS = {"description_placeholders", "translation_placeholders"}


def _is_invalid_key(key: nodes.NodeNG) -> bool:
    """Check if a placeholder key is a constant not dedicated to placeholders."""
    match key:
        case nodes.Name(name=name):
            return name.isupper() and not name.startswith("PLACEHOLDER_")
        case nodes.Attribute(attrname=str() as attrname, expr=expr):
            # Enum members are allowed on a dedicated *Placeholder enum
            if isinstance(expr, nodes.Name) and expr.name.endswith("Placeholder"):
                return False
            return attrname.isupper()
    return False


class PlaceholderKeysChecker(BaseChecker):
    """Checker for translation placeholder keys."""

    name = "home_assistant_placeholder_keys"
    priority = -1
    msgs = {
        "C7459": (
            "Placeholder key %s should be a string literal",
            "home-assistant-placeholder-key",
            "Used when a description_placeholders or translation_placeholders "
            "key is not a string literal. Placeholder keys belong to the "
            "translation string, so constants such as CONF_* should not be "
            "used. Use a PLACEHOLDER_* constant or a *Placeholder enum when "
            "a dedicated constant is needed.",
        ),
    }
    options = ()

    def visit_call(self, node: nodes.Call) -> None:
        """Check placeholder dicts passed to a call."""
        for keyword in node.keywords:
            if keyword.arg not in _PLACEHOLDER_KEYWORDS:
                continue
            if not isinstance(keyword.value, nodes.Dict):
                continue
            for key, _ in keyword.value.items:
                if not _is_invalid_key(key):
                    continue
                self.add_message(
                    "home-assistant-placeholder-key",
                    node=key,
                    args=(key.as_string(),),
                )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(PlaceholderKeysChecker(linter))
