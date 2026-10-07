"""Generate usb file."""

from .model import Config, Integration
from .serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration]) -> str:
    """Validate and generate usb data."""
    match_list = []
    dependents = []

    for domain in sorted(integrations):
        manifest = integrations[domain].manifest

        dependencies = {
            *manifest.get("dependencies", []),
            *manifest.get("after_dependencies", []),
        }

        if "usb" in dependencies:
            dependents.append(domain)

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

    return format_python_namespace({"USB": match_list, "USB_DEPENDENTS": dependents})


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
