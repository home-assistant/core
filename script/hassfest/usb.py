"""Generate usb file."""

import ast

from hassfest import ast_parse_module
from hassfest.model import Config, Integration
from hassfest.serializer import format_python_namespace


def _uses_serial_port_selector(integration: Integration) -> bool:
    """Return if the config flow of an integration uses SerialPortSelector."""
    config_flow = integration.path / "config_flow.py"
    if not config_flow.is_file():
        return False

    for node in ast.walk(ast_parse_module(config_flow)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Name) and func.id == "SerialPortSelector") or (
            isinstance(func, ast.Attribute) and func.attr == "SerialPortSelector"
        ):
            return True
    return False


def generate_and_validate(integrations: dict[str, Integration]) -> str:
    """Validate and generate usb data."""
    match_list = []
    serial_port_selector_integrations = []

    for domain in sorted(integrations):
        integration = integrations[domain]
        manifest = integration.manifest

        # Only integrations opening their port with serialx may use the selector
        if _uses_serial_port_selector(integration):
            serial_port_selector_integrations.append(domain)

        match_types = manifest.get("usb", [])

        if not match_types:
            continue

        match_list.extend(
            {
                "domain": domain,
                **{k: v for k, v in entry.items() if k != "known_devices"},
            }
            for entry in match_types
        )

    return format_python_namespace(
        {
            "USB": match_list,
            "SERIAL_PORT_SELECTOR_INTEGRATIONS": serial_port_selector_integrations,
        }
    )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate usb file."""
    usb_path = config.root / "homeassistant/generated/usb.py"
    config.cache["usb"] = content = generate_and_validate(integrations)

    if config.specific_integrations:
        return

    if usb_path.read_text() != content:
        config.add_error(
            "usb",
            "File usb.py is not up to date. Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate usb file."""
    usb_path = config.root / "homeassistant/generated/usb.py"
    usb_path.write_text(f"{config.cache['usb']}")
