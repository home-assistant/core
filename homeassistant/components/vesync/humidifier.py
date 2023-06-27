"""Support for VeSync humidifiers."""
import logging

from pyvesync.vesyncfan import VeSyncHumid200S, VeSyncHumid200300S

from homeassistant.components.humidifier import (
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.core import HomeAssistant, callback

from .common import VeSyncDevice
from .const import DOMAIN, SKU_TO_BASE_DEVICE, VS_DISCOVERY, VS_HUMIDIFIERS


from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

DEV_TYPE_TO_HA = {
    "LUH-A602S-WUS": "humidifier",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the VeSync fan platform."""

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_HUMIDIFIERS), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_HUMIDIFIERS], async_add_entities)


@callback
def _setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    entities = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(SKU_TO_BASE_DEVICE.get(dev.device_type)) == "humidifier":
            entities.append(VeSyncHumidifierHA(dev))
        else:
            _LOGGER.warning(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(entities, update_before_add=True)


class VeSyncHumidifierHA(VeSyncDevice, HumidifierEntity):
    """Representation of a VeSync humidifier."""

    _attr_supported_features = HumidifierEntityFeature.MODES

    def __init__(self, humidifier: VeSyncHumid200S | VeSyncHumid200300S) -> None:
        """Initialize the VeSync humidifier device."""
        super().__init__(humidifier)
        self.smartfan = humidifier

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on the humidifier"""
        self.smartfan.turn_on()

    def set_humidity(self, humidity: int) -> None:
        """Sets humidity"""
        self.smartfan.set_humidity(humidity)

    @property
    def target_humidity(self) -> int | None:
        """Gets humidity"""
        return self.smartfan.auto_humidity

    @property
    def available_modes(self) -> list[str] | None:
        """Gets available modes"""
        return self.smartfan.mist_modes

    @property
    def mode(self) -> str | None:
        """Gets current mode"""
        return self.smartfan.details["mode"]

    def set_mode(self, mode: str) -> None:
        """Sets modes"""
        self.smartfan.set_humidity_mode(mode)
