"""Shared helpers for action/service checkers."""

from dataclasses import dataclass, field

from astroid import nodes

from pylint_home_assistant.helpers.module_info import parse_module

from .const import PLATFORM_ACTION_METHODS


@dataclass
class ActionHandlers:
    """Action handler names for a module, split by source.

    ``platform_methods`` are entity action methods defined by the platform
    (e.g., ``async_turn_on`` for switch). These must be on an entity class.

    ``registered_handlers`` are dynamically registered service handlers
    (via ``hass.services.async_register`` etc.). These can be standalone
    functions or methods.
    """

    platform_methods: set[str] = field(default_factory=set)
    registered_handlers: set[str] = field(default_factory=set)

    @property
    def all_names(self) -> set[str]:
        """Return all handler names."""
        return self.platform_methods | self.registered_handlers


def collect_action_handlers(module: nodes.Module) -> ActionHandlers:
    """Collect all action handler names for the given module.

    Returns an ``ActionHandlers`` with platform methods and dynamically
    registered handlers separated, so the checker can apply the right
    scope rules to each.
    """
    result = ActionHandlers()

    parsed = parse_module(module.name)
    if parsed is None:
        return result

    # Add platform-specific entity action methods
    if parsed.module and (
        platform_methods := PLATFORM_ACTION_METHODS.get(parsed.module)
    ):
        result.platform_methods = set(platform_methods)

    # Discover dynamically registered service handlers
    for call in module.nodes_of_class(nodes.Call):
        match call.func:
            case nodes.Attribute(attrname="async_register_entity_service"):
                if len(call.args) >= 3:
                    # String method name: "async_set_speed"
                    if isinstance(call.args[2], nodes.Const):
                        result.registered_handlers.add(call.args[2].value)
                    # Function reference: async_handle_snapshot_service
                    elif isinstance(call.args[2], nodes.Name):
                        result.registered_handlers.add(call.args[2].name)
            # hass.services.async_register(DOMAIN, "name", handler)
            case nodes.Attribute(
                attrname="async_register",
                expr=nodes.Attribute(attrname="services"),
            ):
                if len(call.args) >= 3 and isinstance(call.args[2], nodes.Name):
                    result.registered_handlers.add(call.args[2].name)
            # async_register_admin_service(hass, DOMAIN, "name", handler)
            # Also matches service.async_register_admin_service(...)
            case (
                nodes.Name(name="async_register_admin_service")
                | nodes.Attribute(attrname="async_register_admin_service")
            ):
                if len(call.args) >= 4 and isinstance(call.args[3], nodes.Name):
                    result.registered_handlers.add(call.args[3].name)

    return result
