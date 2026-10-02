"""Checker for the usb dependency when a config flow uses SerialPortSelector.

``SerialPortSelector`` populates its port list via the
``usb/list_serial_ports`` websocket command, which is only registered when the
``usb`` integration is set up. Integrations using the selector must therefore
declare ``usb`` as a hard dependency in ``manifest.json`` so it is guaranteed
to be set up; ``after_dependencies`` is not sufficient because it does not
force ``usb`` to be set up.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import Module
from pylint_home_assistant.helpers.integration import read_manifest
from pylint_home_assistant.helpers.module_info import parse_module


class HassEnforceSerialPortSelectorUsbChecker(BaseChecker):
    """Checker for the usb dependency when using SerialPortSelector."""

    name = "home_assistant_serial_port_selector_usb_dependency"
    priority = -1
    msgs = {
        "W7430": (
            "Config flow uses SerialPortSelector but the integration does not "
            "declare 'usb' in 'dependencies' in manifest.json",
            "home-assistant-serial-port-selector-usb-dependency",
            "SerialPortSelector populates its port list via the "
            "'usb/list_serial_ports' websocket command, which is only "
            "registered when the 'usb' integration is set up. The selector "
            "therefore requires 'usb' as a hard dependency; "
            "'after_dependencies' is not sufficient because it does not force "
            "'usb' to be set up.",
        ),
    }
    options = ()

    def __init__(self, linter: PyLinter) -> None:
        """Initialize the checker."""
        super().__init__(linter)
        self._reported_modules: set[str] = set()

    def visit_call(self, node: nodes.Call) -> None:
        """Check that SerialPortSelector usage declares the usb dependency."""
        func = node.func
        if isinstance(func, nodes.Attribute):
            name = func.attrname
        elif isinstance(func, nodes.Name):
            name = func.name
        else:
            return
        if name != "SerialPortSelector":
            return

        parsed = parse_module(node.root().name)
        if parsed is None or parsed.module != Module.CONFIG_FLOW:
            return

        module_name = node.root().name
        if module_name in self._reported_modules:
            return

        manifest = read_manifest(node.root())
        if manifest is None:
            return

        if "usb" in manifest.get("dependencies", []):
            return

        self._reported_modules.add(module_name)
        self.add_message(
            "home-assistant-serial-port-selector-usb-dependency",
            node=node,
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceSerialPortSelectorUsbChecker(linter))
