"""Checker for translation placeholder keys.

Placeholder keys refer to the ``{name}`` placeholders in ``strings.json``,
not to config keys, so constants such as ``CONF_*`` should not be used.
Integrations that reuse a placeholder in many places can opt in to a
dedicated constant (``PLACEHOLDER_*``) or enum (``*Placeholder``).

Placeholder dicts are recognised by a name ending in ``placeholders``: a
keyword argument, an assignment target (variable, attribute or subscript such
as ``self.context["title_placeholders"]``) or a string key of another dict.

- ``C7459``: Placeholder key is a constant not dedicated to placeholders
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter


def _is_placeholder_name(name: object) -> bool:
    """Check if a name refers to a dict of translation placeholders."""
    return isinstance(name, str) and name.lower().endswith("placeholders")


def _target_name(target: nodes.NodeNG) -> object:
    """Return the name of an assignment target."""
    match target:
        case nodes.AssignName(name=name) | nodes.AssignAttr(attrname=name):
            return name
        case nodes.Subscript(slice=nodes.Const(value=value)):
            return value
    return None


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
            "Used when a key of a translation placeholder dict, such as "
            "description_placeholders, translation_placeholders or "
            "title_placeholders, is not a string literal. Placeholder keys "
            "belong to the translation string, so constants such as CONF_* "
            "should not be used. Use a PLACEHOLDER_* constant or a "
            "*Placeholder enum when a dedicated constant is needed.",
        ),
    }
    options = ()

    def visit_call(self, node: nodes.Call) -> None:
        """Check placeholder dicts passed as keyword arguments."""
        for keyword in node.keywords:
            if _is_placeholder_name(keyword.arg):
                self._check_placeholders(keyword.value)

    def visit_assign(self, node: nodes.Assign) -> None:
        """Check placeholder dicts assigned to a placeholder target."""
        if any(_is_placeholder_name(_target_name(t)) for t in node.targets):
            self._check_placeholders(node.value)

    def visit_annassign(self, node: nodes.AnnAssign) -> None:
        """Check placeholder dicts assigned to an annotated placeholder target."""
        if node.value is not None and _is_placeholder_name(_target_name(node.target)):
            self._check_placeholders(node.value)

    def visit_dict(self, node: nodes.Dict) -> None:
        """Check placeholder dicts nested under a placeholder key."""
        for key, value in node.items:
            if isinstance(key, nodes.Const) and _is_placeholder_name(key.value):
                self._check_placeholders(value)

    def _check_placeholders(self, node: nodes.NodeNG) -> None:
        """Report constant keys in a placeholder dict literal."""
        if not isinstance(node, nodes.Dict):
            return
        if any(
            isinstance(value, nodes.Dict) and not isinstance(key, nodes.DictUnpack)
            for key, value in node.items
        ):
            # A mapping of placeholder dicts, keyed by translation key
            for _, value in node.items:
                self._check_placeholders(value)
            return
        for key, _ in node.items:
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
