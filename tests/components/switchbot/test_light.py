"""Test the switchbot lights."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from switchbot.devices.device import SwitchbotOperationError

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import (
    BULB_SERVICE_INFO,
    CEILING_LIGHT_SERVICE_INFO,
    FLOOR_LAMP_SERVICE_INFO,
    RGBICWW_FLOOR_LAMP_SERVICE_INFO,
    RGBICWW_STRIP_LIGHT_SERVICE_INFO,
    STRIP_LIGHT_3_SERVICE_INFO,
    WOSTRIP_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

COMMON_PARAMETERS = (
    "service",
    "service_data",
    "mock_method",
    "expected_args",
)
TURN_ON_PARAMETERS = (
    SERVICE_TURN_ON,
    {},
    "turn_on",
    {},
)
TURN_OFF_PARAMETERS = (
    SERVICE_TURN_OFF,
    {},
    "turn_off",
    {},
)
SET_BRIGHTNESS_PARAMETERS = (
    SERVICE_TURN_ON,
    {ATTR_BRIGHTNESS: 128},
    "set_brightness",
    (round(128 / 255 * 100),),
)
SET_RGB_PARAMETERS = (
    SERVICE_TURN_ON,
    {ATTR_BRIGHTNESS: 128, ATTR_RGB_COLOR: (255, 0, 0)},
    "set_rgb",
    (round(128 / 255 * 100), 255, 0, 0),
)
SET_COLOR_TEMP_PARAMETERS = (
    SERVICE_TURN_ON,
    {ATTR_BRIGHTNESS: 128, ATTR_COLOR_TEMP_KELVIN: 4000},
    "set_color_temp",
    (round(128 / 255 * 100), 4000),
)
BULB_PARAMETERS = (
    COMMON_PARAMETERS,
    [
        TURN_ON_PARAMETERS,
        TURN_OFF_PARAMETERS,
        SET_BRIGHTNESS_PARAMETERS,
        SET_RGB_PARAMETERS,
        SET_COLOR_TEMP_PARAMETERS,
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "breathing"},
            "set_effect",
            ("breathing",),
        ),
    ],
)
CEILING_LIGHT_PARAMETERS = (
    COMMON_PARAMETERS,
    [
        TURN_ON_PARAMETERS,
        TURN_OFF_PARAMETERS,
        SET_BRIGHTNESS_PARAMETERS,
        SET_COLOR_TEMP_PARAMETERS,
    ],
)
STRIP_LIGHT_PARAMETERS = (
    COMMON_PARAMETERS,
    [
        TURN_ON_PARAMETERS,
        TURN_OFF_PARAMETERS,
        SET_BRIGHTNESS_PARAMETERS,
        SET_RGB_PARAMETERS,
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "halloween"},
            "set_effect",
            ("halloween",),
        ),
    ],
)
FLOOR_LAMP_PARAMETERS = (
    COMMON_PARAMETERS,
    [
        TURN_ON_PARAMETERS,
        TURN_OFF_PARAMETERS,
        SET_BRIGHTNESS_PARAMETERS,
        SET_RGB_PARAMETERS,
        SET_COLOR_TEMP_PARAMETERS,
        (
            SERVICE_TURN_ON,
            {ATTR_EFFECT: "halloween"},
            "set_effect",
            ("halloween",),
        ),
    ],
)


@pytest.mark.parametrize(*BULB_PARAMETERS)
async def test_bulb_services(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
    expected_args: Any,
) -> None:
    """Test all SwitchBot bulb services."""
    inject_bluetooth_service_info(hass, BULB_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="bulb")
    entry.add_to_hass(hass)
    entity_id = "light.test_name"

    mocked_instance = AsyncMock(return_value=True)

    with patch.multiple(
        "homeassistant.components.switchbot.light.switchbot.SwitchbotBulb",
        **{mock_method: mocked_instance},
        update=AsyncMock(return_value=None),
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


@pytest.mark.parametrize(*BULB_PARAMETERS)
async def test_bulb_services_exception(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
    expected_args: Any,
) -> None:
    """Test all SwitchBot bulb services with exception."""
    inject_bluetooth_service_info(hass, BULB_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="bulb")
    entry.add_to_hass(hass)
    entity_id = "light.test_name"

    exception = SwitchbotOperationError("Operation failed")
    error_message = "An error occurred while performing the action: Operation failed"

    with patch.multiple(
        "homeassistant.components.switchbot.light.switchbot.SwitchbotBulb",
        **{mock_method: AsyncMock(side_effect=exception)},
        update=AsyncMock(return_value=None),
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


@pytest.mark.parametrize(*CEILING_LIGHT_PARAMETERS)
async def test_ceiling_light_services(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
    expected_args: Any,
) -> None:
    """Test all SwitchBot ceiling light services."""
    inject_bluetooth_service_info(hass, CEILING_LIGHT_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="ceiling_light")
    entry.add_to_hass(hass)
    entity_id = "light.test_name"

    mocked_instance = AsyncMock(return_value=True)

    with patch.multiple(
        "homeassistant.components.switchbot.light.switchbot.SwitchbotCeilingLight",
        **{mock_method: mocked_instance},
        update=AsyncMock(return_value=None),
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


@pytest.mark.parametrize(*CEILING_LIGHT_PARAMETERS)
async def test_ceiling_light_services_exception(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
    expected_args: Any,
) -> None:
    """Test all SwitchBot ceiling light services with exception."""
    inject_bluetooth_service_info(hass, CEILING_LIGHT_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="ceiling_light")
    entry.add_to_hass(hass)
    entity_id = "light.test_name"

    exception = SwitchbotOperationError("Operation failed")
    error_message = "An error occurred while performing the action: Operation failed"

    with patch.multiple(
        "homeassistant.components.switchbot.light.switchbot.SwitchbotCeilingLight",
        **{mock_method: AsyncMock(side_effect=exception)},
        update=AsyncMock(return_value=None),
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


@pytest.mark.parametrize(*STRIP_LIGHT_PARAMETERS)
async def test_strip_light_services(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
    expected_args: Any,
) -> None:
    """Test all SwitchBot strip light services."""
    inject_bluetooth_service_info(hass, WOSTRIP_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="light_strip")
    entry.add_to_hass(hass)
    entity_id = "light.test_name"

    mocked_instance = AsyncMock(return_value=True)

    with patch.multiple(
        "homeassistant.components.switchbot.light.switchbot.SwitchbotLightStrip",
        **{mock_method: mocked_instance},
        update=AsyncMock(return_value=None),
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


@pytest.mark.parametrize(*STRIP_LIGHT_PARAMETERS)
async def test_strip_light_services_exception(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
    expected_args: Any,
) -> None:
    """Test all SwitchBot strip light services with exception."""
    inject_bluetooth_service_info(hass, WOSTRIP_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="light_strip")
    entry.add_to_hass(hass)
    entity_id = "light.test_name"

    exception = SwitchbotOperationError("Operation failed")
    error_message = "An error occurred while performing the action: Operation failed"

    with patch.multiple(
        "homeassistant.components.switchbot.light.switchbot.SwitchbotLightStrip",
        **{mock_method: AsyncMock(side_effect=exception)},
        update=AsyncMock(return_value=None),
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


@pytest.mark.parametrize(
    ("sensor_type", "service_info", "dev_cls"),
    [
        ("strip_light_3", STRIP_LIGHT_3_SERVICE_INFO, "SwitchbotStripLight3"),
        ("floor_lamp", FLOOR_LAMP_SERVICE_INFO, "SwitchbotStripLight3"),
        (
            "rgbicww_strip_light",
            RGBICWW_STRIP_LIGHT_SERVICE_INFO,
            "SwitchbotRgbicLight",
        ),
        ("rgbicww_floor_lamp", RGBICWW_FLOOR_LAMP_SERVICE_INFO, "SwitchbotRgbicLight"),
    ],
)
@pytest.mark.parametrize(*FLOOR_LAMP_PARAMETERS)
async def test_floor_lamp_services(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    sensor_type: str,
    service_info: BluetoothServiceInfoBleak,
    dev_cls: str,
    service: str,
    service_data: dict,
    mock_method: str,
    expected_args: Any,
) -> None:
    """Test all SwitchBot floor lamp services."""
    inject_bluetooth_service_info(hass, service_info)

    entry = mock_entry_encrypted_factory(sensor_type=sensor_type)
    entry.add_to_hass(hass)
    entity_id = "light.test_name"

    mocked_instance = AsyncMock(return_value=True)

    with patch.multiple(
        f"homeassistant.components.switchbot.light.switchbot.{dev_cls}",
        **{mock_method: mocked_instance},
        update=AsyncMock(return_value=None),
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
    ("sensor_type", "service_info"),
    [
        ("strip_light_3", STRIP_LIGHT_3_SERVICE_INFO),
        ("floor_lamp", FLOOR_LAMP_SERVICE_INFO),
    ],
)
@pytest.mark.parametrize(*FLOOR_LAMP_PARAMETERS)
async def test_floor_lamp_services_exception(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    sensor_type: str,
    service_info: BluetoothServiceInfoBleak,
    service: str,
    service_data: dict,
    mock_method: str,
    expected_args: Any,
) -> None:
    """Test all SwitchBot floor lamp services with exception."""
    inject_bluetooth_service_info(hass, service_info)

    entry = mock_entry_encrypted_factory(sensor_type=sensor_type)
    entry.add_to_hass(hass)
    entity_id = "light.test_name"
    exception = SwitchbotOperationError("Operation failed")
    error_message = "An error occurred while performing the action: Operation failed"
    with patch.multiple(
        "homeassistant.components.switchbot.light.switchbot.SwitchbotStripLight3",
        **{mock_method: AsyncMock(side_effect=exception)},
        update=AsyncMock(return_value=None),
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
