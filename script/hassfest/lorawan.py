"""Generate LoRaWAN file."""

from collections import defaultdict

from .model import Config, Integration
from .serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration]) -> str:
    """Validate and generate LoRaWAN data."""

    data = defaultdict(list)

    for domain in sorted(integrations):
        lorawan = integrations[domain].manifest.get("lorawan")

        if not lorawan:
            continue

        integration = integrations[domain]
        if "lorawan" not in integration.manifest.get("dependencies", []):
            integration.add_error(
                "lorawan", "LoRaWAN discovery requires a lorawan dependency"
            )
        if not integration.manifest.get("config_flow"):
            integration.add_error("lorawan", "LoRaWAN discovery requires a config flow")
        for stack, brand_id in lorawan:
            data[domain].append((stack, brand_id))

    return format_python_namespace(
        {"LORAWAN": data},
        annotations={"LORAWAN": "Final[dict[str, list[tuple[str, int | str]]]]"},
    )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate LoRaWAN file."""
    lorawan_path = config.root / "homeassistant/generated/lorawan.py"
    config.cache["lorawan"] = content = generate_and_validate(integrations)

    if config.specific_integrations:
        return

    if not lorawan_path.exists() or lorawan_path.read_text() != content:
        config.add_error(
            "lorawan",
            "File lorawan.py is not up to date. Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate LoRaWAN file."""
    lorawan_path = config.root / "homeassistant/generated/lorawan.py"
    lorawan_path.write_text(f"{config.cache['lorawan']}")
