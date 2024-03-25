"""Representation of Denon AVR device entities."""

from denonavr import DenonAVR

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .config_flow import CONF_MANUFACTURER, CONF_TYPE, DOMAIN


class DenonDeviceEntity(Entity):
    """Representation of a Denon Device Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        receiver: DenonAVR,
        unique_id: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the device."""
        self._attr_unique_id = unique_id
        assert config_entry.unique_id
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{config_entry.data[CONF_HOST]}/",
            hw_version=config_entry.data[CONF_TYPE],
            identifiers={(DOMAIN, config_entry.unique_id)},
            manufacturer=config_entry.data[CONF_MANUFACTURER],
            model=config_entry.data[CONF_MODEL],
            name=receiver.name,
        )
        self._receiver = receiver
