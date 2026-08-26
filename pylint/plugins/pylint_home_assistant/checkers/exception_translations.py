"""Checker for HomeAssistantError translation usage.

Ensures that ``HomeAssistantError`` and its subclasses use the translation
system (``translation_domain``, ``translation_key``) instead of hardcoded
English strings. Also verifies that referenced translation keys exist in
the integration's ``strings.json`` and that placeholders match.

- ``W7417``: Hardcoded string instead of translations (quality-scale-gated)
- ``W7419``: Both a message string and ``translation_key`` provided
- ``E7406``: Translation key not found in ``strings.json``
- ``E7408``: Only one of ``translation_key``/``translation_domain`` provided
- ``E7418``: Placeholder mismatch between code and ``strings.json``
"""

from pathlib import Path

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.integration import get_integration_dir
from pylint_home_assistant.helpers.module_info import parse_module
from pylint_home_assistant.helpers.quality_scale import quality_scale_rule_is_done
from pylint_home_assistant.helpers.translations import (
    extract_placeholder_keys,
    get_exception_translations,
    get_exception_translations_for_domain,
    get_message_placeholders,
)

_HA_ERROR_QNAME = "homeassistant.exceptions.HomeAssistantError"


def _accepts_translation_key(class_node: nodes.ClassDef) -> bool:
    """Check if a class accepts translation_key in its constructor.

    If the class overrides ``__init__`` without a ``translation_key``
    parameter (and without ``**kwargs``), it doesn't support the
    translation system.
    """
    for method in class_node.mymethods():
        if method.name != "__init__":
            continue
        # Class has its own __init__, check if it accepts translation_key
        if method.args.kwarg:
            return True
        return any(
            arg.name == "translation_key"
            for arg in method.args.args + method.args.kwonlyargs
        )
    # No __init__ override, inherits from parent (HomeAssistantError accepts it)
    return True


def _is_ha_exception(call: nodes.Call) -> str | None:
    """Check if a call constructs a HomeAssistantError subclass that supports translations.

    Returns the class name if it is, None otherwise.
    """
    try:
        for inferred in call.func.infer():
            if not isinstance(inferred, nodes.ClassDef):
                continue
            is_ha = inferred.qname() == _HA_ERROR_QNAME
            if not is_ha:
                try:
                    is_ha = any(
                        a.qname() == _HA_ERROR_QNAME for a in inferred.ancestors()
                    )
                except astroid.exceptions.InferenceError:
                    continue
            if is_ha and _accepts_translation_key(inferred):
                return str(inferred.name)
    except astroid.exceptions.InferenceError:
        pass
    return None


def _get_keyword_value(call: nodes.Call, name: str) -> nodes.NodeNG | None:
    """Get the value of a keyword argument from a Call node."""
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _extract_const_string(node: nodes.NodeNG | None) -> str | None:
    """Extract a constant string value from a node."""
    if isinstance(node, nodes.Const) and isinstance(node.value, str):
        return node.value
    return None


class ExceptionTranslationsChecker(BaseChecker):
    """Checker for HomeAssistantError translation usage."""

    name = "home_assistant_exception_translations"
    priority = -1
    msgs = {
        "W7417": (
            "%s should use translation_domain and translation_key",
            "home-assistant-exception-not-translated",
            "Used when a HomeAssistantError subclass is raised without "
            "using the translation system.",
        ),
        "E7406": (
            "Translation key '%s' not found in exceptions section of "
            "strings.json for domain '%s'",
            "home-assistant-exception-translation-key-missing",
            "Used when a HomeAssistantError references a translation_key "
            "that does not exist in the integration's strings.json.",
        ),
        "W7419": (
            "%s should not pass positional arguments when translation_key is set",
            "home-assistant-exception-message-with-translation",
            "Used when a HomeAssistantError subclass passes both "
            "positional arguments and a translation_key. The translation "
            "system generates the message from the key.",
        ),
        "E7408": (
            "%s must set both translation_key and translation_domain, "
            "but only one is provided",
            "home-assistant-exception-translation-key-domain-mismatch",
            "Used when a HomeAssistantError subclass sets translation_key "
            "without translation_domain or vice versa. Both are required "
            "for the translation system to generate the exception message.",
        ),
        "E7418": (
            "Placeholder mismatch for translation key '%s': "
            "code passes {%s} but strings.json expects {%s}",
            "home-assistant-exception-placeholder-mismatch",
            "Used when the translation_placeholders in code don't match "
            "the placeholders in the strings.json message template.",
        ),
    }
    options = ()

    _in_integration: bool
    _module_node: nodes.Module | None
    _domain: str | None
    _components_dir: Path | None
    _exception_translations_done: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Load integration context."""
        parsed = parse_module(node.name)
        self._in_integration = parsed is not None
        self._module_node = node if parsed else None
        self._domain = parsed.domain if parsed else None
        integration_dir = get_integration_dir(node) if parsed else None
        self._components_dir = integration_dir.parent if integration_dir else None
        self._exception_translations_done = (
            parsed is not None
            and quality_scale_rule_is_done(node, "exception-translations")
        )

    def visit_call(self, node: nodes.Call) -> None:
        """Check HomeAssistantError raises for translation usage."""
        if not self._in_integration or self._module_node is None:
            return

        # Must be inside a raise statement
        if not isinstance(node.parent, nodes.Raise):
            return

        exc_name = _is_ha_exception(node)
        if exc_name is None:
            return

        translation_key_node = _get_keyword_value(node, "translation_key")
        has_translation_key = translation_key_node is not None
        translation_key = _extract_const_string(translation_key_node)

        # Resolve domain presence
        domain_node = _get_keyword_value(node, "translation_domain")
        has_translation_domain = domain_node is not None

        # Case 1: Only one of translation_key/translation_domain provided
        if has_translation_key != has_translation_domain:
            self.add_message(
                "home-assistant-exception-translation-key-domain-mismatch",
                node=node,
                args=(exc_name,),
            )
            return

        # Case 2: No translation_key at all (either hardcoded string or bare raise)
        # Only enforced when quality scale rule exception-translations is done
        if not has_translation_key:
            if self._exception_translations_done:
                self.add_message(
                    "home-assistant-exception-not-translated",
                    node=node,
                    args=(exc_name,),
                )
            return

        # Case 3: Both message and translation_key (message overrides translation)
        if node.args and has_translation_key:
            self.add_message(
                "home-assistant-exception-message-with-translation",
                node=node,
                args=(exc_name,),
            )
            return

        # If no translation key or non-literal key, skip further checks
        if translation_key is None:
            return

        # Resolve the domain value
        translation_domain = _extract_const_string(domain_node)
        if translation_domain is None:
            # Try resolving DOMAIN constant
            if isinstance(domain_node, nodes.Name) and domain_node.name == "DOMAIN":
                translation_domain = self._domain

        if translation_domain is None:
            # Non-literal domain (variable, attribute), can't check further
            return

        # Load translations for the target domain (may differ from current module)
        if translation_domain == self._domain:
            exception_translations = get_exception_translations(self._module_node)
        else:
            exception_translations = get_exception_translations_for_domain(
                self._module_node, translation_domain
            )

        # Case 3: Check translation key exists
        if translation_key not in exception_translations:
            self.add_message(
                "home-assistant-exception-translation-key-missing",
                node=node,
                args=(translation_key, translation_domain),
            )
            return

        # Case 4: Check placeholder mismatch
        entry = exception_translations[translation_key]
        message = entry.get("message", "")
        expected = get_message_placeholders(message, self._components_dir)

        placeholder_node = _get_keyword_value(node, "translation_placeholders")

        if placeholder_node is None:
            if not expected:
                # No placeholders expected and none provided
                return
            # No translation_placeholders keyword but strings.json expects some
            code_placeholders: set[str] = set()
        else:
            code_placeholders_or_none = extract_placeholder_keys(placeholder_node)
            if code_placeholders_or_none is None:
                # Non-literal (variable, attribute, etc.), can't check
                return
            code_placeholders = code_placeholders_or_none

        if code_placeholders != expected:
            self.add_message(
                "home-assistant-exception-placeholder-mismatch",
                node=node,
                args=(
                    translation_key,
                    ", ".join(sorted(code_placeholders)) or "(none)",
                    ", ".join(sorted(expected)) or "(none)",
                ),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ExceptionTranslationsChecker(linter))
