"""Sensor for Last.fm account status."""
from __future__ import annotations

import hashlib
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import (
    ATTR_LAST_PLAYED,
    ATTR_PLAY_COUNT,
    ATTR_TOP_PLAYED,
    CONF_USERS,
    DEFAULT_NAME,
    DOMAIN,
    STATE_NOT_SCROBBLING,
)
from .coordinator import LastFMDataUpdateCoordinator, LastFMUserData

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
    """Set up the Last.fm sensor platform from yaml."""

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2023.12.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "LastFM",
        },
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize the entries."""

    coordinator: LastFMDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        (
            LastFmSensor(coordinator, username, entry.entry_id)
            for username in entry.options[CONF_USERS]
        ),
    )


class LastFmSensor(CoordinatorEntity[LastFMDataUpdateCoordinator], SensorEntity):
    """A class for the Last.fm account."""

    _attr_attribution = "Data provided by Last.fm"
    _attr_icon = "mdi:radio-fm"

    def __init__(
        self,
        coordinator: LastFMDataUpdateCoordinator,
        username: str,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._username = username
        self._attr_unique_id = hashlib.sha256(username.encode("utf-8")).hexdigest()
        self._attr_name = username
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.last.fm",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{entry_id}_{self._attr_unique_id}")},
            manufacturer=DEFAULT_NAME,
            name=f"{DEFAULT_NAME} {username}",
        )

    @property
    def user_data(self) -> LastFMUserData | None:
        """Returns the user from the coordinator."""
        return self.coordinator.data.get(self._username)

    @property
    def available(self) -> bool:
        """If user not found in coordinator, entity is unavailable."""
        return super().available and self.user_data is not None

    @property
    def entity_picture(self) -> str | None:
        """Return user avatar."""
        if self.user_data and self.user_data.image is not None:
            return self.user_data.image
        return None

    @property
    def native_value(self) -> str:
        """Return value of sensor."""
        if self.user_data and self.user_data.now_playing is not None:
            return self.user_data.now_playing
        return STATE_NOT_SCROBBLING

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return state attributes."""
        play_count = None
        last_track = None
        top_track = None
        if self.user_data:
            play_count = self.user_data.play_count
            last_track = self.user_data.last_track
            top_track = self.user_data.top_track
        return {
            ATTR_PLAY_COUNT: play_count,
            ATTR_LAST_PLAYED: last_track,
            ATTR_TOP_PLAYED: top_track,
        }
