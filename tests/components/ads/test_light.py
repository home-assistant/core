"""Test the ADS light platform."""

import struct
from typing import Any
from unittest.mock import MagicMock, call

import pyads
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    LightEntityStateAttribute,
    LightService,
    LightServiceArgument,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockAdsDevice, async_run_past_first_update, setup_ads_platform

ADS_VAR = "GVL.light"
ADS_VAR_BRIGHTNESS = "GVL.light_brightness"
ADS_VAR_COLOR_TEMP = "GVL.light_color_temp"
ENTITY_ID = "light.ceiling"

ONOFF_CONFIG = {"adsvar": ADS_VAR, "name": "Ceiling"}
BRIGHTNESS_CONFIG = {**ONOFF_CONFIG, "adsvar_brightness": ADS_VAR_BRIGHTNESS}
COLOR_TEMP_CONFIG = {
    **BRIGHTNESS_CONFIG,
    "adsvar_color_temp_kelvin": ADS_VAR_COLOR_TEMP,
}

BOOL_TRUE = b"\x01"
BOOL_FALSE = b"\x00"
PLC_VALUES = {
    ADS_VAR: BOOL_TRUE,
    ADS_VAR_BRIGHTNESS: struct.pack("<H", 128),
    ADS_VAR_COLOR_TEMP: struct.pack("<H", 4000),
}


@pytest.mark.parametrize(
    ("platform_config", "entity_id"),
    [
        pytest.param({"adsvar": ADS_VAR}, "light.ads_light", id="defaults"),
        pytest.param(BRIGHTNESS_CONFIG, ENTITY_ID, id="brightness"),
        pytest.param(COLOR_TEMP_CONFIG, ENTITY_ID, id="color_temp"),
        pytest.param(
            {
                **COLOR_TEMP_CONFIG,
                "min_color_temp_kelvin": 2700,
                "max_color_temp_kelvin": 6500,
            },
            ENTITY_ID,
            id="color_temp_range",
        ),
    ],
)
async def test_light(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ads_device: MockAdsDevice,
    snapshot: SnapshotAssertion,
    platform_config: dict[str, Any],
    entity_id: str,
) -> None:
    """Test the light is created from YAML with the PLC's values."""
    mock_ads_device.values.update(PLC_VALUES)

    assert await setup_ads_platform(
        hass, mock_ads_device, LIGHT_DOMAIN, platform_config
    )

    assert entity_registry.async_get(entity_id) == snapshot(name="entry")
    assert hass.states.get(entity_id) == snapshot(name="state")


async def test_state_follows_the_plc(
    hass: HomeAssistant, mock_ads_device: MockAdsDevice
) -> None:
    """Test the light follows the values the PLC pushes, brightness unscaled."""
    mock_ads_device.values.update(PLC_VALUES)
    assert await setup_ads_platform(
        hass, mock_ads_device, LIGHT_DOMAIN, COLOR_TEMP_CONFIG
    )

    await mock_ads_device.async_push(hass, ADS_VAR_BRIGHTNESS, struct.pack("<H", 1000))
    await mock_ads_device.async_push(hass, ADS_VAR_COLOR_TEMP, struct.pack("<H", 3000))
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[LightEntityStateAttribute.BRIGHTNESS] == 1000
    assert state.attributes[LightEntityStateAttribute.COLOR_TEMP_KELVIN] == 3000

    await mock_ads_device.async_push(hass, ADS_VAR, BOOL_FALSE)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


@pytest.mark.parametrize(
    ("silent_var", "expected_state", "expected_brightness"),
    [
        pytest.param(ADS_VAR_BRIGHTNESS, STATE_ON, None, id="silent_brightness"),
        pytest.param(ADS_VAR, STATE_UNAVAILABLE, None, id="silent_onoff"),
    ],
)
async def test_availability_follows_the_onoff_variable(
    hass: HomeAssistant,
    mock_ads_device: MockAdsDevice,
    silent_var: str,
    expected_state: str,
    expected_brightness: int | None,
) -> None:
    """Test only the on/off variable decides whether the light is available."""
    mock_ads_device.values.update(PLC_VALUES)
    del mock_ads_device.values[silent_var]

    assert await async_run_past_first_update(
        hass,
        mock_ads_device,
        setup_ads_platform(hass, mock_ads_device, LIGHT_DOMAIN, BRIGHTNESS_CONFIG),
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == expected_state
    assert (
        state.attributes.get(LightEntityStateAttribute.BRIGHTNESS)
        == expected_brightness
    )


@pytest.mark.parametrize(
    ("platform_config", "service", "data", "writes"),
    [
        pytest.param(
            ONOFF_CONFIG,
            LightService.TURN_ON,
            {},
            [call(ADS_VAR, True, pyads.PLCTYPE_BOOL)],
            id="turn_on",
        ),
        pytest.param(
            BRIGHTNESS_CONFIG,
            LightService.TURN_ON,
            {LightServiceArgument.BRIGHTNESS: 200},
            [
                call(ADS_VAR, True, pyads.PLCTYPE_BOOL),
                call(ADS_VAR_BRIGHTNESS, 200, pyads.PLCTYPE_UINT),
            ],
            id="turn_on_brightness",
        ),
        pytest.param(
            COLOR_TEMP_CONFIG,
            LightService.TURN_ON,
            {LightServiceArgument.COLOR_TEMP_KELVIN: 3000},
            [
                call(ADS_VAR, True, pyads.PLCTYPE_BOOL),
                call(ADS_VAR_COLOR_TEMP, 3000, pyads.PLCTYPE_UINT),
            ],
            id="turn_on_color_temp",
        ),
        pytest.param(
            COLOR_TEMP_CONFIG,
            LightService.TURN_ON,
            {
                LightServiceArgument.BRIGHTNESS: 200,
                LightServiceArgument.COLOR_TEMP_KELVIN: 3000,
            },
            [
                call(ADS_VAR, True, pyads.PLCTYPE_BOOL),
                call(ADS_VAR_BRIGHTNESS, 200, pyads.PLCTYPE_UINT),
                call(ADS_VAR_COLOR_TEMP, 3000, pyads.PLCTYPE_UINT),
            ],
            id="turn_on_brightness_color_temp",
        ),
        pytest.param(
            BRIGHTNESS_CONFIG,
            LightService.TURN_OFF,
            {},
            [call(ADS_VAR, False, pyads.PLCTYPE_BOOL)],
            id="turn_off",
        ),
    ],
)
async def test_actions_write_to_the_plc(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    platform_config: dict[str, Any],
    service: str,
    data: dict[str, Any],
    writes: list[Any],
) -> None:
    """Test the actions write the on/off variable first, then the values."""
    mock_ads_device.values.update(PLC_VALUES)
    assert await setup_ads_platform(
        hass, mock_ads_device, LIGHT_DOMAIN, platform_config
    )

    await hass.services.async_call(
        LIGHT_DOMAIN, service, {TargetKey.ENTITY_ID: ENTITY_ID, **data}, blocking=True
    )

    assert mock_pyads_connection.return_value.write_by_name.call_args_list == writes


async def test_write_error(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing write is logged, and the remaining writes still go out."""
    mock_ads_device.values.update(PLC_VALUES)
    assert await setup_ads_platform(
        hass, mock_ads_device, LIGHT_DOMAIN, BRIGHTNESS_CONFIG
    )
    write_by_name = mock_pyads_connection.return_value.write_by_name
    write_by_name.side_effect = pyads.ADSError(err_code=1861)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: ENTITY_ID, LightServiceArgument.BRIGHTNESS: 200},
        blocking=True,
    )

    assert f"Error writing {ADS_VAR}: ADSError: timeout elapsed (1861)" in caplog.text
    assert write_by_name.call_args_list == [
        call(ADS_VAR, True, pyads.PLCTYPE_BOOL),
        call(ADS_VAR_BRIGHTNESS, 200, pyads.PLCTYPE_UINT),
    ]
