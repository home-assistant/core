"""Generate bluetooth file."""
from __future__ import annotations

from .model import Config, Integration
from .serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration]) -> str:
    """Validate and generate Bluetooth data.

    Args:
        integrations (dict[str, Integration]): A dictionary of integrations.

    Returns:
        str: The formatted Bluetooth data.
    """
    bluetooth_data = []

    for domain in sorted(integrations):
        bluetooth_manifest = integrations[domain].manifest.get("bluetooth", [])

        if not bluetooth_manifest:
            continue

        for entry in bluetooth_manifest:
            bluetooth_data.append({"domain": domain, **entry})

    return format_python_namespace(
        {"BLUETOOTH": bluetooth_data},
        annotations={"BLUETOOTH": list[dict[str, bool | str | int | list[int]]]},
    )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate the Bluetooth file.

    Args:
        integrations (dict[str, Integration]): A dictionary of integrations.
        config (Config): The configuration.

    Returns:
        None
    """
    bluetooth_path = config.root / "homeassistant/generated/bluetooth.py"
    config.cache["bluetooth"] = generated_content = generate_and_validate(integrations)

    if config.specific_integrations:
        return

    with open(str(bluetooth_path)) as file:
        current_content = file.read()
        if current_content != generated_content:
            config.add_error(
                "bluetooth",
                "File bluetooth.py is not up to date. Run python3 -m script.hassfest",
                fixable=True,
            )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate the Bluetooth file.

    Args:
        integrations (dict[str, Integration]): A dictionary of integrations.
        config (Config): The configuration.

    Returns:
        None
    """
    bluetooth_path = config.root / "homeassistant/generated/bluetooth.py"
    with open(str(bluetooth_path), "w") as file:
        file.write(config.cache["bluetooth"])
