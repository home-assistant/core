"""Tests for number platform."""

from unittest.mock import AsyncMock, patch

from aioautomower.exceptions import ApiException
from aioautomower.utils import mower_list_to_dictionary_dataclass
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import MockConfigEntry, load_json_value_fixture, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_commands(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test number commands."""
    entity_id = "number.test_mower_1_cutting_height"
    await setup_integration(hass, mock_config_entry)
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


async def test_number_workarea_commands(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test number commands."""
    entity_id = "number.test_mower_1_front_lawn_cutting_height"
    await setup_integration(hass, mock_config_entry)
    values = mower_list_to_dictionary_dataclass(
        load_json_value_fixture("mower.json", DOMAIN)
    )
    values[TEST_MOWER_ID].work_areas[123456].cutting_height = 75
    mock_automower_client.get_status.return_value = values
    mocked_method = AsyncMock()
    setattr(mock_automower_client, "set_cutting_height_workarea", mocked_method)
    await hass.services.async_call(
        domain="number",
        service="set_value",
        target={"entity_id": entity_id},
        service_data={"value": "75"},
        blocking=True,
    )
    assert len(mocked_method.mock_calls) == 1
    state = hass.states.get(entity_id)
    assert state.state is not None
    assert state.state == "75"

    mocked_method.side_effect = ApiException("Test error")
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            domain="number",
            service="set_value",
            target={"entity_id": entity_id},
            service_data={"value": "75"},
            blocking=True,
        )
    assert (
        str(exc_info.value)
        == "Command couldn't be sent to the command queue: Test error"
    )
    assert len(mocked_method.mock_calls) == 2


async def test_workarea_deleted(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test if work area is deleted after removed."""

    values = mower_list_to_dictionary_dataclass(
        load_json_value_fixture("mower.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)
    current_entries = len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )

    del values[TEST_MOWER_ID].work_areas[123456]
    mock_automower_client.get_status.return_value = values
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    ) == (current_entries - 1)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_snapshot_number(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states of the number entity."""
    with patch(
        "homeassistant.components.husqvarna_automower.PLATFORMS",
        [Platform.NUMBER],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )
