"""The ezbeq Profile Loader integration."""

from __future__ import annotations

import logging

from httpx import HTTPStatusError, RequestError
from pyezbeq.consts import DEFAULT_PORT, DISCOVERY_ADDRESS
from pyezbeq.errors import BEQProfileNotFound
from pyezbeq.ezbeq import EzbeqClient
from pyezbeq.models import SearchRequest
from pyezbeq.utils import convert_jellyfin_to_plex_format, map_audio_codec

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_CODEC_EXTENDED_SENSOR,
    CONF_CODEC_SENSOR,
    CONF_EDITION_SENSOR,
    CONF_JELLYFIN_CODEC_SENSOR,
    CONF_JELLYFIN_DISPLAY_TITLE_SENSOR,
    CONF_JELLYFIN_LAYOUT_SENSOR,
    CONF_JELLYFIN_PROFILE_SENSOR,
    CONF_PREFERRED_AUTHOR,
    CONF_SOURCE_MEDIA_PLAYER,
    CONF_SOURCE_TYPE,
    CONF_TITLE_SENSOR,
    CONF_TMDB_SENSOR,
    CONF_YEAR_SENSOR,
)
from .coordinator import EzbeqCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type EzBEQConfigEntry = ConfigEntry[EzbeqCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EzBEQConfigEntry) -> bool:
    """Set up ezbeq Profile Loader from a config entry."""
    _LOGGER.debug("Setting up ezbeq from a config entry")
    host = entry.data.get(CONF_HOST, DISCOVERY_ADDRESS)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)

    client = EzbeqClient(host=host, port=port)
    coordinator = EzbeqCoordinator(hass, client)

    await coordinator.async_config_entry_first_refresh()

    @callback
    def handle_sensor_change(event):
        """Handle changes in the watched sensor."""
        new_state = event.data.get("new_state")
        _LOGGER.debug("Sensor change: %s", new_state)
        if new_state is None:
            _LOGGER.debug("No new state")
            return

        hass.async_create_task(process_state_change(coordinator))

    async def process_state_change(coordinator: EzbeqCoordinator):
        """Process the state change and interact with ezbeq."""
        tmdb = hass.states.get(entry.data[CONF_TMDB_SENSOR])
        year = hass.states.get(entry.data[CONF_YEAR_SENSOR])
        # edition won't always be found, that's expected
        edition = hass.states.get(entry.data[CONF_EDITION_SENSOR])
        title = hass.states.get(entry.data[CONF_TITLE_SENSOR])
        preferred_author = entry.data.get(CONF_PREFERRED_AUTHOR, "")
        codec = ""
        codec_extended = ""

        # if JF, use the other sensor types
        if entry.data[CONF_SOURCE_TYPE] == "Jellyfin":
            jf_codec = hass.states.get(entry.data[CONF_JELLYFIN_CODEC_SENSOR])
            display_title = hass.states.get(
                entry.data[CONF_JELLYFIN_DISPLAY_TITLE_SENSOR]
            )
            profile = hass.states.get(entry.data[CONF_JELLYFIN_PROFILE_SENSOR])
            layout = hass.states.get(entry.data[CONF_JELLYFIN_LAYOUT_SENSOR])

            # normalize the data to plex
            assert jf_codec is not None
            assert display_title is not None
            assert profile is not None
            assert layout is not None

            codec, codec_extended = convert_jellyfin_to_plex_format(
                jf_codec.state, display_title.state, profile.state, layout.state
            )

        else:
            ha_codec = hass.states.get(entry.data[CONF_CODEC_SENSOR])
            if ha_codec:
                codec = ha_codec.state
            ha_codec_extended = hass.states.get(entry.data[CONF_CODEC_EXTENDED_SENSOR])
            if ha_codec_extended:
                codec_extended = ha_codec_extended.state

        _LOGGER.debug(
            "tmdb: %s, year: %s, codec: %s, codec_extended: %s, edition: %s, title: %s",
            tmdb,
            year,
            codec,
            codec_extended,
            edition,
            title,
        )
        # Check if all sensors are available
        if None not in (tmdb, year, codec, codec_extended, edition, title):
            _LOGGER.warning("Not all required sensors are available")
            return

        # Get BEQ mapped codec
        mapped_codec = map_audio_codec(codec, codec_extended)

        # Create search request
        assert tmdb is not None
        assert year is not None
        assert edition is not None
        assert title is not None

        search_request = SearchRequest(
            tmdb=tmdb.state,
            year=int(year.state) if year.state.isdigit() else 0,
            codec=mapped_codec,
            preferred_author=preferred_author,
            edition=edition.state,
            title=title.state,
            # eventually support media_type if its needed
        )
        source_status = hass.data.get(entry.data[CONF_SOURCE_MEDIA_PLAYER])
        if source_status == "playing":
            try:
                # check if CONF_SOURCE_MEDIA_PLAYER is playing
                await coordinator.client.load_beq_profile(search_request)
            except (
                ValueError,
                BEQProfileNotFound,
                HTTPStatusError,
                RequestError,
            ) as e:  # ValueError BEQProfileNotFound HTTPStatusError, RequestError
                _LOGGER.error("Failed to interact with BEQ profile: %s", str(e))
        elif source_status in ("idle", "paused"):
            try:
                await coordinator.client.unload_beq_profile(search_request)
            except (
                ValueError,
                BEQProfileNotFound,
                HTTPStatusError,
                RequestError,
            ) as e:  # ValueError BEQProfileNotFound HTTPStatusError, RequestError
                _LOGGER.error("Failed to interact with BEQ profile: %s", str(e))

        await coordinator.async_request_refresh()

    # Listen for changes in the watched sensor
    sensors_to_watch = [
        entry.data[CONF_TMDB_SENSOR],
        entry.data[CONF_YEAR_SENSOR],
        entry.data[CONF_CODEC_SENSOR],
        entry.data[CONF_EDITION_SENSOR],
        entry.data[CONF_TITLE_SENSOR],
    ]

    unsub = async_track_state_change_event(hass, sensors_to_watch, handle_sensor_change)

    entry.async_on_unload(unsub)
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Finished setting up ezbeq from a config entry")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EzBEQConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading ezbeq config entry")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = entry.runtime_data
        await coordinator.client.client.aclose()
    return unload_ok
