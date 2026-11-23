"""Support for EnOcean binary sensors."""

from typing import override

from enocean_async.address import Address
from enocean_async.protocol.erp1.telegram import ERP1Telegram
import probatio

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ID, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import EnOceanConfigEntry
from .const import (
    CONF_DEVICE_TYPE_ID,
    DEVICE_TYPE_ROCKER_SWITCH,
    SIGNAL_DEVICE_ADDED,
    SUBENTRY_TYPE_DEVICE,
)
from .entity import EnOceanEntity, combine_hex
from .yaml_import import async_import_yaml_device

DEFAULT_NAME = "EnOcean binary sensor"
DEPENDENCIES = ["enocean"]
EVENT_BUTTON_PRESSED = "button_pressed"

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_ID): probatio.All(
            probatio.EnsureList(), [probatio.Coerce(int)]
        ),
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import a binary sensor configured in YAML into the config entry."""
    async_import_yaml_device(
        hass,
        Platform.BINARY_SENSOR,
        config[CONF_ID],
        config[CONF_NAME],
        DEVICE_TYPE_ROCKER_SWITCH,
        {CONF_DEVICE_CLASS: config[CONF_DEVICE_CLASS].value}
        if CONF_DEVICE_CLASS in config
        else {},
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors of the configured devices."""

    @callback
    def async_add_device(subentry: ConfigSubentry) -> None:
        """Add the binary sensor of a rocker switch."""
        if subentry.data[CONF_DEVICE_TYPE_ID] != DEVICE_TYPE_ROCKER_SWITCH:
            return
        device_class = subentry.data.get(CONF_DEVICE_CLASS)
        async_add_entities(
            [
                EnOceanBinarySensor(
                    Address(subentry.data[CONF_ID]).bytelist,
                    subentry.title,
                    BinarySensorDeviceClass(device_class) if device_class else None,
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )

    for subentry in config_entry.get_subentries_of_type(SUBENTRY_TYPE_DEVICE):
        async_add_device(subentry)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICE_ADDED, async_add_device)
    )


class EnOceanBinarySensor(EnOceanEntity, BinarySensorEntity):
    """Representation of EnOcean binary sensors such as wall switches.

    Supported EEPs (EnOcean Equipment Profiles):
    - F6-02-01 (Light and Blind Control - Application Style 2)
    - F6-02-02 (Light and Blind Control - Application Style 1)
    """

    def __init__(
        self,
        dev_id: list[int],
        dev_name: str,
        device_class: BinarySensorDeviceClass | None,
    ) -> None:
        """Initialize the EnOcean binary sensor."""
        super().__init__(dev_id)
        self._attr_device_class = device_class
        self.which = -1
        self.onoff = -1
        self._attr_unique_id = f"{combine_hex(dev_id)}-{device_class}"
        self._attr_name = dev_name

    @override
    def value_changed(self, telegram: ERP1Telegram) -> None:
        """Fire an event with the data that have changed.

        This method is called when there is an incoming packet associated
        with this platform.
        """
        if not self.address:
            return
        # Energy Bow
        pushed = None

        if telegram.status == 0x30:
            pushed = 1
        elif telegram.status == 0x20:
            pushed = 0

        self.schedule_update_ha_state()

        action = telegram.telegram_data[0]
        if action == 0x70:
            self.which = 0
            self.onoff = 0
        elif action == 0x50:
            self.which = 0
            self.onoff = 1
        elif action == 0x30:
            self.which = 1
            self.onoff = 0
        elif action == 0x10:
            self.which = 1
            self.onoff = 1
        elif action == 0x37:
            self.which = 10
            self.onoff = 0
        elif action == 0x15:
            self.which = 10
            self.onoff = 1
        self.hass.bus.fire(
            EVENT_BUTTON_PRESSED,
            {
                "id": self.address.bytelist,
                "pushed": pushed,
                "which": self.which,
                "onoff": self.onoff,
            },
        )
