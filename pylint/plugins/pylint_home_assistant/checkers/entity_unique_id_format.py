"""Checker for entity unique-ID value-format antipatterns.

Hosts format-related checks on the value an entity uses for its unique
ID (``_attr_unique_id`` assignments and ``unique_id`` property/method
returns). Once an integration ships with malformed unique_ids, the IDs
cannot be changed without an entity-registry migration, so these checks
are **not** gated on ``quality_scale.yaml`` claims, and they fire on
every class inheriting from ``Entity`` anywhere inside an integration
(including shared bases in ``entity.py`` and mixins/abstract bases
subclassed by other classes in the same module).

``W7425`` (``home-assistant-entity-unique-id-redundant-domain``)
----------------------------------------------------------------
The entity registry keys uniqueness on ``(domain, platform, unique_id)``
where ``platform`` is the integration's name (as declared by the
``"domain"`` field in ``manifest.json``). Any prefix in the unique_id
that repeats the integration's name duplicates information already
present in the registry key. The rule fires when the value used for
the entity's unique id either:

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

Three locations are scanned: class-body ``_attr_unique_id``
assignments, ``self._attr_unique_id = ...`` assignments inside method
bodies, and ``return`` values inside a ``unique_id`` property/method
override. Aliased imports (``from .const import DOMAIN as MY_DOMAIN``)
are not scanned.
"""

import re

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.entity_class import inherits_from_entity
from pylint_home_assistant.helpers.integration import read_manifest
from pylint_home_assistant.helpers.module_info import is_integration_module

_ATTR_NAME = "_attr_unique_id"
_PROPERTY_NAME = "unique_id"


def _value_references_domain(value: nodes.NodeNG | None, domain: str | None) -> bool:
    """Return True if the value expression embeds the integration's domain.

    Matches either a ``Name(name="DOMAIN")`` reference at any depth, or
    the integration's domain string appearing as a delimited segment
    (bordered by a non-alphanumeric character or a string boundary)
    inside any string ``Const`` in the value (including f-string
    literal parts). Letters and digits are excluded from the boundary
    set because both are valid in HA integration domain names.
    """
    if value is None:
        return False
    if any(n.name == "DOMAIN" for n in value.nodes_of_class(nodes.Name)):
        return True
    if domain:
        pattern = re.compile(
            rf"(?:^|[^a-zA-Z0-9]){re.escape(domain)}(?:[^a-zA-Z0-9]|$)"
        )
        for const in value.nodes_of_class(nodes.Const):
            if isinstance(const.value, str) and pattern.search(const.value):
                return True
    return False


def _is_self_attr_target(target: nodes.NodeNG) -> bool:
    """Return True if the target is ``self._attr_unique_id``."""
    match target:
        case nodes.AssignAttr(attrname=name, expr=nodes.Name(name="self")) if (
            name == _ATTR_NAME
        ):
            return True
    return False


def _redundant_domain_value_nodes(
    class_node: nodes.ClassDef, domain: str | None
) -> list[nodes.NodeNG]:
    """Return value nodes that embed the domain in the entity's unique_id.

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
                name == _ATTR_NAME and _value_references_domain(value, domain)
            ):
                hits.append(value)
            case nodes.Assign(targets=targets, value=value) if any(
                isinstance(t, nodes.AssignName) and t.name == _ATTR_NAME
                for t in targets
            ) and _value_references_domain(value, domain):
                hits.append(value)
    for method in class_node.body:
        if not isinstance(method, nodes.FunctionDef):
            continue
        if method.name == _PROPERTY_NAME:
            hits.extend(
                ret.value
                for ret in method.nodes_of_class(nodes.Return)
                if ret.value is not None and _value_references_domain(ret.value, domain)
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
            if _value_references_domain(value, domain) and any(
                _is_self_attr_target(t) for t in target_list
            ):
                hits.append(value)
    return hits


def _integration_domain(module: nodes.Module) -> str | None:
    """Return the integration's domain from manifest.json, or None."""
    manifest = read_manifest(module)
    return manifest.get("domain") if manifest else None


class EntityUniqueIdFormatChecker(BaseChecker):
    """Format-related checks on ``_attr_unique_id`` values."""

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
    }
    options = ()

    _is_integration_module: bool
    _integration_domain: str | None

    def visit_module(self, node: nodes.Module) -> None:
        """Cache per-module state."""
        self._is_integration_module = is_integration_module(node.name)
        self._integration_domain = (
            _integration_domain(node) if self._is_integration_module else None
        )

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Flag entity classes whose unique_id embeds the integration's domain.

        Every class inheriting from ``Entity`` in any integration module
        is inspected. Mixin/abstract bases are not exempted, because the
        antipattern lives in the code (which is inherited by every
        runtime subclass).
        """
        if not self._is_integration_module:
            return
        if not inherits_from_entity(node):
            return
        for value_node in _redundant_domain_value_nodes(node, self._integration_domain):
            self.add_message(
                "home-assistant-entity-unique-id-redundant-domain",
                node=value_node,
                args=(node.name,),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(EntityUniqueIdFormatChecker(linter))
