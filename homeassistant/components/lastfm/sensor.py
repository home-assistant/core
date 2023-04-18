"""Sensor for Last.fm account status."""
from __future__ import annotations

import hashlib
import logging

from pylast import WSError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_LAST_PLAYED, ATTR_PLAY_COUNT, ATTR_TOP_PLAYED, CONF_USERS
from .coordinator import LastFmUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_USERS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Last.fm sensor platform."""
    coordinator = LastFmUpdateCoordinator(hass, config)
    try:
        await coordinator.async_refresh()
    except WSError as exc:
        raise PlatformNotReady from exc
    async_add_entities(
        (LastFmSensor(coordinator, user) for user in config[CONF_USERS]), True
    )


class LastFmSensor(CoordinatorEntity[LastFmUpdateCoordinator], SensorEntity):
    """A class for the Last.fm account."""

    _attr_attribution = "Data provided by Last.fm"
    _attr_icon = "mdi:radio-fm"

    def __init__(self, coordinator: LastFmUpdateCoordinator, user: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = hashlib.sha256(user.encode("utf-8")).hexdigest()
        self._attr_name = f"lastfm_{user}"
        self._user = user

    @callback
    def _handle_coordinator_update(self) -> None:
        if user_data := self.coordinator.data.get(self._user):
            self._attr_entity_picture = user_data.image
            self._attr_native_value = user_data.now_playing
            self._attr_extra_state_attributes = {
                ATTR_LAST_PLAYED: user_data.last_played,
                ATTR_PLAY_COUNT: user_data.play_count,
                ATTR_TOP_PLAYED: user_data.top_played,
            }
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self._handle_coordinator_update()
        await super().async_added_to_hass()
