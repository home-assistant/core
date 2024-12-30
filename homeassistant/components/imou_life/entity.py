"""An abstract class common to all IMOU entities."""

from pyimouapi.ha_device import DeviceStatus, ImouHaDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ImouDataUpdateCoordinator
from .const import DOMAIN, PARAM_STATUS


class ImouEntity(CoordinatorEntity):
    """EntityBaseClass."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ImouDataUpdateCoordinator,
        config_entry: ConfigEntry,
        entity_type: str,
        device: ImouHaDevice,
    ) -> None:
        """Init ImouEntity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._entity_type = entity_type
        self._device = device
        self.entity_available = None
        self._unique_id = (
            self._device.device_id
            + "_"
            + self._device.channel_id
            + "#"
            + self._entity_type
        )
        self._attr_translation_key = entity_type

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # The combination of DeviceId and ChannelId uniquely identifies the device
                (DOMAIN, self._device.device_id + "_" + self._device.channel_id)
            },
            name=self._device.channel_name,
            manufacturer=self._device.manufacturer,
            model=self._device.model,
            sw_version=self._device.swversion,
            serial_number=self._device.device_id,
        )

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return self._unique_id

    @property
    def translation_key(self):
        """Return translation_key."""
        return self._attr_translation_key

    @property
    def available(self) -> bool:
        """Return entity is available."""
        if self._entity_type == PARAM_STATUS:
            return True
        return self._device.sensors[PARAM_STATUS] != DeviceStatus.OFFLINE.status
