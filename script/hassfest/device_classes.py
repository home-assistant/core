"""Generate the device_classes.json file."""

import json
import re

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.button import ButtonDeviceClass
from homeassistant.components.cover.const import CoverDeviceClass
from homeassistant.components.event import EventDeviceClass
from homeassistant.components.humidifier import HumidifierDeviceClass
from homeassistant.components.image_processing import ImageProcessingDeviceClass
from homeassistant.components.infrared.entity import InfraredDeviceClass
from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.components.number.const import NumberDeviceClass
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.components.update import UpdateDeviceClass
from homeassistant.components.valve.const import ValveDeviceClass

from .model import Config, Integration

PATH = "homeassistant/generated/device_classes.json"

DEVICE_CLASS_ENUMS = {
    "binary_sensor": BinarySensorDeviceClass,
    "button": ButtonDeviceClass,
    "cover": CoverDeviceClass,
    "event": EventDeviceClass,
    "humidifier": HumidifierDeviceClass,
    "image_processing": ImageProcessingDeviceClass,
    "infrared": InfraredDeviceClass,
    "media_player": MediaPlayerDeviceClass,
    "number": NumberDeviceClass,
    "sensor": SensorDeviceClass,
    "switch": SwitchDeviceClass,
    "update": UpdateDeviceClass,
    "valve": ValveDeviceClass,
}

DEVICE_CLASS_ENUM_DEFINITION = re.compile(
    r"^class \w*DeviceClass\(StrEnum\)", re.MULTILINE
)


def find_undeclared_domains(integrations: dict[str, Integration]) -> set[str]:
    """Return entity domains defining a device class enum but missing above."""
    return {
        domain
        for domain, integration in integrations.items()
        if domain not in DEVICE_CLASS_ENUMS
        and integration.manifest.get("integration_type") == "entity"
        and any(
            DEVICE_CLASS_ENUM_DEFINITION.search(path.read_text(encoding="utf-8"))
            for path in integration.path.rglob("*.py")
        )
    }


def _generate() -> str:
    """Generate the device class data."""
    device_classes = {
        domain: sorted(device_class.value for device_class in enum)
        for domain, enum in sorted(DEVICE_CLASS_ENUMS.items())
    }
    return json.dumps({"device_classes": device_classes}, indent=2)


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate device_classes.json."""
    if undeclared := find_undeclared_domains(integrations):
        config.add_error(
            "device_classes",
            f"Add {', '.join(sorted(undeclared))} to DEVICE_CLASS_ENUMS in"
            " script/hassfest/device_classes.py",
        )

    path = config.root / PATH
    config.cache["device_classes"] = content = _generate()

    if path.read_text() != content + "\n":
        config.add_error(
            "device_classes",
            "File device_classes.json is not up to date. Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate device_classes.json."""
    path = config.root / PATH
    path.write_text(f"{config.cache['device_classes']}\n")
