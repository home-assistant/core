"""Tests for number platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aioautomower.exceptions import ApiException
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_number_states(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test number state."""
    entity_id = "number.test_mower_1_cutting_height"
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(entity_id)
    assert state is None  ## disabled by default
    entity_registry.async_update_entity(entity_id=entity_id, disabled_by=None)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "4"


async def test_number_commands(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test number commands."""
    entity_id = "number.test_mower_1_cutting_height"
    await setup_integration(hass, mock_config_entry)
    entity_registry.async_update_entity(entity_id=entity_id, disabled_by=None)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.services.async_call(
        domain="number",
        service="set_value",
        target={"entity_id": entity_id},
        service_data={"value": "3"},
        blocking=True,
    )
    mocked_method = mock_automower_client.set_cutting_height
    assert len(mocked_method.mock_calls) == 1

    mocked_method.side_effect = ApiException("Test error")
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            domain="number",
            service="set_value",
            target={"entity_id": entity_id},
            service_data={"value": "3"},
            blocking=True,
        )
    assert (
        str(exc_info.value)
        == "Command couldn't be sent to the command queue: Test error"
    )
    assert len(mocked_method.mock_calls) == 2
