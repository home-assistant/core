"""Generate dhcp file."""

from __future__ import annotations

from .model import Config, Integration
from .serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration]) -> str:
    """Validate and generate dhcp data."""
    match_list = []

    for domain in sorted(integrations):
        match_types = integrations[domain].manifest.get("dhcp", [])

        if not match_types:
            continue

        match_list.extend({"domain": domain, **entry} for entry in match_types)

    return format_python_namespace(
        {"DHCP": match_list},
        annotations={"DHCP": "list[dict[str, str | bool]]"},
    )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate dhcp file."""
    dhcp_path = config.root / "homeassistant/generated/dhcp.py"
    config.cache["dhcp"] = content = generate_and_validate(integrations)

    if config.specific_integrations:
        return

    with open(str(dhcp_path)) as fp:
        current = fp.read()
        if current != content:
            config.add_error(
                "dhcp",
                "File dhcp.py is not up to date. Run python3 -m script.hassfest",
                fixable=True,
            )
        return


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate dhcp file."""
    dhcp_path = config.root / "homeassistant/generated/dhcp.py"
    with open(str(dhcp_path), "w") as fp:
        fp.write(f"{config.cache['dhcp']}")
