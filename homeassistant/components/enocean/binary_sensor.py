"""Support for EnOcean binary sensors."""

from __future__ import annotations

from enocean.utils import from_hex_string, to_hex_string

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import _LOGGER, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_flow import CONF_ENOCEAN_DEVICE_TYPE_ID, CONF_ENOCEAN_DEVICES
from .const import DATA_ENOCEAN, ENOCEAN_DONGLE
from .entity import EnOceanEntity
from .supported_device_type import (
    EnOceanSupportedDeviceType,
    get_supported_enocean_device_types,
)

DEFAULT_NAME = ""
DEPENDENCIES = ["enocean"]
EVENT_BUTTON_PRESSED = "button_pressed"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""

    # config_entry.options.get(CONF_DEVICE)
    # enocean_dongle = hass.data[DATA_ENOCEAN][ENOCEAN_DONGLE]
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
                        name=channel,
                    )
                    for channel in ("A0", "A1", "B0", "B1", "AB0", "AB1")
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
        self._attr_on = False

        self._attr_should_poll = False

        self._channel = channel

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._attr_on

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
        elif action == 0x50:
            self.which = 0
            self.onoff = 1
            if self._channel == "A1":
                self._attr_on = True
        elif action == 0x30:
            self.which = 1
            self.onoff = 0
            if self._channel == "B0":
                self._attr_on = True
        elif action == 0x10:
            self.which = 1
            self.onoff = 1
            if self._channel == "B1":
                self._attr_on = True
        elif action == 0x37:
            self.which = 10
            self.onoff = 0
            if self._channel in ("A0", "B0", "AB0"):
                self._attr_on = True
                enocean_dongle = self.hass.data[DATA_ENOCEAN][ENOCEAN_DONGLE]
                _LOGGER.warning("Chip id: %s", enocean_dongle.chip_id)
        elif action == 0x15:
            self.which = 10
            self.onoff = 1
            if self._channel in ("A1", "B1", "AB1"):
                self._attr_on = True

        elif action == 0x17:
            self.which = 10
            self.onoff = 1
            if self._channel in ("A0", "B1"):
                self._attr_on = True

        elif action == 0x35:
            self.which = 10
            self.onoff = 1
            if self._channel in ("A1", "B0"):
                self._attr_on = True

        elif action == 0x00:
            self._attr_on = False
        else:
            _LOGGER.warning("Unknown action: %s", action)
            self._attr_on = False

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
