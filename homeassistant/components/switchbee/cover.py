"""Support for SwitchBee cover."""
import switchbee

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

DEVICE_CLASS_MAP = {
    "SHUTTER": CoverDeviceClass.SHUTTER,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Freedompro switch."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    print(coordinator.data)
    async_add_entities(
        Device(hass, coordinator.data[device], coordinator)
        for device in coordinator.data
        if coordinator.data[device]["type"] == switchbee.TYPE_SHUTTER
    )


class Device(CoordinatorEntity, CoverEntity):
    """Representation of an Freedompro cover."""

    def __init__(self, hass, device, coordinator):
        """Initialize the Freedompro cover."""
        super().__init__(coordinator)
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._attr_name = device["name"]
        self._attr_unique_id = device["uid"]
        self._device_id = device[switchbee.ATTR_ID]
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, device["uid"]),
            },
            manufacturer="SwitchBee",
            model=device["type"],
            name=self.name,
        )
        self._attr_current_cover_position = 0
        self._attr_is_closed = True
        self._attr_supported_features = (
            CoverEntityFeature.CLOSE
            | CoverEntityFeature.OPEN
            | CoverEntityFeature.SET_POSITION
        )
        self._attr_device_class = DEVICE_CLASS_MAP[device["type"]]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        position = self.coordinator.data[self._device_id][switchbee.ATTR_STATE]
        if isinstance(position, str) and position == switchbee.STATE_OFF:
            self._attr_current_cover_position = 0
        elif isinstance(position, int):
            self._attr_current_cover_position = position

        if self._attr_current_cover_position == 0:
            self._attr_is_closed = True
        else:
            self._attr_is_closed = False
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        if self._attr_current_cover_position == 100:
            return
        await self.async_set_cover_position(position=100)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        if self._attr_current_cover_position == 0:
            return
        await self.async_set_cover_position(position=0)

    async def async_set_cover_position(self, **kwargs):
        """Async function to set position to cover."""
        if self._attr_current_cover_position == kwargs[ATTR_POSITION]:
            return
        await self.coordinator.api.set_state(self._device_id, kwargs[ATTR_POSITION])
        await self.coordinator.async_request_refresh()
