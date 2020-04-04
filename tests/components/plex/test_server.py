"""Tests for Plex server."""
import copy
from datetime import timedelta

from asynctest import patch

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.plex.const import (
    CONF_IGNORE_NEW_SHARED_USERS,
    CONF_MONITORED_USERS,
    DEBOUNCE_TIMEOUT,
    DOMAIN,
    PLEX_UPDATE_PLATFORMS_SIGNAL,
    SERVERS,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
import homeassistant.util.dt as dt_util

from .common import trigger_plex_update
from .const import DEFAULT_DATA, DEFAULT_OPTIONS
from .mock_classes import MockPlexServer

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_new_users_available(hass):
    """Test setting up when new users available on Plex server."""

    MONITORED_USERS = {"Owner": {"enabled": True}}
    OPTIONS_WITH_USERS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS_WITH_USERS[MP_DOMAIN][CONF_MONITORED_USERS] = MONITORED_USERS

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=OPTIONS_WITH_USERS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    mock_plex_server = MockPlexServer(config_entry=entry)

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "homeassistant.components.plex.PlexWebsocket.listen"
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    server_id = mock_plex_server.machineIdentifier

    await trigger_plex_update(hass, server_id)

    monitored_users = hass.data[DOMAIN][SERVERS][server_id].option_monitored_users

    ignored_users = [x for x in monitored_users if not monitored_users[x]["enabled"]]
    assert len(monitored_users) == 1
    assert len(ignored_users) == 0

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))


async def test_new_ignored_users_available(hass, caplog):
    """Test setting up when new users available on Plex server but are ignored."""

    MONITORED_USERS = {"Owner": {"enabled": True}}
    OPTIONS_WITH_USERS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS_WITH_USERS[MP_DOMAIN][CONF_MONITORED_USERS] = MONITORED_USERS
    OPTIONS_WITH_USERS[MP_DOMAIN][CONF_IGNORE_NEW_SHARED_USERS] = True

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=OPTIONS_WITH_USERS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    mock_plex_server = MockPlexServer(config_entry=entry)

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "homeassistant.components.plex.PlexWebsocket.listen"
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    server_id = mock_plex_server.machineIdentifier

    await trigger_plex_update(hass, server_id)

    monitored_users = hass.data[DOMAIN][SERVERS][server_id].option_monitored_users

    ignored_users = [x for x in mock_plex_server.accounts if x not in monitored_users]
    assert len(monitored_users) == 1
    assert len(ignored_users) == 2
    for ignored_user in ignored_users:
        assert f"Ignoring Plex client owned by {ignored_user}" in caplog.text

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))


async def test_mark_sessions_idle(hass):
    """Test marking media_players as idle when sessions end."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    mock_plex_server = MockPlexServer(config_entry=entry)

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "homeassistant.components.plex.PlexWebsocket.listen"
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    server_id = mock_plex_server.machineIdentifier

    await trigger_plex_update(hass, server_id)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))

    mock_plex_server.clear_clients()
    mock_plex_server.clear_sessions()

    await trigger_plex_update(hass, server_id)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == "0"


async def test_debouncer(hass, caplog):
    """Test debouncer decorator logic."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    mock_plex_server = MockPlexServer(config_entry=entry)

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "homeassistant.components.plex.PlexWebsocket.listen"
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    server_id = mock_plex_server.machineIdentifier

    # First two updates are skipped
    async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))
    await hass.async_block_till_done()
    async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))
    await hass.async_block_till_done()
    async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))
    await hass.async_block_till_done()

    next_update = dt_util.utcnow() + timedelta(seconds=DEBOUNCE_TIMEOUT)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert (
        caplog.text.count(f"Throttling update of {mock_plex_server.friendlyName}") == 2
    )
