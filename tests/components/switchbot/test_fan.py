"""Test the switchbot fan."""

from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_switchbot_entities

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    switchbot_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Switchbot entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_switchbot_entities(hass, entity_registry, snapshot, Platform.FAN)


# @pytest.mark.parametrize(
#     (
#         "service",
#         "service_data",
#         "mock_method",
#     ),
#     [
#         (
#             SERVICE_SET_PRESET_MODE,
#             {ATTR_PRESET_MODE: "baby"},
#             "set_preset_mode",
#         ),
#         (
#             SERVICE_SET_PERCENTAGE,
#             {ATTR_PERCENTAGE: 27},
#             "set_percentage",
#         ),
#         (
#             SERVICE_OSCILLATE,
#             {ATTR_OSCILLATING: True},
#             "set_oscillation",
#         ),
#         (
#             SERVICE_TURN_OFF,
#             {},
#             "turn_off",
#         ),
#         (
#             SERVICE_TURN_ON,
#             {},
#             "turn_on",
#         ),
#     ],
# )
# async def test_circulator_fan_controlling(
#     hass: HomeAssistant,
#     mock_entry_factory: Callable[[str], MockConfigEntry],
#     service: str,
#     service_data: dict,
#     mock_method: str,
# ) -> None:
#     """Test controlling the circulator fan with different services."""
#     inject_bluetooth_service_info(hass, CIRCULATOR_FAN_SERVICE_INFO)
#
#     entry = mock_entry_factory(sensor_type="circulator_fan")
#     entity_id = "fan.test_name"
#     entry.add_to_hass(hass)
#
#     mocked_instance = AsyncMock(return_value=True)
#     mcoked_none_instance = AsyncMock(return_value=None)
#     with patch.multiple(
#         "homeassistant.components.switchbot.fan.switchbot.SwitchbotFan",
#         get_basic_info=mcoked_none_instance,
#         **{mock_method: mocked_instance},
#     ):
#         assert await hass.config_entries.async_setup(entry.entry_id)
#         await hass.async_block_till_done()
#
#         await hass.services.async_call(
#             FAN_DOMAIN,
#             service,
#             {**service_data, ATTR_ENTITY_ID: entity_id},
#             blocking=True,
#         )
#
#         mocked_instance.assert_awaited_once()
