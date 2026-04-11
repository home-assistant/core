"""Tests for Kodi binary sensors."""

from unittest.mock import patch

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.homeassistant import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.components.kodi.const import CONF_WS_PORT, DOMAIN
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from . import init_integration
from .util import MockConnection, MockWSConnection

from tests.common import MockConfigEntry


async def test_screensaver_binary_sensor_defaults_off(hass: HomeAssistant) -> None:
    """Test the Kodi screensaver binary sensor is created."""
    await init_integration(hass)

    state = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.name_screensaver")

    assert state is not None
    assert state.state == "off"


async def test_screensaver_binary_sensor_updates_from_websocket(
    hass: HomeAssistant,
) -> None:
    """Test the Kodi screensaver binary sensor updates from websocket events."""
    connection = MockWSConnection()
    await init_integration(hass, connection=connection)

    connection.server.GUI.OnScreensaverActivated(None, None)
    await hass.async_block_till_done()

    state = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.name_screensaver")

    assert state is not None
    assert state.state == "on"

    connection.server.GUI.OnScreensaverDeactivated(None, None)
    await hass.async_block_till_done()

    state = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.name_screensaver")

    assert state is not None
    assert state.state == "off"


async def test_screensaver_binary_sensor_clears_on_disconnect(
    hass: HomeAssistant,
) -> None:
    """Test the Kodi screensaver binary sensor clears on disconnect."""
    connection = MockWSConnection()
    await init_integration(
        hass,
        call_method_return_value={"System.ScreenSaverActive": True},
        connection=connection,
    )

    await connection.server.System.OnQuit(None, None)
    await hass.async_block_till_done()

    state = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.name_screensaver")

    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_screensaver_binary_sensor_updates_via_media_player_polling(
    hass: HomeAssistant,
) -> None:
    """Test the Kodi screensaver binary sensor updates via media player polling."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "name",
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 8080,
            CONF_WS_PORT: 9090,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_SSL: False,
        },
        title="name",
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.kodi.Kodi.ping", return_value=True),
        patch(
            "homeassistant.components.kodi.Kodi.call_method",
            side_effect=[
                {"System.ScreenSaverActive": False},
                {"System.ScreenSaverActive": True},
            ],
        ),
        patch("homeassistant.components.kodi.Kodi.get_players", return_value=[]),
        patch(
            "homeassistant.components.kodi.Kodi.get_application_properties",
            return_value={"version": {"major": 1, "minor": 1}},
        ),
        patch(
            "homeassistant.components.kodi.get_kodi_connection",
            return_value=MockConnection(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            HOMEASSISTANT_DOMAIN,
            "update_entity",
            {"entity_id": f"{MEDIA_PLAYER_DOMAIN}.name"},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.name_screensaver")

        assert state is not None
        assert state.state == "on"
