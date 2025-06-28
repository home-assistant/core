"""Test Wallbox Lock component."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.components.wallbox.const import CHARGER_STATUS_ID_KEY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import authorisation_response, http_404_error, http_429_error, setup_integration
from .const import MOCK_SWITCH_ENTITY_ID

from tests.common import MockConfigEntry


async def test_wallbox_switch_class(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox switch class."""

    await setup_integration(hass, entry)

    state = hass.states.get(MOCK_SWITCH_ENTITY_ID)
    assert state
    assert state.state == "on"

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.pauseChargingSession",
            new=Mock(return_value={CHARGER_STATUS_ID_KEY: 193}),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.resumeChargingSession",
            new=Mock(return_value={CHARGER_STATUS_ID_KEY: 193}),
        ),
    ):
        await hass.services.async_call(
            "switch",
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
            },
            blocking=True,
        )

        await hass.services.async_call(
            "switch",
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
            },
            blocking=True,
        )


async def test_wallbox_switch_class_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox switch class connection error."""

    await setup_integration(hass, entry)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.resumeChargingSession",
            new=Mock(side_effect=http_404_error),
        ),
        pytest.raises(HomeAssistantError),
    ):
        # Test behavior when a connection error occurs
        await hass.services.async_call(
            "switch",
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
            },
            blocking=True,
        )


async def test_wallbox_switch_class_too_many_requests(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox switch class connection error."""

    await setup_integration(hass, entry)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.resumeChargingSession",
            new=Mock(side_effect=http_429_error),
        ),
        pytest.raises(HomeAssistantError),
    ):
        # Test behavior when a connection error occurs
        await hass.services.async_call(
            "switch",
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
            },
            blocking=True,
        )
