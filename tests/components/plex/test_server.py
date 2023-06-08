"""Tests for Plex server."""
import copy
from unittest.mock import patch

import pytest
from requests.exceptions import ConnectionError, RequestException
import requests_mock

from homeassistant.components.plex.const import (
    CONF_IGNORE_NEW_SHARED_USERS,
    CONF_IGNORE_PLEX_WEB_CLIENTS,
    CONF_MONITORED_USERS,
    CONF_SERVER,
    DOMAIN,
    SERVERS,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DEFAULT_DATA, DEFAULT_OPTIONS
from .helpers import trigger_plex_update, wait_for_debouncer


async def test_new_users_available(
    hass: HomeAssistant, entry, setup_plex_server
) -> None:
    """Test setting up when new users available on Plex server."""
    MONITORED_USERS = {"User 1": {"enabled": True}}
    OPTIONS_WITH_USERS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS_WITH_USERS[Platform.MEDIA_PLAYER][CONF_MONITORED_USERS] = MONITORED_USERS
    entry.options = OPTIONS_WITH_USERS

    mock_plex_server = await setup_plex_server(config_entry=entry)

    server_id = mock_plex_server.machine_identifier

    monitored_users = hass.data[DOMAIN][SERVERS][server_id].option_monitored_users

    ignored_users = [x for x in monitored_users if not monitored_users[x]["enabled"]]
    assert len(monitored_users) == 1
    assert len(ignored_users) == 0


async def test_new_ignored_users_available(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    entry,
    mock_websocket,
    setup_plex_server,
    requests_mock: requests_mock.Mocker,
    session_new_user,
) -> None:
    """Test setting up when new users available on Plex server but are ignored."""
    MONITORED_USERS = {"User 1": {"enabled": True}}
    OPTIONS_WITH_USERS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS_WITH_USERS[Platform.MEDIA_PLAYER][CONF_MONITORED_USERS] = MONITORED_USERS
    OPTIONS_WITH_USERS[Platform.MEDIA_PLAYER][CONF_IGNORE_NEW_SHARED_USERS] = True
    entry.options = OPTIONS_WITH_USERS

    mock_plex_server = await setup_plex_server(config_entry=entry)

    requests_mock.get(
        f"{mock_plex_server.url_in_use}/status/sessions",
        text=session_new_user,
    )
    trigger_plex_update(mock_websocket)
    await wait_for_debouncer(hass)

    server_id = mock_plex_server.machine_identifier

    active_sessions = mock_plex_server._plex_server.sessions()
    monitored_users = hass.data[DOMAIN][SERVERS][server_id].option_monitored_users
    ignored_users = [x for x in mock_plex_server.accounts if x not in monitored_users]

    assert len(monitored_users) == 1
    assert len(ignored_users) == 2

    for ignored_user in ignored_users:
        ignored_client = [
            x.players[0] for x in active_sessions if x.usernames[0] == ignored_user
        ]
        if ignored_client:
            assert (
                f"Ignoring {ignored_client[0].product} client owned by '{ignored_user}'"
                in caplog.text
            )

    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(active_sessions))


async def test_network_error_during_refresh(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_plex_server
) -> None:
    """Test network failures during refreshes."""
    server_id = mock_plex_server.machine_identifier
    loaded_server = hass.data[DOMAIN][SERVERS][server_id]
    active_sessions = mock_plex_server._plex_server.sessions()

    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(active_sessions))

    with patch("plexapi.server.PlexServer.clients", side_effect=RequestException):
        await loaded_server._async_update_platforms()
        await hass.async_block_till_done()

    assert (
        f"Could not connect to Plex server: {DEFAULT_DATA[CONF_SERVER]}" in caplog.text
    )


async def test_gdm_client_failure(
    hass: HomeAssistant, mock_websocket, setup_plex_server
) -> None:
    """Test connection failure to a GDM discovered client."""
    with patch(
        "homeassistant.components.plex.server.PlexClient", side_effect=ConnectionError
    ):
        mock_plex_server = await setup_plex_server(disable_gdm=False)
        await hass.async_block_till_done()

    active_sessions = mock_plex_server._plex_server.sessions()
    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(active_sessions))

    with patch("plexapi.server.PlexServer.clients", side_effect=RequestException):
        trigger_plex_update(mock_websocket)
        await hass.async_block_till_done()


async def test_mark_sessions_idle(
    hass: HomeAssistant,
    mock_plex_server,
    mock_websocket,
    requests_mock: requests_mock.Mocker,
    empty_payload,
) -> None:
    """Test marking media_players as idle when sessions end."""
    await wait_for_debouncer(hass)

    active_sessions = mock_plex_server._plex_server.sessions()

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(active_sessions))

    url = mock_plex_server.url_in_use
    requests_mock.get(f"{url}/clients", text=empty_payload)
    requests_mock.get(f"{url}/status/sessions", text=empty_payload)

    trigger_plex_update(mock_websocket)
    await hass.async_block_till_done()
    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == "0"


async def test_ignore_plex_web_client(
    hass: HomeAssistant, entry, setup_plex_server
) -> None:
    """Test option to ignore Plex Web clients."""
    OPTIONS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS[Platform.MEDIA_PLAYER][CONF_IGNORE_PLEX_WEB_CLIENTS] = True
    entry.options = OPTIONS

    mock_plex_server = await setup_plex_server(
        config_entry=entry, client_type="plexweb", disable_clients=True
    )
    await wait_for_debouncer(hass)

    active_sessions = mock_plex_server._plex_server.sessions()
    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(active_sessions))

    media_players = hass.states.async_entity_ids("media_player")

    assert len(media_players) == int(sensor.state) - 1
