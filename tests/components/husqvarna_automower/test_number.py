"""Tests for number platform."""

from unittest.mock import AsyncMock, patch

from aioautomower.exceptions import ApiError
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import MockConfigEntry, snapshot_platform


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
    mocked_method = mock_automower_client.commands.set_cutting_height
    mocked_method.assert_called_once_with(TEST_MOWER_ID, 3)

    mocked_method.side_effect = ApiError("Test error")
    with pytest.raises(
        HomeAssistantError,
        match="Failed to send command: Test error",
    ):
        await hass.services.async_call(
            domain="number",
            service="set_value",
            target={"entity_id": entity_id},
            service_data={"value": "3"},
            blocking=True,
        )
    assert len(mocked_method.mock_calls) == 2


# async def test_number_workarea_commands(
#     hass: HomeAssistant,
#     mock_automower_client: AsyncMock,
#     mock_config_entry: MockConfigEntry,
#     freezer: FrozenDateTimeFactory,
#     values: dict[str, MowerAttributes],
# ) -> None:
#     """Test number commands."""
#     entity_id = "number.test_mower_1_front_lawn_cutting_height"
#     await setup_integration(hass, mock_config_entry)
#     values[TEST_MOWER_ID].work_areas[123456].cutting_height = 75
#     mock_automower_client.get_status.return_value = values
#     mocked_method = AsyncMock()
#     mock_automower_client.commands.workarea_settings.return_value = mocked_method
#     await hass.services.async_call(
#         domain="number",
#         service="set_value",
#         target={"entity_id": entity_id},
#         service_data={"value": "75"},
#         blocking=False,
#     )
#     freezer.tick(timedelta(seconds=EXECUTION_TIME_DELAY))
#     async_fire_time_changed(hass)
#     await hass.async_block_till_done()
#     mocked_method.cutting_height.assert_called_once_with(cutting_height=75)
#     state = hass.states.get(entity_id)
#     assert state.state is not None
#     assert state.state == "75"

#     mocked_method.cutting_height.side_effect = ApiError("Test error")
#     with pytest.raises(
#         HomeAssistantError,
#         match="Failed to send command: Test error",
#     ):
#         await hass.services.async_call(
#             domain="number",
#             service="set_value",
#             target={"entity_id": entity_id},
#             service_data={"value": "75"},
#             blocking=True,
#         )
#     assert len(mocked_method.mock_calls) == 2


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot tests of the number entities."""
    with patch(
        "homeassistant.components.husqvarna_automower.PLATFORMS",
        [Platform.NUMBER],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )
