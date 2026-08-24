"""Generate the sensor.json file."""

import json

from homeassistant.components.sensor import (
    DEVICE_CLASS_UNITS,
    NON_NUMERIC_DEVICE_CLASSES,
    STATE_CLASS_UNITS,
    UNIT_CONVERTERS,
    SensorDeviceClass,
    SensorStateClass,
)

from .model import Config, Integration

PATH = "homeassistant/generated/sensor.json"


def _generate() -> str:
    """Generate the sensor data."""
    numeric_device_classes = sorted(
        device_class.value
        for device_class in set(SensorDeviceClass) - NON_NUMERIC_DEVICE_CLASSES
    )
    device_class_units = {
        device_class: sorted(units, key=lambda u: (str.casefold(str(u)), u or ""))
        for device_class, units in DEVICE_CLASS_UNITS.items()
    }
    convertible_units = {
        device_class: sorted(
            DEVICE_CLASS_UNITS[device_class],
            key=lambda u: (str.casefold(str(u)), u or ""),
        )
        for device_class in numeric_device_classes
        if device_class in UNIT_CONVERTERS and device_class in DEVICE_CLASS_UNITS
    }
    state_classes = sorted(state_class.value for state_class in SensorStateClass)
    state_class_units = {
        state_class: sorted(units, key=lambda u: (str.casefold(str(u)), u or ""))
        for state_class, units in STATE_CLASS_UNITS.items()
    }
    return json.dumps(
        {
            "convertible_units": convertible_units,
            "device_class_units": device_class_units,
            "numeric_device_classes": numeric_device_classes,
            "state_class_units": state_class_units,
            "state_classes": state_classes,
        },
        indent=2,
    )


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
