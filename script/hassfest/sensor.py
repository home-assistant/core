"""Generate the sensor.json file."""

import json

from homeassistant.components.sensor.const import (
    NON_NUMERIC_DEVICE_CLASSES,
    SensorDeviceClass,
)

from .model import Config, Integration

PATH = "homeassistant/generated/sensor.json"


def _generate() -> str:
    """Generate the sensor data."""
    numeric_device_classes = sorted(
        device_class.value
        for device_class in set(SensorDeviceClass) - NON_NUMERIC_DEVICE_CLASSES
    )
    return json.dumps({"numeric_device_classes": numeric_device_classes}, indent=2)


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate sensor.json."""
    path = config.root / PATH
    config.cache["sensor"] = content = _generate()

    if path.read_text() != content + "\n":
        config.add_error(
            "sensor",
            "File sensor.json is not up to date. Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate sensor.json."""
    path = config.root / PATH
    path.write_text(f"{config.cache['sensor']}\n")
