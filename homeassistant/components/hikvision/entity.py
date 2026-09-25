"""Base entity for Hikvision integration."""

from typing import override

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import HikvisionConfigEntry
from .const import DOMAIN


class HikvisionEntity(Entity):
    """Base class for Hikvision entities."""

    _attr_has_entity_name = True

    # pyhik routes an update to the callbacks registered under this exact
    # identifier and passes it back as the callback message. It also
    # broadcasts to every registered callback when the event stream
    # connects or drops, which is what drives availability.
    _callback_id: str

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HikvisionConfigEntry,
        channel: int,
    ) -> None:
        """Initialize the entity."""
        super().__init__()
        self._data = entry.runtime_data
        self._camera = self._data.camera
        self._channel = channel

        if self._data.device_type == "NVR":
            # NVR channels get their own device linked to the NVR via via_device_id
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{self._data.device_id}_{channel}")},
                via_device_id=dr.async_get_device_id_by_identifier(
                    hass, (DOMAIN, self._data.device_id), config_entry_id=entry.entry_id
                ),
                translation_key="nvr_channel",
                translation_placeholders={
                    "device_name": self._data.device_name,
                    "channel_number": str(channel),
                },
                manufacturer="Hikvision",
                model="NVR channel",
            )
        else:
            # Single camera device
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self._data.device_id)},
                name=self._data.device_name,
                manufacturer="Hikvision",
                model=self._data.device_type,
            )

    @property
    @override
    def available(self) -> bool:
        """Return true if the device's event stream is connected."""
        return self._camera.stream_connected

    @override
    async def async_added_to_hass(self) -> None:
        """Register callback when entity is added, and drop it on removal."""
        await super().async_added_to_hass()

        self._camera.add_update_callback(self._update_callback, self._callback_id)
        self.async_on_remove(
            lambda: self._camera.remove_update_callback(
                self._update_callback, self._callback_id
            )
        )

    def _update_callback(self, msg: str) -> None:
        """Update the entity state when the callback is triggered.

        This is called from pyhik event stream thread, so we use
        schedule_update_ha_state which is thread-safe.
        """
        self.schedule_update_ha_state()
