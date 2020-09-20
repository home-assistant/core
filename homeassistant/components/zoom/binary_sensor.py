"""Binary sensor platform for Zoom."""
from datetime import timedelta
from logging import getLogger
from typing import Any, Dict, List, Optional

from aiohttp.web import HTTPException, HTTPUnauthorized

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import Event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import slugify

from .api import ZoomAPI
from .common import get_contact_name
from .const import (
    API,
    ATTR_EVENT,
    CONNECTIVITY_EVENT,
    CONNECTIVITY_ID,
    CONNECTIVITY_STATUS,
    CONNECTIVITY_STATUS_ON,
    DOMAIN,
    HA_ZOOM_EVENT,
)

_LOGGER = getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)
PARALLEL_UPDATES = 5


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up a Zoom presence sensor entry."""
    entity = ZoomAuthenticatedUserBinarySensor(hass, config_entry)
    async_add_entities([entity], update_before_add=True)


def get_data_from_path(data: Dict[str, Any], path: List[str]) -> Optional[str]:
    """Get value from dictionary using path list."""
    for val in path:
        data = data.get(val, {})

    if isinstance(data, str):
        return data
    return None


class ZoomBaseBinarySensor(BinarySensorEntity):
    """Base class for Zoom binary_sensor."""

    def __init__(self, hass: HomeAssistantType, config_entry: ConfigEntry) -> None:
        """Initialize base sensor."""
        self._config_entry = config_entry
        self._hass = hass
        self._api: ZoomAPI = hass.data[DOMAIN][config_entry.entry_id][API]
        self._name: str = config_entry.data[CONF_NAME]
        self._profile = None
        self._zoom_event_state = None
        self._state = STATE_OFF
        self._should_poll = True

    async def async_update(self) -> None:
        """Update state of entity."""
        try:
            self._profile = await self._api.async_get_contact_user_profile(self.id)
            self._set_state(self._profile["presence_status"])
        except HTTPUnauthorized:
            _LOGGER.warning(
                "Unable to poll presence status for user %s. Relying solely on webhooks.",
                self.profile["email"],
            )
            self._should_poll = False

    def _set_state(self, zoom_event_state: Optional[str]) -> None:
        """Set Zoom and HA state."""
        self._zoom_event_state = zoom_event_state
        self._state = (
            STATE_ON
            if self._zoom_event_state
            and self._zoom_event_state.lower() == CONNECTIVITY_STATUS_ON.lower()
            else STATE_OFF
        )
        _LOGGER.debug(
            "Set Zoom state to %s and HA state to %s", zoom_event_state, self._state
        )

    @property
    def name(self) -> str:
        """Entity name."""
        raise NotImplementedError

    @property
    def state(self) -> str:
        """Entity state."""
        return self._state

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.state == STATE_ON

    @property
    def icon(self) -> str:
        """Entity icon."""
        if self.is_on:
            return "mdi:video"
        return "mdi:video-off"

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_CONNECTIVITY

    @property
    def profile(self) -> Optional[Dict[str, str]]:
        """Get user profile."""
        return self._profile

    @property
    def first_name(self) -> Optional[str]:
        """Return the first name."""
        return self.profile.get("first_name")

    @property
    def last_name(self) -> Optional[str]:
        """Return the last name."""
        return self.profile.get("last_name")

    @property
    def id(self) -> Optional[str]:
        """Return the id."""
        self.profile.get("id")

    @property
    def email(self) -> Optional[str]:
        """Return the email."""
        return self.profile.get("email")

    @property
    def account_id(self) -> Optional[str]:
        """Return the account_id."""
        return self.profile.get("account_id")

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return additional state attributes."""
        data = {}

        for prop in ["id", "first_name", "last_name", "email", "account_id"]:
            val = getattr(self, prop)
            if val:
                data[prop] = val

        if self._zoom_event_state:
            data["status"] = self._zoom_event_state

        return data if data else None

    @property
    def unique_id(self) -> str:
        """Return unique_id for entity."""
        return f"{DOMAIN}_{slugify(self._name)}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return self._should_poll


class ZoomAuthenticatedUserBinarySensor(RestoreEntity, ZoomBaseBinarySensor):
    """Class for Zoom user profile binary sensor for authenticated user."""

    async def async_event_received(self, event: Event) -> None:
        """Update status if event received for this entity."""
        if (
            event.data[ATTR_EVENT] == CONNECTIVITY_EVENT
            and get_data_from_path(event.data, CONNECTIVITY_ID).lower()
            == self.id.lower()
        ):
            self._set_state(get_data_from_path(event.data, CONNECTIVITY_STATUS))
            self.async_write_ha_state()

    async def _restore_state(self) -> None:
        """Restore state from last known state."""
        restored_state = await self.async_get_last_state()
        if restored_state:
            self._state = restored_state.state

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        await super().async_added_to_hass()

        # Register callback for webhook event
        self.async_on_remove(
            self.hass.bus.async_listen(HA_ZOOM_EVENT, self.async_event_received)
        )

        if not self.id:
            _LOGGER.debug("ID not found, restoring state.")
            await self._restore_state()

        try:
            contact = await self._api.async_get_contact_user_profile(self.id)
            status = contact["presence_status"]
            _LOGGER.debug("Retrieved initial Zoom status: %s", status)
            self._set_state(status)
            self.async_write_ha_state()
        except HTTPUnauthorized:
            _LOGGER.debug(
                "User is unauthorized to query presence status, restoring state.",
                exc_info=True,
            )
            await self._restore_state()
        except HTTPException:
            _LOGGER.warning(
                "Error retrieving initial zoom status, restoring state.", exc_info=True
            )
            await self._restore_state()

    @property
    def profile(self) -> Optional[Dict[str, str]]:
        """Get user profile."""
        return self.profile

    @property
    def name(self) -> str:
        """Entity name."""
        return f"Zoom - {get_contact_name(self.profile)}"
