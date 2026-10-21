"""Checker for raw string units on entities with a device class.

Sensors and numbers with a device class only accept the units listed for it
in ``DEVICE_CLASS_UNITS`` of their platform's ``const.py``. Those units are
constants, such as ``UnitOfTemperature.CELSIUS``, which the entity should use
instead of a raw string like ``"°C"``.

Entities without a device class, or with one that accepts any unit (such as
``monetary``), are not checked, as a raw string is often the only option
there.

``W7454`` (``home-assistant-unit-raw-string``)
``W7455`` (``home-assistant-unit-invalid-for-device-class``)
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.entity_class import (
    inherits_from_entity,
    resolve_entity_description_class,
)
from pylint_home_assistant.helpers.module_info import is_integration_module

_DEVICE_CLASS_MODULES = {
    "homeassistant.components.number.const.NumberDeviceClass": (
        "homeassistant.components.number.const"
    ),
    "homeassistant.components.sensor.const.SensorDeviceClass": (
        "homeassistant.components.sensor.const"
    ),
}

_UNIT_FIELDS = frozenset(
    {
        "native_unit_of_measurement",
        "suggested_unit_of_measurement",
        "unit_of_measurement",
    }
)

# Device class enum qname -> device class member -> unit value -> constant
_units_cache: dict[str, dict[str, dict[str, str]]] = {}


def _enum_members(class_node: nodes.ClassDef) -> dict[str, str]:
    """Return ``{value: "Enum.MEMBER"}`` for the string members of an enum."""
    members: dict[str, str] = {}
    for item in class_node.body:
        match item:
            case nodes.Assign(
                targets=[nodes.AssignName(name=name)],
                value=nodes.Const(value=str() as value),
            ):
                members.setdefault(value, f"{class_node.name}.{name}")
    return members


def _infer_one(node: nodes.NodeNG) -> nodes.NodeNG | None:
    """Return the first inferred value of *node*."""
    try:
        return next(node.infer())
    except astroid.exceptions.InferenceError, StopIteration:
        return None


def _resolve_units(node: nodes.NodeNG) -> dict[str, str]:
    """Return ``{value: constant}`` for one entry of a device class unit set."""
    match node:
        case nodes.Attribute(expr=expr, attrname=attrname):
            if isinstance(enum_class := _infer_one(expr), nodes.ClassDef):
                return {
                    value: name
                    for value, name in _enum_members(enum_class).items()
                    if name == f"{enum_class.name}.{attrname}"
                }
        case nodes.Name(name=name):
            match _infer_one(node):
                case nodes.ClassDef() as enum_class:
                    return _enum_members(enum_class)
                case nodes.Const(value=str() as value):
                    return {value: name}
        case nodes.Starred(value=value):
            return _resolve_units(value)
    return {}


def _load_device_class_units(enum_qname: str) -> dict[str, dict[str, str]]:
    """Return the allowed units per device class from ``DEVICE_CLASS_UNITS``."""
    if enum_qname in _units_cache:
        return _units_cache[enum_qname]

    units: dict[str, dict[str, str]] = {}
    _units_cache[enum_qname] = units
    try:
        module = astroid.MANAGER.ast_from_module_name(_DEVICE_CLASS_MODULES[enum_qname])
    except astroid.exceptions.AstroidBuildingError:
        return units

    unit_dict = next(
        (
            item.value
            for item in module.body
            if isinstance(item, nodes.AnnAssign)
            and isinstance(item.target, nodes.AssignName)
            and item.target.name == "DEVICE_CLASS_UNITS"
            and isinstance(item.value, nodes.Dict)
        ),
        None,
    )
    if unit_dict is None:
        return units

    for key, value in unit_dict.items:
        if not isinstance(key, nodes.Attribute):
            continue
        match value:
            # set(UnitOfTemperature)
            case nodes.Call(func=nodes.Name(name="set"), args=[arg]):
                elements = [arg]
            case nodes.Set(elts=elts):
                elements = elts
            case _:
                continue
        allowed: dict[str, str] = {}
        for element in elements:
            for unit, name in _resolve_units(element).items():
                allowed.setdefault(unit, name)
        units[key.attrname] = allowed

    return units


def _resolve_device_class(node: nodes.NodeNG) -> tuple[str, str] | None:
    """Return the device class enum qname and member *node* refers to."""
    if not isinstance(node, nodes.Attribute):
        return None
    enum_class = _infer_one(node.expr)
    if (
        not isinstance(enum_class, nodes.ClassDef)
        or enum_class.qname() not in _DEVICE_CLASS_MODULES
    ):
        return None
    return enum_class.qname(), node.attrname


class DeviceClassUnitChecker(BaseChecker):
    """Checker for raw string units on entities with a device class."""

    name = "home_assistant_device_class_unit"
    priority = -1
    msgs = {
        "W7454": (
            "Use %s instead of the raw string '%s' for %s",
            "home-assistant-unit-raw-string",
            "Used when an entity with a device class sets its unit to a raw "
            "string that is available as a constant.",
        ),
        "W7455": (
            "'%s' is not a valid unit for %s",
            "home-assistant-unit-invalid-for-device-class",
            "Used when an entity with a device class sets its unit to a raw "
            "string that the device class does not accept.",
        ),
    }
    options = ()

    _in_integration: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in an integration module."""
        self._in_integration = is_integration_module(node.name)

    def visit_call(self, node: nodes.Call) -> None:
        """Check entity descriptions that set a device class and a unit."""
        if not self._in_integration or not node.keywords:
            return

        keywords = {keyword.arg: keyword for keyword in node.keywords}
        if (
            "device_class" not in keywords
            or not _UNIT_FIELDS & keywords.keys()
            or resolve_entity_description_class(node) is None
        ):
            return

        self._check(
            keywords["device_class"].value,
            {
                field: (keyword, keyword.value)
                for field, keyword in keywords.items()
                if field in _UNIT_FIELDS
            },
        )

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Check entity classes that set a device class and a unit."""
        if not self._in_integration:
            return

        assignments: dict[str, tuple[nodes.NodeNG, nodes.NodeNG]] = {}
        for item in node.body:
            match item:
                case (
                    nodes.Assign(targets=[nodes.AssignName(name=name)], value=value)
                    | nodes.AnnAssign(target=nodes.AssignName(name=name), value=value)
                ) if value is not None and name.startswith("_attr_"):
                    assignments[name.removeprefix("_attr_")] = (item, value)

        if (
            "device_class" not in assignments
            or not _UNIT_FIELDS & assignments.keys()
            or not inherits_from_entity(node)
        ):
            return

        self._check(
            assignments["device_class"][1],
            {
                field: assignment
                for field, assignment in assignments.items()
                if field in _UNIT_FIELDS
            },
        )

    def _check(
        self,
        device_class_node: nodes.NodeNG,
        units: dict[str, tuple[nodes.NodeNG, nodes.NodeNG]],
    ) -> None:
        """Flag raw string units, given as ``{field: (report node, value)}``."""
        if (device_class := _resolve_device_class(device_class_node)) is None:
            return
        enum_qname, member = device_class
        # Device classes without a unit list, such as monetary, accept any unit
        if (allowed := _load_device_class_units(enum_qname).get(member)) is None:
            return

        device_class_name = f"{enum_qname.rsplit('.', 1)[1]}.{member}"
        for field, (report_node, value_node) in units.items():
            if not isinstance(value_node, nodes.Const) or not isinstance(
                value_node.value, str
            ):
                continue
            unit = value_node.value
            if (constant := allowed.get(unit)) is not None:
                self.add_message(
                    "home-assistant-unit-raw-string",
                    node=report_node,
                    args=(constant, unit, field),
                )
            else:
                self.add_message(
                    "home-assistant-unit-invalid-for-device-class",
                    node=report_node,
                    args=(unit, device_class_name),
                )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(DeviceClassUnitChecker(linter))
