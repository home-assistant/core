"""Test the switchbot lights."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from switchbot import ColorMode as switchbotColorMode
from switchbot.devices.device import SwitchbotOperationError
from syrupy import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import WOSTRIP_SERVICE_INFO, setup_integration, snapshot_switchbot_entities

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


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

    snapshot_switchbot_entities(hass, entity_registry, snapshot, Platform.LIGHT)


@pytest.mark.parametrize(
    (
        "service",
        "service_data",
        "mock_method",
        "expected_args",
        "color_modes",
        "color_mode",
    ),
    [
        (
            SERVICE_TURN_OFF,
            {},
            "turn_off",
            (),
            {switchbotColorMode.RGB},
            switchbotColorMode.RGB,
        ),
        (
            SERVICE_TURN_ON,
            {},
            "turn_on",
            (),
            {switchbotColorMode.RGB},
            switchbotColorMode.RGB,
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_BRIGHTNESS: 128},
            "set_brightness",
            (round(128 / 255 * 100),),
            {switchbotColorMode.RGB},
            switchbotColorMode.RGB,
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_RGB_COLOR: (255, 0, 0)},
            "set_rgb",
            (round(255 / 255 * 100), 255, 0, 0),
            {switchbotColorMode.RGB},
            switchbotColorMode.RGB,
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_COLOR_TEMP_KELVIN: 4000},
            "set_color_temp",
            (100, 4000),
            {switchbotColorMode.COLOR_TEMP},
            switchbotColorMode.COLOR_TEMP,
        ),
    ],
)
async def test_light_strip_services(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
    expected_args: Any,
    color_modes: set | None,
    color_mode: switchbotColorMode | None,
) -> None:
    """Test all SwitchBot light strip services with proper parameters."""
    inject_bluetooth_service_info(hass, WOSTRIP_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="light_strip")
    entry.add_to_hass(hass)
    entity_id = "light.test_name"

    mocked_instance = AsyncMock(return_value=True)

    with patch.multiple(
        "homeassistant.components.switchbot.light.switchbot.SwitchbotLightStrip",
        color_modes=color_modes,
        color_mode=color_mode,
        update=AsyncMock(return_value=None),
        **{mock_method: mocked_instance},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            LIGHT_DOMAIN,
            service,
            {**service_data, ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mocked_instance.assert_awaited_once_with(*expected_args)


@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            SwitchbotOperationError("Operation failed"),
            "An error occurred while performing the action: Operation failed",
        ),
    ],
)
@pytest.mark.parametrize(
    ("service", "service_data", "mock_method", "color_modes", "color_mode"),
    [
        (
            SERVICE_TURN_ON,
            {},
            "turn_on",
            {switchbotColorMode.RGB},
            switchbotColorMode.RGB,
        ),
        (
            SERVICE_TURN_OFF,
            {},
            "turn_off",
            {switchbotColorMode.RGB},
            switchbotColorMode.RGB,
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_BRIGHTNESS: 128},
            "set_brightness",
            {switchbotColorMode.RGB},
            switchbotColorMode.RGB,
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_RGB_COLOR: (255, 0, 0)},
            "set_rgb",
            {switchbotColorMode.RGB},
            switchbotColorMode.RGB,
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_COLOR_TEMP_KELVIN: 4000},
            "set_color_temp",
            {switchbotColorMode.COLOR_TEMP},
            switchbotColorMode.COLOR_TEMP,
        ),
    ],
)
async def test_exception_handling_light_service(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
    color_modes: set | None,
    color_mode: switchbotColorMode | None,
    exception: Exception,
    error_message: str,
) -> None:
    """Test exception handling for light service with exception."""
    inject_bluetooth_service_info(hass, WOSTRIP_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="light_strip")
    entry.add_to_hass(hass)
    entity_id = "light.test_name"

    with patch.multiple(
        "homeassistant.components.switchbot.light.switchbot.SwitchbotLightStrip",
        color_modes=color_modes,
        color_mode=color_mode,
        update=AsyncMock(return_value=None),
        **{mock_method: AsyncMock(side_effect=exception)},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match=error_message):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                service,
                {**service_data, ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
