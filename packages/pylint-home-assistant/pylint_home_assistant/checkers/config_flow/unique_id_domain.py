"""Checker for config flows that use the integration domain as unique ID.

The domain is the same for every config entry, so as a unique ID it doesn't
identify a device or an account, it only limits the integration to a single
config entry. The ``single_config_entry`` manifest option does that, and
``_async_handle_discovery_without_unique_id`` stops duplicate discovery flows.

``W7456`` (``home-assistant-config-flow-unique-id-domain``)
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import parse_module


class ConfigFlowUniqueIdDomainChecker(BaseChecker):
    """Checker for the domain used as config entry unique ID."""

    name = "home_assistant_config_flow_unique_id_domain"
    priority = -1
    msgs = {
        "W7456": (
            (
                "Don't use the domain as unique ID, use an ID of the device or "
                "account. To allow a single config entry, set "
                "`single_config_entry` in the manifest, and use "
                "`_async_handle_discovery_without_unique_id()` in discovery steps"
            ),
            "home-assistant-config-flow-unique-id-domain",
            (
                "Used when `async_set_unique_id` is called with the integration "
                "domain. The domain doesn't identify a device or account, it "
                "only limits the integration to a single config entry."
            ),
        ),
    }
    options = ()

    def visit_call(self, node: nodes.Call) -> None:
        """Check ``async_set_unique_id`` calls."""
        match node.func:
            case nodes.Attribute(attrname="async_set_unique_id"):
                pass
            case _:
                return
        if (parsed := parse_module(node.root().name)) is None:
            return

        unique_id = node.args[0] if node.args else None
        for keyword in node.keywords:
            if keyword.arg == "unique_id":
                unique_id = keyword.value

        match unique_id:
            case nodes.Name(name="DOMAIN") | nodes.Attribute(attrname="DOMAIN"):
                pass
            case nodes.Const(value=str(value)) if value == parsed.domain:
                pass
            case _:
                return
        self.add_message("home-assistant-config-flow-unique-id-domain", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ConfigFlowUniqueIdDomainChecker(linter))
