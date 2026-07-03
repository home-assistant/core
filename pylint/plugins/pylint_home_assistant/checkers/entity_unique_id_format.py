"""Checker for entity unique-ID value-format antipatterns.

Hosts format-related checks on the value an entity uses for its unique
ID (``_attr_unique_id`` assignments and ``unique_id`` property/method
returns). Migrating unique_ids after an integration has shipped risks
disrupting existing users, so these checks are **not** gated on
``quality_scale.yaml`` claims. Both checks inspect every class
inheriting from ``Entity`` in their respective scopes (including
shared bases and mixins/abstract bases subclassed by other classes in
the same module); see the per-rule sections below for the module
scope.

``W7425`` (``home-assistant-entity-unique-id-redundant-domain``)
----------------------------------------------------------------
The entity registry keys uniqueness on ``(domain, platform, unique_id)``
where ``platform`` is the integration's name (as declared by the
``"domain"`` field in ``manifest.json``). Any occurrence of the
integration's name in the unique_id duplicates information already
present in the registry key. The rule fires in every integration
module (entity-platform modules, ``entity.py``, ``__init__.py``, ...)
when the value used for the entity's unique id either:

- references the ``DOMAIN`` name at any depth (e.g.
  ``f"{DOMAIN}_{entry.entry_id}"``), or
- contains the integration's domain (read from ``manifest.json``) as a
  delimited segment of any string literal (including f-string literal
  parts), e.g. ``f"myhub-{device_id}"`` in an integration whose
  manifest declares ``"domain": "myhub"``. A segment is considered
  delimited when bordered by a non-alphanumeric character
  (``_``, ``-``, ``.``, ``:``, space, ...) or a string boundary;
  letters and digits adjacent to the segment make it part of a
  longer identifier, so substrings like ``"myhubitat_..."`` or
  ``"myhub2"`` don't match.

``W7427`` (``home-assistant-entity-unique-id-redundant-platform``)
------------------------------------------------------------------
The ``domain`` field of the registry key (in Home Assistant
user-facing vocabulary: the *platform*, e.g. ``sensor``, ``light``,
``binary_sensor``) is already known from the module the entity lives
in. Repeating that name as a delimited segment of the entity's unique
ID duplicates information already present in the registry key. The
rule fires when the integration sub-module path keys off a known
entity platform name; both single-file platform modules
(``sensor.py``, ``binary_sensor.py``, ``light.py``, ...) and platform
packages (``sensor/__init__.py``, ``sensor/helpers.py``, ...) are in
scope. Shared bases in ``entity.py`` and code in ``__init__.py`` at
the integration root are not in scope because the platform context is
ambiguous there.

Three locations are scanned for both rules: class-body
``_attr_unique_id`` assignments, ``self._attr_unique_id = ...``
assignments inside method bodies, and ``return`` values inside a
``unique_id`` property/method override. Aliased imports
(``from .const import DOMAIN as MY_DOMAIN``) are not scanned.
"""

from collections.abc import Callable, Iterable
import re

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import ENTITY_COMPONENTS
from pylint_home_assistant.helpers.entity_class import inherits_from_entity
from pylint_home_assistant.helpers.integration import read_manifest
from pylint_home_assistant.helpers.module_info import (
    is_integration_module,
    parse_module,
)

_ATTR_NAME = "_attr_unique_id"
_PROPERTY_NAME = "unique_id"


_FSTRING_PLACEHOLDER = "a"


def _joined_str_approximation(node: nodes.JoinedStr) -> str:
    """Build the runtime string of *node* with f-string expressions replaced.

    Each ``FormattedValue`` is replaced by a single alphanumeric character
    so that boundary checks at part boundaries do not claim a delimiter
    that may not exist at runtime. Const string parts are concatenated
    verbatim.
    """
    parts: list[str] = []
    for v in node.values:
        if isinstance(v, nodes.Const) and isinstance(v.value, str):
            parts.append(v.value)
        else:
            parts.append(_FSTRING_PLACEHOLDER)
    return "".join(parts)


def _is_inside_joined_str(node: nodes.NodeNG) -> bool:
    """Return True if *node* has a ``JoinedStr`` ancestor."""
    parent = node.parent
    while parent is not None:
        if isinstance(parent, nodes.JoinedStr):
            return True
        parent = parent.parent
    return False


def _iter_string_literals(value: nodes.NodeNG) -> Iterable[str]:
    """Yield the static string approximations contained in *value*.

    For f-strings (``JoinedStr``), expression parts are substituted with
    a single alphanumeric placeholder so boundary checks evaluate
    against the whole runtime string instead of per-fragment.
    ``Const`` strings outside any ``JoinedStr`` are yielded verbatim;
    those nested inside a ``JoinedStr`` are skipped because they are
    already covered by the ``JoinedStr`` approximation.
    """
    for node in value.nodes_of_class(nodes.JoinedStr):
        yield _joined_str_approximation(node)
    for const in value.nodes_of_class(nodes.Const):
        if isinstance(const.value, str) and not _is_inside_joined_str(const):
            yield const.value


def _value_contains_segment(value: nodes.NodeNG, segment: str) -> bool:
    """Return True if any string literal in *value* contains *segment* delimited.

    A segment is considered delimited when bordered by a non-alphanumeric
    character (``_``, ``-``, ``.``, ``:``, space, ...) or a string
    boundary. Letters and digits are excluded from the boundary set
    because both are valid in HA integration domain names, so substrings
    like ``"myhubitat_..."`` or ``"myhub2"`` don't match ``myhub``.

    f-strings are evaluated against the full runtime string (with
    expression parts substituted by a placeholder), so e.g.
    ``f"{prefix}sensor_{key}"`` does not match ``sensor`` (because the
    character before ``sensor`` at runtime is unknown and may not be a
    delimiter).
    """
    pattern = re.compile(rf"(?:^|[^a-zA-Z0-9]){re.escape(segment)}(?:[^a-zA-Z0-9]|$)")
    return any(pattern.search(s) for s in _iter_string_literals(value))


def _value_references_domain(value: nodes.NodeNG | None, domain: str | None) -> bool:
    """Return True if the value expression embeds the integration's domain.

    Matches either a ``Name(name="DOMAIN")`` reference at any depth, or
    the integration's domain string appearing as a delimited segment of
    any string literal in the value (with f-strings evaluated against
    their full runtime approximation, see ``_iter_string_literals``).
    """
    if value is None:
        return False
    if any(n.name == "DOMAIN" for n in value.nodes_of_class(nodes.Name)):
        return True
    return domain is not None and _value_contains_segment(value, domain)


def _value_references_platform(
    value: nodes.NodeNG | None, platform: str | None
) -> bool:
    """Return True if the value embeds the platform name as a delimited segment."""
    if value is None or platform is None:
        return False
    return _value_contains_segment(value, platform)


def _is_self_attr_target(target: nodes.NodeNG) -> bool:
    """Return True if the target is ``self._attr_unique_id``."""
    match target:
        case nodes.AssignAttr(attrname=name, expr=nodes.Name(name="self")) if (
            name == _ATTR_NAME
        ):
            return True
    return False


def _redundant_value_nodes(
    class_node: nodes.ClassDef,
    check: Callable[[nodes.NodeNG], bool],
) -> list[nodes.NodeNG]:
    """Return value nodes for which *check* returns True.

    Scans three locations:

    - Class-body ``_attr_unique_id = ...`` assignments.
    - ``self._attr_unique_id = ...`` assignments at any depth inside
      method bodies.
    - ``return ...`` statements inside a ``unique_id`` method/property
      override on the class itself.
    """
    hits: list[nodes.NodeNG] = []
    for item in class_node.body:
        match item:
            case nodes.AnnAssign(target=nodes.AssignName(name=name), value=value) if (
                name == _ATTR_NAME and value is not None and check(value)
            ):
                hits.append(value)
            case nodes.Assign(targets=targets, value=value) if any(
                isinstance(t, nodes.AssignName) and t.name == _ATTR_NAME
                for t in targets
            ) and check(value):
                hits.append(value)
    for method in class_node.body:
        if not isinstance(method, nodes.FunctionDef | nodes.AsyncFunctionDef):
            continue
        if method.name == _PROPERTY_NAME:
            hits.extend(
                ret.value
                for ret in method.nodes_of_class(nodes.Return)
                if ret.value is not None and check(ret.value)
            )
            continue
        for stmt in method.nodes_of_class((nodes.Assign, nodes.AnnAssign)):
            match stmt:
                case nodes.Assign(targets=targets, value=value):
                    target_list = list(targets)
                case nodes.AnnAssign(target=target, value=value):
                    target_list = [target]
                case _:
                    continue
            if (
                value is not None
                and check(value)
                and any(_is_self_attr_target(t) for t in target_list)
            ):
                hits.append(value)
    return hits


def _integration_domain(module: nodes.Module) -> str | None:
    """Return the integration's domain from manifest.json, or None."""
    manifest = read_manifest(module)
    return manifest.get("domain") if manifest else None


def _module_platform(module_name: str) -> str | None:
    """Return the entity platform for *module_name*, or None.

    Returns the platform name (e.g. ``"sensor"``) when *module_name*
    points to a known entity-platform sub-module of an integration.
    Returns ``None`` for non-platform sub-modules (``entity.py``,
    ``__init__.py``, ``const.py``, ...) and for modules outside the
    integration root.
    """
    parsed = parse_module(module_name)
    if parsed is None or parsed.module is None:
        return None
    return parsed.module if parsed.module in ENTITY_COMPONENTS else None


class EntityUniqueIdFormatChecker(BaseChecker):
    """Format-related checks on entity unique-ID values."""

    name = "home_assistant_entity_unique_id_format"
    priority = -1
    msgs = {
        "W7425": (
            (
                "Entity class `%s` embeds the integration's domain (its "
                "manifest `domain` field) in its unique ID; the entity "
                "registry already namespaces unique IDs per integration, so "
                "including the domain is redundant"
            ),
            "home-assistant-entity-unique-id-redundant-domain",
            (
                "Used when an entity's unique ID embeds the integration's "
                "domain, either via a reference to the DOMAIN constant or as "
                "a delimited substring of a string literal. Entity registry "
                "uniqueness is keyed on (domain, platform, unique_id), so "
                "including the domain duplicates information already present "
                "in the entity_id namespace."
            ),
        ),
        "W7427": (
            (
                "Entity class `%s` embeds the platform name `%s` in its "
                "unique ID; the entity registry namespaces unique IDs per "
                "platform, so this segment is redundant"
            ),
            "home-assistant-entity-unique-id-redundant-platform",
            (
                "Used when an entity's unique ID contains the name of the "
                "entity platform (e.g. `sensor`, `light`, `binary_sensor`) "
                "as a delimited substring. Entity registry uniqueness is "
                "keyed on (domain, platform, unique_id) where `domain` is "
                "the entity platform, so embedding the platform in the "
                "unique id duplicates information already present in the "
                "registry key."
            ),
        ),
    }
    options = ()

    _is_integration_module: bool
    _integration_domain: str | None
    _platform: str | None

    def visit_module(self, node: nodes.Module) -> None:
        """Cache per-module state."""
        self._is_integration_module = is_integration_module(node.name)
        self._integration_domain = (
            _integration_domain(node) if self._is_integration_module else None
        )
        self._platform = (
            _module_platform(node.name) if self._is_integration_module else None
        )

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Flag entity classes whose unique_id embeds the domain or platform.

        Every class inheriting from ``Entity`` in any integration module
        is inspected. Mixin/abstract bases are not exempted, because the
        antipattern lives in the code (which is inherited by every
        runtime subclass).
        """
        if not self._is_integration_module:
            return
        if not inherits_from_entity(node):
            return
        for value_node in _redundant_value_nodes(
            node, lambda v: _value_references_domain(v, self._integration_domain)
        ):
            self.add_message(
                "home-assistant-entity-unique-id-redundant-domain",
                node=value_node,
                args=(node.name,),
            )
        platform = self._platform
        if platform is None:
            return
        for value_node in _redundant_value_nodes(
            node, lambda v: _value_references_platform(v, platform)
        ):
            self.add_message(
                "home-assistant-entity-unique-id-redundant-platform",
                node=value_node,
                args=(node.name, platform),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(EntityUniqueIdFormatChecker(linter))
