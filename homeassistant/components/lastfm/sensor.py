"""Sensor for Last.fm account status."""
from __future__ import annotations

import hashlib

from pylast import LastFMNetwork, PyLastError, Track, User
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

from .const import (
    ATTR_LAST_PLAYED,
    ATTR_PLAY_COUNT,
    ATTR_TOP_PLAYED,
    CONF_USERS,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER,
    STATE_NOT_SCROBBLING,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_USERS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)


def format_track(track: Track) -> str:
    """Format the track."""
    return f"{track.artist} - {track.title}"


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

    lastfm_api = LastFMNetwork(api_key=entry.options[CONF_API_KEY])
    async_add_entities(
        (
            LastFmSensor(lastfm_api.get_user(user), entry.entry_id)
            for user in entry.options[CONF_USERS]
        ),
        True,
    )


class LastFmSensor(SensorEntity):
    """A class for the Last.fm account."""

    _attr_attribution = "Data provided by Last.fm"
    _attr_icon = "mdi:radio-fm"

    def __init__(self, user: User, entry_id: str) -> None:
        """Initialize the sensor."""
        self._user = user
        self._attr_unique_id = hashlib.sha256(user.name.encode("utf-8")).hexdigest()
        self._attr_name = user.name
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.last.fm",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{entry_id}_{self._attr_unique_id}")},
            manufacturer=DEFAULT_NAME,
            name=f"{DEFAULT_NAME} {user.name}",
        )

    def update(self) -> None:
        """Update device state."""
        self._attr_native_value = STATE_NOT_SCROBBLING
        try:
            play_count = self._user.get_playcount()
            self._attr_entity_picture = self._user.get_image()
            now_playing = self._user.get_now_playing()
            top_tracks = self._user.get_top_tracks(limit=1)
            last_tracks = self._user.get_recent_tracks(limit=1)
        except PyLastError as exc:
            self._attr_available = False
            LOGGER.error("Failed to load LastFM user `%s`: %r", self._user.name, exc)
            return
        self._attr_available = True
        if now_playing:
            self._attr_native_value = format_track(now_playing)
        self._attr_extra_state_attributes = {
            ATTR_PLAY_COUNT: play_count,
            ATTR_LAST_PLAYED: None,
            ATTR_TOP_PLAYED: None,
        }
        if len(last_tracks) > 0:
            self._attr_extra_state_attributes[ATTR_LAST_PLAYED] = format_track(
                last_tracks[0].track
            )
        if len(top_tracks) > 0:
            self._attr_extra_state_attributes[ATTR_TOP_PLAYED] = format_track(
                top_tracks[0].item
            )
