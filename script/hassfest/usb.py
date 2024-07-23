"""Generate usb file."""

from __future__ import annotations

from .model import Config, Integration
from .serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration]) -> str:
    """Validate and generate usb data."""
    match_list = []

    for domain in sorted(integrations):
        match_types = integrations[domain].manifest.get("usb", [])

        if not match_types:
            continue

        match_list.extend(
            {
                "domain": domain,
                **{k: v for k, v in entry.items() if k != "known_devices"},
            }
            for entry in match_types
        )

    return format_python_namespace({"USB": match_list})


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate usb file."""
    usb_path = config.root / "homeassistant/generated/usb.py"
    config.cache["usb"] = content = generate_and_validate(integrations)

    if config.specific_integrations:
        return

    with open(str(usb_path)) as fp:
        current = fp.read()
        if current != content:
            config.add_error(
                "usb",
                "File usb.py is not up to date. Run python3 -m script.hassfest",
                fixable=True,
            )
        return


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate usb file."""
    usb_path = config.root / "homeassistant/generated/usb.py"
    with open(str(usb_path), "w") as fp:
        fp.write(f"{config.cache['usb']}")
