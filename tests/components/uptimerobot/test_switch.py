"""Test UptimeRobot switch."""

from unittest.mock import patch

import pytest
from pyuptimerobot import UptimeRobotAuthenticationException, UptimeRobotException

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import (
    MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA,
    MOCK_UPTIMEROBOT_MONITOR,
    MOCK_UPTIMEROBOT_MONITOR_PAUSED,
    UPTIMEROBOT_SWITCH_TEST_ENTITY,
    MockApiResponseKey,
    mock_uptimerobot_api_response,
    setup_uptimerobot_integration,
)

from tests.common import MockConfigEntry


async def test_presentation(hass: HomeAssistant) -> None:
    """Test the presentation of UptimeRobot switches."""
    await setup_uptimerobot_integration(hass)

    assert (entity := hass.states.get(UPTIMEROBOT_SWITCH_TEST_ENTITY)) is not None
    assert entity.state == STATE_ON
    assert entity.attributes["target"] == MOCK_UPTIMEROBOT_MONITOR["url"]


async def test_switch_off(hass: HomeAssistant) -> None:
    """Test entity unavailable on update failure."""

    mock_entry = MockConfigEntry(**MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA)
    mock_entry.add_to_hass(hass)

    with (
        patch(
            "pyuptimerobot.UptimeRobot.async_get_monitors",
            return_value=mock_uptimerobot_api_response(
                data=[MOCK_UPTIMEROBOT_MONITOR_PAUSED]
            ),
        ),
        patch(
            "pyuptimerobot.UptimeRobot.async_edit_monitor",
            return_value=mock_uptimerobot_api_response(),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: UPTIMEROBOT_SWITCH_TEST_ENTITY},
            blocking=True,
        )

    assert (entity := hass.states.get(UPTIMEROBOT_SWITCH_TEST_ENTITY)) is not None
    assert entity.state == STATE_OFF


async def test_switch_on(hass: HomeAssistant) -> None:
    """Test entity unaviable on update failure."""

    mock_entry = MockConfigEntry(**MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA)
    mock_entry.add_to_hass(hass)

    with (
        patch(
            "pyuptimerobot.UptimeRobot.async_get_monitors",
            return_value=mock_uptimerobot_api_response(data=[MOCK_UPTIMEROBOT_MONITOR]),
        ),
        patch(
            "pyuptimerobot.UptimeRobot.async_edit_monitor",
            return_value=mock_uptimerobot_api_response(),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: UPTIMEROBOT_SWITCH_TEST_ENTITY},
            blocking=True,
        )

        assert (entity := hass.states.get(UPTIMEROBOT_SWITCH_TEST_ENTITY)) is not None
        assert entity.state == STATE_ON


async def test_authentication_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test authentication error turning switch on/off."""
    await setup_uptimerobot_integration(hass)

    assert (entity := hass.states.get(UPTIMEROBOT_SWITCH_TEST_ENTITY)) is not None
    assert entity.state == STATE_ON

    with (
        patch(
            "pyuptimerobot.UptimeRobot.async_edit_monitor",
            side_effect=UptimeRobotAuthenticationException,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntry.async_start_reauth"
        ) as config_entry_reauth,
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: UPTIMEROBOT_SWITCH_TEST_ENTITY},
            blocking=True,
        )

        assert config_entry_reauth.assert_called


async def test_action_execution_failure(hass: HomeAssistant) -> None:
    """Test turning switch on/off failure."""
    await setup_uptimerobot_integration(hass)

    assert (entity := hass.states.get(UPTIMEROBOT_SWITCH_TEST_ENTITY)) is not None
    assert entity.state == STATE_ON

    with (
        patch(
            "pyuptimerobot.UptimeRobot.async_edit_monitor",
            side_effect=UptimeRobotException,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: UPTIMEROBOT_SWITCH_TEST_ENTITY},
            blocking=True,
        )

    assert exc_info.value.translation_domain == "uptimerobot"
    assert exc_info.value.translation_key == "api_exception"
    assert exc_info.value.translation_placeholders == {
        "error": "UptimeRobotException()"
    }


async def test_switch_api_failure(hass: HomeAssistant) -> None:
    """Test general exception turning switch on/off."""
    await setup_uptimerobot_integration(hass)

    assert (entity := hass.states.get(UPTIMEROBOT_SWITCH_TEST_ENTITY)) is not None
    assert entity.state == STATE_ON

    with patch(
        "pyuptimerobot.UptimeRobot.async_edit_monitor",
        return_value=mock_uptimerobot_api_response(key=MockApiResponseKey.ERROR),
    ):
        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: UPTIMEROBOT_SWITCH_TEST_ENTITY},
                blocking=True,
            )

        assert exc_info.value.translation_domain == "uptimerobot"
        assert exc_info.value.translation_key == "api_exception"
        assert exc_info.value.translation_placeholders == {
            "error": "test error from API."
        }
