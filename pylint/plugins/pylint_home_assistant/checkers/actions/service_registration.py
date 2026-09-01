"""Checker for service registration in async_setup_entry.

Services must be registered in ``async_setup``, not ``async_setup_entry``.
Registering in ``async_setup_entry`` means services are only available when
a config entry is loaded, which prevents Home Assistant from validating
automations that reference those services.

This checker flags:
- ``hass.services.async_register(...)`` / ``hass.services.register(...)``
- ``async_register_admin_service(...)`` (both bare name and attribute forms)

Entity services (``async_register_entity_service``) in platform
``async_setup_entry`` are NOT flagged, as those are tied to the
platform lifecycle.

The checker also follows calls to functions defined in the same module,
so service registrations inside helper functions called from
``async_setup_entry`` are caught too.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-setup/
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_integration_module


def _is_service_registration(node: nodes.Call) -> bool:
    """Return True if *node* is a service registration call."""
    if not isinstance(node.func, (nodes.Attribute, nodes.Name)):
        return False

    match node.func:
        # hass.services.async_register(...) / hass.services.register(...)
        case nodes.Attribute(
            attrname="async_register" | "register",
            expr=nodes.Attribute(attrname="services"),
        ):
            return True
        # async_register_admin_service(...)
        case nodes.Name(name="async_register_admin_service"):
            return True
        # service.async_register_admin_service(...)
        case nodes.Attribute(attrname="async_register_admin_service"):
            return True

    return False


def _find_service_registrations(
    func: nodes.FunctionDef,
    module: nodes.Module,
    visited: set[str] | None = None,
) -> list[nodes.Call]:
    """Find service registration calls, following calls to local functions.

    Recursively checks functions defined in the same module that are
    called from *func*, to catch service registrations in helper functions.
    """
    if visited is None:
        visited = set()
    visited.add(func.name)

    violations: list[nodes.Call] = []
    for node in func.nodes_of_class(nodes.Call):
        # Direct service registration
        if _is_service_registration(node):
            violations.append(node)
            continue

        # Follow calls to functions defined in the same module
        if isinstance(node.func, nodes.Name) and node.func.name not in visited:
            for child in module.body:
                if (
                    isinstance(child, (nodes.FunctionDef, nodes.AsyncFunctionDef))
                    and child.name == node.func.name
                ):
                    violations.extend(
                        _find_service_registrations(child, module, visited)
                    )
                    break

    return violations


class ServiceRegistrationChecker(BaseChecker):
    """Checker for service registration in async_setup_entry."""

    name = "home_assistant_actions_service_registration"
    priority = -1
    msgs = {
        "W7414": (
            "Service registered in `async_setup_entry` instead of `async_setup` "
            "(https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/action-setup)",
            "home-assistant-service-registered-in-setup-entry",
            "Used when a service is registered inside async_setup_entry "
            "or a function called from it. Services should be registered "
            "in async_setup so they are available for automation validation "
            "even when the config entry is not loaded.",
        ),
    }
    options = ()

    _in_integration: bool
    _module: nodes.Module | None

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in an integration module."""
        self._in_integration = is_integration_module(node.name)
        self._module = node if self._in_integration else None

    def visit_asyncfunctiondef(self, node: nodes.AsyncFunctionDef) -> None:
        """Check async_setup_entry for service registrations."""
        if not self._in_integration or self._module is None:
            return

        if node.name != "async_setup_entry":
            return

        # Must be a top-level function (not a method)
        if not isinstance(node.parent, nodes.Module):
            return

        for call in _find_service_registrations(node, self._module):
            self.add_message(
                "home-assistant-service-registered-in-setup-entry",
                node=call,
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ServiceRegistrationChecker(linter))
