"""Test UptimeRobot sensor."""

from unittest.mock import patch

from pyuptimerobot import UptimeRobotAuthenticationException

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from .common import (
    MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA,
    MOCK_UPTIMEROBOT_MONITOR,
    MOCK_UPTIMEROBOT_MONITOR_PAUSED,
    UPTIMEROBOT_SWITCH_TEST_ENTITY,
    mock_uptimerobot_api_response,
    setup_uptimerobot_integration,
)

from tests.common import MockConfigEntry

SWITCH_ICON = "mdi:cog"


async def test_presentation(hass: HomeAssistant) -> None:
    """Test the presenstation of UptimeRobot sensors."""
    await setup_uptimerobot_integration(hass)

    entity = hass.states.get(UPTIMEROBOT_SWITCH_TEST_ENTITY)

    assert entity.state == STATE_OFF
    assert entity.attributes["icon"] == SWITCH_ICON
    assert entity.attributes["target"] == MOCK_UPTIMEROBOT_MONITOR["url"]


async def test_switch_off(hass: HomeAssistant) -> None:
    """Test entity unaviable on update failure."""
    await setup_uptimerobot_integration(hass)

    with patch("pyuptimerobot.UptimeRobot.async_edit_monitor"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: UPTIMEROBOT_SWITCH_TEST_ENTITY},
            blocking=True,
        )

    entity = hass.states.get(UPTIMEROBOT_SWITCH_TEST_ENTITY)
    assert entity.state == STATE_OFF


async def test_switch_on(hass: HomeAssistant) -> None:
    """Test entity unaviable on update failure."""

    mock_entry = MockConfigEntry(**MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA)
    mock_entry.add_to_hass(hass)

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        return_value=mock_uptimerobot_api_response(
            data=[MOCK_UPTIMEROBOT_MONITOR_PAUSED]
        ),
    ):

        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    with patch("pyuptimerobot.UptimeRobot.async_edit_monitor"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: UPTIMEROBOT_SWITCH_TEST_ENTITY},
            blocking=True,
        )

        entity = hass.states.get(UPTIMEROBOT_SWITCH_TEST_ENTITY)
        assert entity.state == STATE_ON


async def test_authentication_error(hass: HomeAssistant, caplog) -> None:
    """Test authentication error turning switch on/off."""
    await setup_uptimerobot_integration(hass)

    entity = hass.states.get(UPTIMEROBOT_SWITCH_TEST_ENTITY)
    assert entity.state == STATE_OFF

    with patch(
        "pyuptimerobot.UptimeRobot.async_edit_monitor",
        side_effect=UptimeRobotAuthenticationException,
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: UPTIMEROBOT_SWITCH_TEST_ENTITY},
            blocking=True,
        )
        assert "Authentication Error" in caplog.text
