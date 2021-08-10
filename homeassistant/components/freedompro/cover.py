"""Support for Freedompro cover."""
import json

from pyfreedompro import put_state

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_BLIND,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GARAGE,
    DEVICE_CLASS_GATE,
    DEVICE_CLASS_WINDOW,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

DEVICE_CLASS_MAP = {
    "windowCovering": DEVICE_CLASS_BLIND,
    "gate": DEVICE_CLASS_GATE,
    "garageDoor": DEVICE_CLASS_GARAGE,
    "door": DEVICE_CLASS_DOOR,
    "window": DEVICE_CLASS_WINDOW,
}

SUPPORTED_SENSORS = {"windowCovering", "gate", "garageDoor", "door", "window"}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro cover."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(hass, api_key, device, coordinator)
        for device in coordinator.data
        if device["type"] in SUPPORTED_SENSORS
    )


class Device(CoordinatorEntity, CoverEntity):
    """Representation of an Freedompro cover."""

    def __init__(self, hass, api_key, device, coordinator):
        """Initialize the Freedompro cover."""
        super().__init__(coordinator)
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._api_key = api_key
        self._attr_name = device["name"]
        self._attr_unique_id = device["uid"]
        self._attr_device_info = {
            "name": self.name,
            "identifiers": {
                (DOMAIN, self.unique_id),
            },
            "model": device["type"],
            "manufacturer": "Freedompro",
        }
        self._attr_current_cover_position = 0
        self._attr_is_closed = True
        self._attr_supported_features = (
            SUPPORT_CLOSE | SUPPORT_OPEN | SUPPORT_SET_POSITION
        )
        self._attr_device_class = DEVICE_CLASS_MAP[device["type"]]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = next(
            (
                device
                for device in self.coordinator.data
                if device["uid"] == self.unique_id
            ),
            None,
        )
        if device is not None and "state" in device:
            state = device["state"]
            if "position" in state:
                self._attr_current_cover_position = state["position"]
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
        await self.async_set_cover_position(position=100)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self.async_set_cover_position(position=0)

    async def async_set_cover_position(self, **kwargs):
        """Async function to set position to cover."""
        payload = {}
        payload["position"] = kwargs[ATTR_POSITION]
        payload = json.dumps(payload)
        await put_state(
            self._session,
            self._api_key,
            self.unique_id,
            payload,
        )
        await self.coordinator.async_request_refresh()
