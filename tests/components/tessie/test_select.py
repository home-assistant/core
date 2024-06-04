"""Test the Tessie select platform."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.tessie.const import TessieSeatHeaterOptions
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import ERROR_UNKNOWN, TEST_RESPONSE, assert_entities, setup_platform


async def test_select(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the select entities are correct."""

    entry = await setup_platform(hass, [Platform.SELECT])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

    entity_id = "select.test_seat_heater_left"

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
    assert hass.states.get(entity_id) == snapshot(name=SERVICE_SELECT_OPTION)


async def test_errors(hass: HomeAssistant) -> None:
    """Tests unknown error is handled."""

    await setup_platform(hass, [Platform.SELECT])
    entity_id = "select.test_seat_heater_left"

    # Test setting cover open with unknown error
    with (
        patch(
            "homeassistant.components.tessie.select.set_seat_heat",
            side_effect=ERROR_UNKNOWN,
        ) as mock_set,
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: [entity_id], ATTR_OPTION: TessieSeatHeaterOptions.LOW},
            blocking=True,
        )
        mock_set.assert_called_once()
        assert error.from_exception == ERROR_UNKNOWN
