"""Test the switchbot humidifiers."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from switchbot import SwitchbotModel
from syrupy import SnapshotAssertion

from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    ATTR_MODE,
    DOMAIN as HUMIDIFIER_DOMAIN,
    MODE_AUTO,
    MODE_NORMAL,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
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

    snapshot_switchbot_entities(hass, entity_registry, snapshot, Platform.HUMIDIFIER)


@pytest.mark.parametrize("switchbot_model", [SwitchbotModel.HUMIDIFIER])
@pytest.mark.parametrize(
    ("service", "extra_service_data", "method", "args"),
    [
        (SERVICE_TURN_OFF, {}, "turn_off", []),
        (SERVICE_TURN_ON, {}, "turn_on", []),
        (SERVICE_SET_HUMIDITY, {ATTR_HUMIDITY: 50}, "set_level", (50,)),
        (SERVICE_SET_MODE, {ATTR_MODE: MODE_AUTO}, "set_auto", []),
        (SERVICE_SET_MODE, {ATTR_MODE: MODE_NORMAL}, "set_manual", []),
    ],
)
async def test_humidifier_actions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switchbot_humidifier: dict[str, AsyncMock],
    service: str,
    extra_service_data: dict[str, Any],
    method: str,
    args: list[Any],
) -> None:
    """Test all humidifier services with proper parameters."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "humidifier.test_name"
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id} | extra_service_data,
        blocking=True,
    )
    mock_switchbot_humidifier[method].assert_awaited_once_with(*args)


# @pytest.mark.parametrize(
#     ("exception", "error_message"),
#     [
#         (
#             SwitchbotOperationError("Operation failed"),
#             "An error occurred while performing the action: Operation failed",
#         ),
#     ],
# )
# @pytest.mark.parametrize(
#     ("service", "service_data", "mock_method"),
#     [
#         (SERVICE_TURN_ON, {}, "turn_on"),
#         (SERVICE_TURN_OFF, {}, "turn_off"),
#         (SERVICE_SET_HUMIDITY, {ATTR_HUMIDITY: 60}, "set_level"),
#         (SERVICE_SET_MODE, {ATTR_MODE: MODE_AUTO}, "async_set_auto"),
#         (SERVICE_SET_MODE, {ATTR_MODE: MODE_NORMAL}, "async_set_manual"),
#     ],
# )
# async def test_exception_handling_humidifier_service(
#     hass: HomeAssistant,
#     mock_entry_factory: Callable[[str], MockConfigEntry],
#     service: str,
#     service_data: dict,
#     mock_method: str,
#     exception: Exception,
#     error_message: str,
# ) -> None:
#     """Test exception handling for humidifier service with exception."""
#     inject_bluetooth_service_info(hass, HUMIDIFIER_SERVICE_INFO)
#
#     entry = mock_entry_factory(sensor_type="humidifier")
#     entry.add_to_hass(hass)
#     entity_id = "humidifier.test_name"
#
#     patch_target = f"homeassistant.components.switchbot.humidifier.switchbot.SwitchbotHumidifier.{mock_method}"
#
#     with patch(patch_target, new=AsyncMock(side_effect=exception)):
#         assert await hass.config_entries.async_setup(entry.entry_id)
#         await hass.async_block_till_done()
#
#         with pytest.raises(HomeAssistantError, match=error_message):
#             await hass.services.async_call(
#                 HUMIDIFIER_DOMAIN,
#                 service,
#                 {**service_data, ATTR_ENTITY_ID: entity_id},
#                 blocking=True,
#             )
