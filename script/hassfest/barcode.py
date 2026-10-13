"""Generate barcode file."""

from .model import Config, Integration
from .serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration]) -> str:
    """Validate and generate barcode data."""
    match_list = []

    for domain in sorted(integrations):
        integration = integrations[domain]
        match_types = integration.manifest.get("barcode", [])

        if not match_types:
            continue

        if not integration.config_flow:
            integration.add_error(
                "barcode", "Integrations with barcode matchers need a config flow"
            )
            continue

        match_list.extend({"domain": domain, **entry} for entry in match_types)

    return format_python_namespace({"BARCODE": match_list})


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate barcode file."""
    barcode_path = config.root / "homeassistant/generated/barcode.py"
    config.cache["barcode"] = content = generate_and_validate(integrations)

    if config.specific_integrations:
        return

    if barcode_path.read_text() != content:
        config.add_error(
            "barcode",
            "File barcode.py is not up to date. Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate barcode file."""
    barcode_path = config.root / "homeassistant/generated/barcode.py"
    barcode_path.write_text(f"{config.cache['barcode']}")
