"""Test Wallbox Lock component."""
from http import HTTPStatus
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import HTTPError

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.components.wallbox import InvalidAuth
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import entry, setup_integration
from .const import MOCK_SWITCH_ENTITY_ID


async def test_wallbox_switch_class(hass: HomeAssistant) -> None:
    """Test wallbox switch class."""

    await setup_integration(hass)

    state = hass.states.get(MOCK_SWITCH_ENTITY_ID)
    assert state
    assert state.state == "on"

    with patch("wallbox.Wallbox.authenticate", return_value=None,), patch(
        "wallbox.Wallbox.lockCharger",
        return_value=None,
    ), patch("wallbox.Wallbox.pauseChargingSession", return_value=None,), patch(
        "wallbox.Wallbox.resumeChargingSession",
        return_value=None,
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

    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_switch_class_connection_error(hass: HomeAssistant) -> None:
    """Test wallbox switch class connection error."""

    await setup_integration(hass)

    with patch("wallbox.Wallbox.authenticate", return_value=None,), patch(
        "wallbox.Wallbox.pauseChargingSession",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.NOT_FOUND),
            response=Mock(status_code=HTTPStatus.NOT_FOUND),
        ),
    ), patch(
        "wallbox.Wallbox.resumeChargingSession",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.NOT_FOUND),
            response=Mock(status_code=HTTPStatus.NOT_FOUND),
        ),
    ):

        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                "switch",
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
                },
                blocking=True,
            )
        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                "switch",
                SERVICE_TURN_OFF,
                {
                    ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
                },
                blocking=True,
            )

    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_switch_class_authentication_error(hass: HomeAssistant) -> None:
    """Test wallbox switch class authentication error."""

    await setup_integration(hass)

    with patch("wallbox.Wallbox.authenticate", return_value=None,), patch(
        "wallbox.Wallbox.pauseChargingSession",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.FORBIDDEN),
            response=Mock(status_code=HTTPStatus.FORBIDDEN),
        ),
    ), patch(
        "wallbox.Wallbox.resumeChargingSession",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.FORBIDDEN),
            response=Mock(status_code=HTTPStatus.FORBIDDEN),
        ),
    ):

        with pytest.raises(InvalidAuth):
            await hass.services.async_call(
                "switch",
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
                },
                blocking=True,
            )
        with pytest.raises(InvalidAuth):
            await hass.services.async_call(
                "switch",
                SERVICE_TURN_OFF,
                {
                    ATTR_ENTITY_ID: MOCK_SWITCH_ENTITY_ID,
                },
                blocking=True,
            )

    await hass.config_entries.async_unload(entry.entry_id)
