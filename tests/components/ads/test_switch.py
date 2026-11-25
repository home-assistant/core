"""Test the ADS switch platform."""

from typing import Any
from unittest.mock import MagicMock

import pyads
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.const import STATE_OFF, STATE_ON, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockAdsDevice, setup_ads_platform

ADS_VAR = "GVL.pump"
ENTITY_ID = "switch.pump"
PLATFORM_CONFIG = {"adsvar": ADS_VAR, "name": "Pump"}

BOOL_TRUE = b"\x01"
BOOL_FALSE = b"\x00"


@pytest.mark.parametrize(
    ("platform_config", "entity_id"),
    [
        pytest.param(PLATFORM_CONFIG, ENTITY_ID, id="named"),
        pytest.param({"adsvar": ADS_VAR}, "switch.ads_switch", id="defaults"),
    ],
)
async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ads_device: MockAdsDevice,
    snapshot: SnapshotAssertion,
    platform_config: dict[str, Any],
    entity_id: str,
) -> None:
    """Test the switch is created from YAML with the PLC's value."""
    mock_ads_device.values[ADS_VAR] = BOOL_TRUE

    assert await setup_ads_platform(
        hass, mock_ads_device, SWITCH_DOMAIN, platform_config
    )

    assert entity_registry.async_get(entity_id) == snapshot(name="entry")
    assert hass.states.get(entity_id) == snapshot(name="state")


async def test_state_follows_the_plc(
    hass: HomeAssistant, mock_ads_device: MockAdsDevice
) -> None:
    """Test the switch follows the values the PLC pushes."""
    mock_ads_device.values[ADS_VAR] = BOOL_TRUE
    assert await setup_ads_platform(
        hass, mock_ads_device, SWITCH_DOMAIN, PLATFORM_CONFIG
    )
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    await mock_ads_device.async_push(hass, ADS_VAR, BOOL_FALSE)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


@pytest.mark.parametrize(
    ("initial", "service", "written"),
    [
        pytest.param(BOOL_FALSE, SwitchService.TURN_ON, True, id="turn_on"),
        pytest.param(BOOL_TRUE, SwitchService.TURN_OFF, False, id="turn_off"),
    ],
)
async def test_actions_write_to_the_plc(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    initial: bytes,
    service: str,
    written: bool,
) -> None:
    """Test the actions write the variable, leaving the state to the PLC."""
    mock_ads_device.values[ADS_VAR] = initial
    assert await setup_ads_platform(
        hass, mock_ads_device, SWITCH_DOMAIN, PLATFORM_CONFIG
    )
    state = hass.states.get(ENTITY_ID).state

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {TargetKey.ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_pyads_connection.return_value.write_by_name.assert_called_once_with(
        ADS_VAR, written, pyads.PLCTYPE_BOOL
    )
    # Nothing changes until the PLC pushes the new value back.
    assert hass.states.get(ENTITY_ID).state == state


async def test_write_error(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing write is logged instead of raised at the caller."""
    mock_ads_device.values[ADS_VAR] = BOOL_FALSE
    assert await setup_ads_platform(
        hass, mock_ads_device, SWITCH_DOMAIN, PLATFORM_CONFIG
    )
    mock_pyads_connection.return_value.write_by_name.side_effect = pyads.ADSError(
        err_code=1861
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_ON,
        {TargetKey.ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert f"Error writing {ADS_VAR}: ADSError: timeout elapsed (1861)" in caplog.text
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
