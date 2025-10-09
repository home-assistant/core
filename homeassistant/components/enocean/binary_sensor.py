"""Support for EnOcean binary sensors."""

from __future__ import annotations

from enocean.utils import from_hex_string, to_hex_string
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.config_entries import _LOGGER, ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ID, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .config_flow import CONF_ENOCEAN_DEVICE_TYPE_ID, CONF_ENOCEAN_DEVICES
from .entity import EnOceanEntity
from .importer import (
    EnOceanPlatformConfig,
    register_platform_config_for_migration_to_config_entry,
)
from .supported_device_type import (
    EnOceanSupportedDeviceType,
    get_supported_enocean_device_types,
)

DEFAULT_NAME = ""
DEPENDENCIES = ["enocean"]
EVENT_BUTTON_PRESSED = "button_pressed"

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Binary Sensor platform for EnOcean."""
    register_platform_config_for_migration_to_config_entry(
        EnOceanPlatformConfig(platform=Platform.BINARY_SENSOR, config=config)
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""

    # config_entry.options.get(CONF_DEVICE)
    async_add_entities(
        [
            EnOceanBinarySensor(
                dev_id=from_hex_string("00:00:00:00"),
                dev_name="Gateway",
                name="Teach-In Active",
                dev_type=EnOceanSupportedDeviceType(
                    manufacturer="EnOcean", model="TCM300/310 Transmitter", eep=""
                ),
            )
        ]
    )

    devices = config_entry.options.get(CONF_ENOCEAN_DEVICES, [])

    for device in devices:
        device_type_id = device[CONF_ENOCEAN_DEVICE_TYPE_ID]
        device_type = get_supported_enocean_device_types()[device_type_id]
        eep = device_type.eep

        if eep in ["F6-02-01", "F6-02-02"]:
            device_id = from_hex_string(device["id"])

            async_add_entities(
                [
                    EnOceanBinarySensor(
                        dev_id=device_id,
                        dev_name=device["name"],
                        channel=channel,
                        dev_type=device_type,
                        name="Button " + channel,
                    )
                    for channel in ("A0", "A1", "B0", "B1")
                ]
            )


class EnOceanBinarySensor(EnOceanEntity, BinarySensorEntity):
    """Representation of EnOcean binary sensors such as wall switches.

    Supported EEPs (EnOcean Equipment Profiles):
    - F6-02-01 (Light and Blind Control - Application Style 2)
    - F6-02-02 (Light and Blind Control - Application Style 1)
    """

    def __init__(
        self,
        dev_id,
        dev_name,
        device_class=Platform.BINARY_SENSOR,
        channel=None,
        dev_type: EnOceanSupportedDeviceType = EnOceanSupportedDeviceType(),
        name=None,
    ) -> None:
        """Initialize the EnOcean binary sensor."""
        super().__init__(dev_id, dev_name, dev_type, name)
        self._device_class = device_class
        self.which = -1
        self.onoff = -1
        self._attr_unique_id = (
            f"{to_hex_string(dev_id).upper()}-{device_class}-{channel}"
        )
        self._attr_on = True

        self._attr_should_poll = False

        self._channel = channel

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    # def is_on(self):
    #     """Return true if the binary sensor is on."""
    #     return self._attr_on

    def value_changed(self, packet):
        """Fire an event with the data that have changed.

        This method is called when there is an incoming packet associated
        with this platform.

        Example packet data:
        - 2nd button pressed
            ['0xf6', '0x10', '0x00', '0x2d', '0xcf', '0x45', '0x30']
        - button released
            ['0xf6', '0x00', '0x00', '0x2d', '0xcf', '0x45', '0x20']
        """
        # Energy Bow
        pushed = None

        if packet.data[6] == 0x30:
            pushed = 1
        elif packet.data[6] == 0x20:
            pushed = 0

        action = packet.data[1]
        if action == 0x70:
            self.which = 0
            self.onoff = 0
            if self._channel == "A0":
                self._attr_on = True
                _LOGGER.info("Button A0 pressed")
        elif action == 0x50:
            self.which = 0
            self.onoff = 1
            if self._channel == "A1":
                self._attr_on = True
                _LOGGER.info("Button A1 pressed")
        elif action == 0x30:
            self.which = 1
            self.onoff = 0
            if self._channel == "B0":
                self._attr_on = True
                _LOGGER.info("Button B0 pressed")
        elif action == 0x10:
            self.which = 1
            self.onoff = 1
            if self._channel == "B1":
                self._attr_on = True
                _LOGGER.info("Button B1 pressed")
        elif action == 0x37:
            self.which = 10
            self.onoff = 0
        elif action == 0x15:
            self.which = 10
            self.onoff = 1
        elif action == 0x00:
            self._attr_on = False
            _LOGGER.info("Button released")
        else:
            _LOGGER.warning("Unknown action: %s", action)

        self.schedule_update_ha_state()

        self.hass.bus.fire(
            EVENT_BUTTON_PRESSED,
            {
                "id": self.dev_id,
                "pushed": pushed,
                "which": self.which,
                "onoff": self.onoff,
            },
        )
