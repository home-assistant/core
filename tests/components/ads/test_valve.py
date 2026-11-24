"""Test the ADS valve platform."""

from typing import Any
from unittest.mock import MagicMock

import pyads
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.valve import (
    DOMAIN as VALVE_DOMAIN,
    ValveService,
    ValveState,
)
from homeassistant.const import STATE_UNAVAILABLE, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockAdsDevice, async_run_past_first_update, setup_ads_platform

ADS_VAR = "GVL.valve"
ENTITY_ID = "valve.water"
PLATFORM_CONFIG = {"adsvar": ADS_VAR, "name": "Water"}

BOOL_TRUE = b"\x01"
BOOL_FALSE = b"\x00"


@pytest.mark.parametrize(
    ("platform_config", "entity_id"),
    [
        pytest.param(
            {**PLATFORM_CONFIG, "device_class": "water"}, ENTITY_ID, id="water"
        ),
        pytest.param({"adsvar": ADS_VAR}, "valve.ads_valve", id="defaults"),
    ],
)
async def test_valve(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ads_device: MockAdsDevice,
    snapshot: SnapshotAssertion,
    platform_config: dict[str, Any],
    entity_id: str,
) -> None:
    """Test the valve is created from YAML."""
    mock_ads_device.values[ADS_VAR] = BOOL_TRUE

    assert await setup_ads_platform(hass, VALVE_DOMAIN, platform_config)

    assert entity_registry.async_get(entity_id) == snapshot(name="entry")
    assert hass.states.get(entity_id) == snapshot(name="state")


@pytest.mark.parametrize(
    ("initial", "pushed"),
    [
        pytest.param(BOOL_TRUE, BOOL_TRUE, id="open"),
        pytest.param(BOOL_FALSE, BOOL_TRUE, id="opened"),
    ],
)
async def test_state_ignores_the_plc(
    hass: HomeAssistant, mock_ads_device: MockAdsDevice, initial: bytes, pushed: bytes
) -> None:
    """Test the valve reports closed whatever the PLC says."""
    mock_ads_device.values[ADS_VAR] = initial
    assert await setup_ads_platform(hass, VALVE_DOMAIN, PLATFORM_CONFIG)

    await mock_ads_device.async_push(hass, ADS_VAR, pushed)

    assert hass.states.get(ENTITY_ID).state == ValveState.CLOSED


async def test_unavailable_until_the_first_value(
    hass: HomeAssistant, mock_ads_device: MockAdsDevice
) -> None:
    """Test the valve is unavailable until the PLC delivers a value."""
    assert await async_run_past_first_update(
        hass, setup_ads_platform(hass, VALVE_DOMAIN, PLATFORM_CONFIG)
    )
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    await mock_ads_device.async_push(hass, ADS_VAR, BOOL_FALSE)
    assert hass.states.get(ENTITY_ID).state == ValveState.CLOSED


@pytest.mark.parametrize(
    ("service", "written"),
    [
        pytest.param(ValveService.OPEN, True, id="open"),
        pytest.param(ValveService.CLOSE, False, id="close"),
    ],
)
async def test_actions_write_to_the_plc(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    service: str,
    written: bool,
) -> None:
    """Test the actions write the variable."""
    mock_ads_device.values[ADS_VAR] = BOOL_FALSE
    assert await setup_ads_platform(hass, VALVE_DOMAIN, PLATFORM_CONFIG)

    await hass.services.async_call(
        VALVE_DOMAIN, service, {TargetKey.ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_pyads_connection.return_value.write_by_name.assert_called_once_with(
        ADS_VAR, written, pyads.PLCTYPE_BOOL
    )


async def test_state_is_assumed_from_the_actions(
    hass: HomeAssistant, mock_ads_device: MockAdsDevice
) -> None:
    """Test the state follows the last action, once the PLC next sends anything."""
    mock_ads_device.values[ADS_VAR] = BOOL_FALSE
    assert await setup_ads_platform(hass, VALVE_DOMAIN, PLATFORM_CONFIG)

    await hass.services.async_call(
        VALVE_DOMAIN, ValveService.OPEN, {TargetKey.ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == ValveState.CLOSED
    await mock_ads_device.async_push(hass, ADS_VAR, BOOL_FALSE)
    assert hass.states.get(ENTITY_ID).state == ValveState.OPEN

    await hass.services.async_call(
        VALVE_DOMAIN,
        ValveService.CLOSE,
        {TargetKey.ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await mock_ads_device.async_push(hass, ADS_VAR, BOOL_TRUE)
    assert hass.states.get(ENTITY_ID).state == ValveState.CLOSED


async def test_write_error(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing write is logged instead of raised at the caller."""
    mock_ads_device.values[ADS_VAR] = BOOL_FALSE
    assert await setup_ads_platform(hass, VALVE_DOMAIN, PLATFORM_CONFIG)
    mock_pyads_connection.return_value.write_by_name.side_effect = pyads.ADSError(
        err_code=1861
    )

    await hass.services.async_call(
        VALVE_DOMAIN, ValveService.OPEN, {TargetKey.ENTITY_ID: ENTITY_ID}, blocking=True
    )

    assert f"Error writing {ADS_VAR}: ADSError: timeout elapsed (1861)" in caplog.text
