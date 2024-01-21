"""Test the Tessie select platform."""
from unittest.mock import patch

import pytest

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.tessie.const import TessieSeatHeaterOptions
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import ERROR_UNKNOWN, TEST_RESPONSE, setup_platform


async def test_select(hass: HomeAssistant) -> None:
    """Tests that the select entities are correct."""

    assert len(hass.states.async_all(SELECT_DOMAIN)) == 0

    await setup_platform(hass)

    assert len(hass.states.async_all(SELECT_DOMAIN)) == 5

    entity_id = "select.test_seat_heater_left"
    assert hass.states.get(entity_id).state == STATE_OFF

    # Test changing select
    with patch(
        "homeassistant.components.tessie.select.set_seat_heat",
        return_value=TEST_RESPONSE,
    ) as mock_set:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: [entity_id], ATTR_OPTION: TessieSeatHeaterOptions.LOW},
            blocking=True,
        )
        mock_set.assert_called_once()
        assert mock_set.call_args[1]["seat"] == "front_left"
        assert mock_set.call_args[1]["level"] == 1
        assert hass.states.get(entity_id).state == TessieSeatHeaterOptions.LOW


async def test_errors(hass: HomeAssistant) -> None:
    """Tests unknown error is handled."""

    await setup_platform(hass)
    entity_id = "select.test_seat_heater_left"

    # Test setting cover open with unknown error
    with patch(
        "homeassistant.components.tessie.select.set_seat_heat",
        side_effect=ERROR_UNKNOWN,
    ) as mock_set, pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: [entity_id], ATTR_OPTION: TessieSeatHeaterOptions.LOW},
            blocking=True,
        )
        mock_set.assert_called_once()
        assert error.from_exception == ERROR_UNKNOWN
