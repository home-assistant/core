"""Checker for action names and fields that do not use the action enums.

Action names and fields are defined in ``<Prefix>Service`` and
``<Prefix>ServiceArgument`` ``StrEnum``s. In ``services.py``, this checker
flags:
- action registrations whose name is not a ``<Prefix>Service`` member
- keys of the registered action schemas and ``ServiceCall.data`` lookups that
  are not ``<Prefix>ServiceArgument`` members

Shared selector fields such as ``config_entry_id``, ``device_id`` and
``entity_id`` keep using the ``homeassistant.const`` constants.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from astroid import nodes
from astroid.exceptions import InferenceError
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import parse_module

_SERVICE_SUFFIXES = ("Service",)
_ARGUMENT_SUFFIXES = ("ServiceArgument",)

# Selector fields that are not specific to one integration
_SHARED_FIELDS = {
    "area_id",
    "config_entry_id",
    "device_id",
    "entity_id",
    "floor_id",
    "label_id",
}

_SCHEMA_MARKERS = {"Exclusive", "Inclusive", "Optional", "Required"}

# Calls whose arguments are schemas for the same data
_SCHEMA_WRAPPERS = {"All", "Any", "Schema", "make_entity_service_schema"}


@dataclass(frozen=True, slots=True)
class _Arguments:
    """Position and keyword of the action name and schema arguments."""

    name: tuple[int, str]
    schema: tuple[int | None, str]


# Helpers in ``homeassistant.helpers.service``
_HELPER_ARGUMENTS = {
    "async_register_admin_service": _Arguments((2, "service"), (4, "schema")),
    "async_register_batched_entity_service": _Arguments((2, "name"), (None, "schema")),
    "async_register_batched_platform_entity_service": _Arguments(
        (2, "service_name"), (None, "schema")
    ),
    "async_register_platform_entity_service": _Arguments(
        (2, "service_name"), (None, "schema")
    ),
}

# ``EntityComponent`` methods
_COMPONENT_ARGUMENTS = {
    "async_register_batched_entity_service": _Arguments((0, "name"), (1, "schema")),
    "async_register_entity_service": _Arguments((0, "name"), (1, "schema")),
}

# ``hass.services.async_register`` / ``hass.services.register``
_SERVICES_ARGUMENTS = _Arguments((1, "service"), (3, "schema"))


def _argument(
    node: nodes.Call, position: int | None, keyword: str
) -> nodes.NodeNG | None:
    """Return the argument passed at *position* or as *keyword*."""
    for kwarg in node.keywords or ():
        if kwarg.arg == keyword:
            return kwarg.value
    if position is not None and len(node.args) > position:
        return node.args[position]
    return None


def _registration_arguments(node: nodes.Call) -> _Arguments | None:
    """Return the arguments of an action registration call, if it is one."""
    match node.func:
        case nodes.Attribute(
            attrname="async_register" | "register",
            expr=nodes.Attribute(attrname="services"),
        ):
            return _SERVICES_ARGUMENTS
        case (
            nodes.Name(name=name)
            | nodes.Attribute(attrname=name, expr=nodes.Name(name="service"))
        ) if name in _HELPER_ARGUMENTS:
            return _HELPER_ARGUMENTS[name]
        case nodes.Attribute(attrname=name) if name in _COMPONENT_ARGUMENTS:
            return _COMPONENT_ARGUMENTS[name]
    return None


def _is_enum_member(node: nodes.NodeNG, suffixes: tuple[str, ...]) -> bool:
    """Return True if *node* is ``<Prefix><suffix>.MEMBER``."""
    match node:
        case nodes.Attribute(
            expr=nodes.Name(name=name) | nodes.Attribute(attrname=name)
        ) if isinstance(name, str):
            return name.endswith(suffixes)
    return False


def _string_value(node: nodes.NodeNG) -> str | None:
    """Return the string *node* evaluates to, if it can be inferred."""
    try:
        inferred = next(node.infer())
    except InferenceError, StopIteration:
        return None
    if isinstance(inferred, nodes.Const) and isinstance(inferred.value, str):
        return inferred.value
    return None


def _schema_dicts(
    node: nodes.NodeNG, module: nodes.Module, seen: set[nodes.NodeNG]
) -> Iterator[nodes.Dict]:
    """Yield the dicts whose keys are the fields of the schema *node*.

    Follows module-level names, schema wrappers such as ``probatio.Schema``
    and ``probatio.All``, ``.extend()`` and ``**`` merges, but not the values
    of a dict: those describe the content of a field.
    """
    if node in seen:
        return
    seen.add(node)
    match node:
        case nodes.Dict():
            yield node
            for key, value in node.items:
                if isinstance(key, nodes.DictUnpack):
                    yield from _schema_dicts(value, module, seen)
        # BASE_SCHEMA.extend({...})
        case nodes.Call(func=nodes.Attribute(attrname="extend", expr=base)):
            yield from _schema_dicts(base, module, seen)
            for argument in node.args:
                yield from _schema_dicts(argument, module, seen)
        case nodes.Call(
            func=nodes.Attribute(attrname=wrapper) | nodes.Name(name=wrapper)
        ) if wrapper in _SCHEMA_WRAPPERS:
            for argument in node.args:
                yield from _schema_dicts(argument, module, seen)
        case nodes.Name(name=name):
            for assignment in module.locals.get(name, ()):
                if isinstance(assignment.parent, (nodes.Assign, nodes.AnnAssign)):
                    yield from _schema_dicts(assignment.parent.value, module, seen)


def _is_service_call(node: nodes.NodeNG) -> bool:
    """Return True if *node* is a function argument annotated as ``ServiceCall``."""
    if not isinstance(node, nodes.Name):
        return False
    _, assignments = node.lookup(node.name)
    for assignment in assignments:
        arguments = assignment.parent
        if (
            isinstance(assignment, nodes.AssignName)
            and isinstance(arguments, nodes.Arguments)
            and assignment in arguments.args
            and isinstance(
                annotation := arguments.annotations[arguments.args.index(assignment)],
                nodes.NodeNG,
            )
        ):
            annotation_name: str = annotation.as_string()
            return annotation_name.rsplit(".", 1)[-1] == "ServiceCall"
    return False


class ServiceEnumsChecker(BaseChecker):
    """Checker for action names and fields that do not use the action enums."""

    name = "home_assistant_actions_service_enums"
    priority = -1
    msgs = {
        "W7454": (
            "Action name should be a member of the integration's `Service` StrEnum",
            "home-assistant-action-name-not-enum",
            "Used when an action is registered in `services.py` with a name "
            "that is not a member of the integration's `<Prefix>Service` "
            "StrEnum.",
        ),
        "W7455": (
            "Action field `%s` should be a member of the integration's "
            "`ServiceArgument` StrEnum",
            "home-assistant-action-field-not-enum",
            "Used when a key of a registered action schema or a "
            "`ServiceCall.data` lookup in `services.py` is not a member of the "
            "integration's `<Prefix>ServiceArgument` StrEnum. Shared selector "
            "fields such as `config_entry_id`, `device_id` and `entity_id` are "
            "allowed.",
        ),
    }
    options = ()

    _in_services_module: bool
    _schema_dicts: set[nodes.Dict]

    def visit_module(self, node: nodes.Module) -> None:
        """Collect the schemas of the actions registered in ``services.py``."""
        module = parse_module(node.name)
        self._in_services_module = module is not None and module.module == "services"
        self._schema_dicts = set()
        if not self._in_services_module:
            return
        seen: set[nodes.NodeNG] = set()
        for call in node.nodes_of_class(nodes.Call):
            if (arguments := _registration_arguments(call)) is not None and (
                schema := _argument(call, *arguments.schema)
            ) is not None:
                self._schema_dicts.update(_schema_dicts(schema, node, seen))
        for schema_dict in self._schema_dicts:
            for key, _ in schema_dict.items:
                match key:
                    case nodes.Call(
                        func=nodes.Attribute(attrname=marker) | nodes.Name(name=marker)
                    ) if marker in _SCHEMA_MARKERS:
                        if (field := _argument(key, 0, "schema")) is not None:
                            self._check_field(field)

    def visit_call(self, node: nodes.Call) -> None:
        """Check action names and ``ServiceCall.data.get`` lookups."""
        if not self._in_services_module:
            return
        if (
            (arguments := _registration_arguments(node)) is not None
            and (name := _argument(node, *arguments.name)) is not None
            and not _is_enum_member(name, _SERVICE_SUFFIXES)
        ):
            self.add_message("home-assistant-action-name-not-enum", node=name)
        match node:
            case nodes.Call(
                func=nodes.Attribute(
                    attrname="get", expr=nodes.Attribute(attrname="data", expr=expr)
                )
            ) if (
                _is_service_call(expr)
                and (field := _argument(node, 0, "key")) is not None
            ):
                self._check_field(field)

    def visit_subscript(self, node: nodes.Subscript) -> None:
        """Check ``ServiceCall.data[...]`` lookups."""
        if not self._in_services_module:
            return
        match node:
            case nodes.Subscript(value=nodes.Attribute(attrname="data", expr=expr)) if (
                _is_service_call(expr)
            ):
                self._check_field(node.slice)

    def _check_field(self, node: nodes.NodeNG) -> None:
        """Check that the action field *node* is an enum member.

        Only keys that resolve to a plain string are checked: dynamic keys,
        whose value cannot be inferred, are skipped.
        """
        if _is_enum_member(node, _ARGUMENT_SUFFIXES):
            return
        if (value := _string_value(node)) is None or value in _SHARED_FIELDS:
            return
        self.add_message(
            "home-assistant-action-field-not-enum", node=node, args=(value,)
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ServiceEnumsChecker(linter))
