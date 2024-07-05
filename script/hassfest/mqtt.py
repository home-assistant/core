"""Generate MQTT file."""

from __future__ import annotations

from collections import defaultdict

from .model import Config, Integration
from .serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration]) -> str:
    """Validate and generate MQTT data."""

    data = defaultdict(list)

    for domain in sorted(integrations):
        mqtt = integrations[domain].manifest.get("mqtt")

        if not mqtt:
            continue

        for topic in mqtt:
            data[domain].append(topic)

    return format_python_namespace({"MQTT": data})


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate MQTT file."""
    mqtt_path = config.root / "homeassistant/generated/mqtt.py"
    config.cache["mqtt"] = content = generate_and_validate(integrations)

    if config.specific_integrations:
        return

    with open(str(mqtt_path)) as fp:
        if fp.read() != content:
            config.add_error(
                "mqtt",
                "File mqtt.py is not up to date. Run python3 -m script.hassfest",
                fixable=True,
            )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate MQTT file."""
    mqtt_path = config.root / "homeassistant/generated/mqtt.py"
    with open(str(mqtt_path), "w") as fp:
        fp.write(f"{config.cache['mqtt']}")
