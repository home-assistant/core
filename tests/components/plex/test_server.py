"""Tests for Plex server."""
import copy

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.plex.const import (
    CONF_IGNORE_NEW_SHARED_USERS,
    CONF_IGNORE_PLEX_WEB_CLIENTS,
    CONF_MONITORED_USERS,
    DOMAIN,
    PLEX_UPDATE_PLATFORMS_SIGNAL,
    SERVERS,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DEFAULT_DATA, DEFAULT_OPTIONS
from .mock_classes import MockPlexServer

from tests.async_mock import patch
from tests.common import MockConfigEntry


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

    async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))
    await hass.async_block_till_done()

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

    async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))
    await hass.async_block_till_done()

    monitored_users = hass.data[DOMAIN][SERVERS][server_id].option_monitored_users

    ignored_users = [x for x in mock_plex_server.accounts if x not in monitored_users]
    assert len(monitored_users) == 1
    assert len(ignored_users) == 2
    for ignored_user in ignored_users:
        ignored_client = [
            x.players[0]
            for x in mock_plex_server.sessions()
            if x.usernames[0] == ignored_user
        ][0]
        assert (
            f"Ignoring {ignored_client.product} client owned by '{ignored_user}'"
            in caplog.text
        )

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))


# class TestClockedPlex(ClockedTestCase):
#     """Create clock-controlled tests.async_mock class."""

#     async def setUp(self):
#         """Initialize this test class."""
#         self.hass = await async_test_home_assistant(self.loop)

#     async def tearDown(self):
#         """Clean up the HomeAssistant instance."""
#         await self.hass.async_stop()

#     async def test_mark_sessions_idle(self):
#         """Test marking media_players as idle when sessions end."""
#         hass = self.hass

#         entry = MockConfigEntry(
#             domain=DOMAIN,
#             data=DEFAULT_DATA,
#             options=DEFAULT_OPTIONS,
#             unique_id=DEFAULT_DATA["server_id"],
#         )

#         mock_plex_server = MockPlexServer(config_entry=entry)

#         with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
#             "homeassistant.components.plex.PlexWebsocket.listen"
#         ):
#             entry.add_to_hass(hass)
#             assert await hass.config_entries.async_setup(entry.entry_id)
#             await hass.async_block_till_done()

#         server_id = mock_plex_server.machineIdentifier

#         async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))
#         await hass.async_block_till_done()

#         sensor = hass.states.get("sensor.plex_plex_server_1")
#         assert sensor.state == str(len(mock_plex_server.accounts))

#         mock_plex_server.clear_clients()
#         mock_plex_server.clear_sessions()

#         await self.advance(DEBOUNCE_TIMEOUT)
#         async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))
#         await hass.async_block_till_done()

#         sensor = hass.states.get("sensor.plex_plex_server_1")
#         assert sensor.state == "0"

#     async def test_debouncer(self):
#         """Test debouncer behavior."""
#         hass = self.hass

#         entry = MockConfigEntry(
#             domain=DOMAIN,
#             data=DEFAULT_DATA,
#             options=DEFAULT_OPTIONS,
#             unique_id=DEFAULT_DATA["server_id"],
#         )

#         mock_plex_server = MockPlexServer(config_entry=entry)

#         with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
#             "homeassistant.components.plex.PlexWebsocket.listen"
#         ):
#             entry.add_to_hass(hass)
#             assert await hass.config_entries.async_setup(entry.entry_id)
#             await hass.async_block_till_done()

#         server_id = mock_plex_server.machineIdentifier

#         with patch.object(mock_plex_server, "clients", return_value=[]), patch.object(
#             mock_plex_server, "sessions", return_value=[]
#         ) as mock_update:
#             # Called immediately
#             async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))
#             await hass.async_block_till_done()
#             assert mock_update.call_count == 1

#             # Throttled
#             async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))
#             await hass.async_block_till_done()
#             assert mock_update.call_count == 1

#             # Throttled
#             async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))
#             await hass.async_block_till_done()
#             assert mock_update.call_count == 1

#             # Called from scheduler
#             await self.advance(DEBOUNCE_TIMEOUT)
#             await hass.async_block_till_done()
#             assert mock_update.call_count == 2

#             # Throttled
#             async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))
#             await hass.async_block_till_done()
#             assert mock_update.call_count == 2

#             # Called from scheduler
#             await self.advance(DEBOUNCE_TIMEOUT)
#             await hass.async_block_till_done()
#             assert mock_update.call_count == 3


async def test_ignore_plex_web_client(hass):
    """Test option to ignore Plex Web clients."""

    OPTIONS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS[MP_DOMAIN][CONF_IGNORE_PLEX_WEB_CLIENTS] = True

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=OPTIONS,
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

    async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))

    media_players = hass.states.async_entity_ids("media_player")

    assert len(media_players) == int(sensor.state) - 1
