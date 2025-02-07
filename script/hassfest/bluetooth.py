"""Generate bluetooth file."""

from __future__ import annotations

from .model import Config, Integration
from .serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration]) -> str:
    """Validate and generate bluetooth data."""
    match_list = []

    for domain in sorted(integrations):
        match_types = integrations[domain].manifest.get("bluetooth", [])

        if not match_types:
            continue

        match_list.extend({"domain": domain, **entry} for entry in match_types)

    return format_python_namespace(
        {"BLUETOOTH": match_list},
        annotations={
            "BLUETOOTH": "Final[list[dict[str, bool | str | int | list[int]]]]"
        },
    )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate bluetooth file."""
    bluetooth_path = config.root / "homeassistant/generated/bluetooth.py"
    config.cache["bluetooth"] = content = generate_and_validate(integrations)

    if config.specific_integrations:
        return

    if bluetooth_path.read_text() != content:
        config.add_error(
            "bluetooth",
            "File bluetooth.py is not up to date. Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate bluetooth file."""
    bluetooth_path = config.root / "homeassistant/generated/bluetooth.py"
    bluetooth_path.write_text(f"{config.cache['bluetooth']}")
