"""Test the ADS cover platform."""

from typing import Any
from unittest.mock import MagicMock, call

import pyads
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    CoverEntityStateAttribute,
    CoverService,
    CoverServiceArgument,
    CoverState,
)
from homeassistant.const import STATE_UNKNOWN, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockAdsDevice, async_run_past_first_update, setup_ads_platform

ADS_VAR = "GVL.blind_closed"
ADS_VAR_POSITION = "GVL.blind_position"
ADS_VAR_SET_POSITION = "GVL.blind_set_position"
ADS_VAR_OPEN = "GVL.blind_open"
ADS_VAR_CLOSE = "GVL.blind_close"
ADS_VAR_STOP = "GVL.blind_stop"
ENTITY_ID = "cover.blind"

MINIMAL_CONFIG = {"adsvar": ADS_VAR, "name": "Blind"}
POSITION_CONFIG = {**MINIMAL_CONFIG, "adsvar_position": ADS_VAR_POSITION}
FULL_CONFIG = {
    **POSITION_CONFIG,
    "adsvar_set_position": ADS_VAR_SET_POSITION,
    "adsvar_open": ADS_VAR_OPEN,
    "adsvar_close": ADS_VAR_CLOSE,
    "adsvar_stop": ADS_VAR_STOP,
    "device_class": "shutter",
}

BOOL_TRUE = b"\x01"
BOOL_FALSE = b"\x00"
PLC_VALUES = {ADS_VAR: BOOL_FALSE, ADS_VAR_POSITION: bytes([75])}


@pytest.mark.parametrize(
    ("platform_config", "entity_id"),
    [
        pytest.param({"adsvar": ADS_VAR}, "cover.ads_cover", id="defaults"),
        pytest.param(FULL_CONFIG, ENTITY_ID, id="full"),
    ],
)
async def test_cover(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ads_device: MockAdsDevice,
    snapshot: SnapshotAssertion,
    platform_config: dict[str, Any],
    entity_id: str,
) -> None:
    """Test the cover is created from YAML with the PLC's values."""
    mock_ads_device.values.update(PLC_VALUES)

    assert await setup_ads_platform(
        hass, mock_ads_device, COVER_DOMAIN, platform_config
    )

    assert entity_registry.async_get(entity_id) == snapshot(name="entry")
    assert hass.states.get(entity_id) == snapshot(name="state")


async def test_state_follows_the_plc(
    hass: HomeAssistant, mock_ads_device: MockAdsDevice
) -> None:
    """Test the closed state and the position follow the PLC independently."""
    mock_ads_device.values.update(PLC_VALUES)
    assert await setup_ads_platform(
        hass, mock_ads_device, COVER_DOMAIN, POSITION_CONFIG
    )

    await mock_ads_device.async_push(hass, ADS_VAR_POSITION, bytes([200]))
    state = hass.states.get(ENTITY_ID)
    assert state.state == CoverState.OPEN
    assert state.attributes[CoverEntityStateAttribute.CURRENT_POSITION] == 200

    # A closed cover keeps reporting whatever position the PLC last sent.
    await mock_ads_device.async_push(hass, ADS_VAR, BOOL_TRUE)
    state = hass.states.get(ENTITY_ID)
    assert state.state == CoverState.CLOSED
    assert state.attributes[CoverEntityStateAttribute.CURRENT_POSITION] == 200


@pytest.mark.parametrize(
    ("silent_var", "expected_state", "expected_position"),
    [
        pytest.param(ADS_VAR_POSITION, CoverState.OPEN, None, id="silent_position"),
        pytest.param(ADS_VAR, STATE_UNKNOWN, 75, id="silent_closed"),
    ],
)
async def test_available_with_either_value(
    hass: HomeAssistant,
    mock_ads_device: MockAdsDevice,
    silent_var: str,
    expected_state: str,
    expected_position: int | None,
) -> None:
    """Test the cover is available as soon as either variable has a value."""
    mock_ads_device.values.update(PLC_VALUES)
    del mock_ads_device.values[silent_var]

    assert await async_run_past_first_update(
        hass,
        mock_ads_device,
        setup_ads_platform(hass, mock_ads_device, COVER_DOMAIN, POSITION_CONFIG),
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == expected_state
    assert (
        state.attributes.get(CoverEntityStateAttribute.CURRENT_POSITION)
        == expected_position
    )


@pytest.mark.parametrize(
    ("platform_config", "service", "data", "writes"),
    [
        pytest.param(
            FULL_CONFIG,
            CoverService.OPEN,
            {},
            [call(ADS_VAR_OPEN, True, pyads.PLCTYPE_BOOL)],
            id="open",
        ),
        pytest.param(
            FULL_CONFIG,
            CoverService.CLOSE,
            {},
            [call(ADS_VAR_CLOSE, True, pyads.PLCTYPE_BOOL)],
            id="close",
        ),
        pytest.param(
            FULL_CONFIG,
            CoverService.STOP,
            {},
            [call(ADS_VAR_STOP, True, pyads.PLCTYPE_BOOL)],
            id="stop",
        ),
        pytest.param(
            FULL_CONFIG,
            CoverService.SET_POSITION,
            {CoverServiceArgument.POSITION: 40},
            [call(ADS_VAR_SET_POSITION, 40, pyads.PLCTYPE_BYTE)],
            id="set_position",
        ),
        pytest.param(
            {**MINIMAL_CONFIG, "adsvar_set_position": ADS_VAR_SET_POSITION},
            CoverService.OPEN,
            {},
            [call(ADS_VAR_SET_POSITION, 100, pyads.PLCTYPE_BYTE)],
            id="open_by_position",
        ),
        pytest.param(
            {**MINIMAL_CONFIG, "adsvar_set_position": ADS_VAR_SET_POSITION},
            CoverService.CLOSE,
            {},
            [call(ADS_VAR_SET_POSITION, 0, pyads.PLCTYPE_BYTE)],
            id="close_by_position",
        ),
        # Open and close are always offered, even with nothing to write them to.
        pytest.param(MINIMAL_CONFIG, CoverService.OPEN, {}, [], id="open_unwired"),
        pytest.param(MINIMAL_CONFIG, CoverService.CLOSE, {}, [], id="close_unwired"),
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
    """Test each action writes the variable it is configured with."""
    mock_ads_device.values.update(PLC_VALUES)
    assert await setup_ads_platform(
        hass, mock_ads_device, COVER_DOMAIN, platform_config
    )

    await hass.services.async_call(
        COVER_DOMAIN, service, {TargetKey.ENTITY_ID: ENTITY_ID, **data}, blocking=True
    )

    assert mock_pyads_connection.return_value.write_by_name.call_args_list == writes


async def test_write_error(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing write is logged instead of raised at the caller."""
    mock_ads_device.values.update(PLC_VALUES)
    assert await setup_ads_platform(hass, mock_ads_device, COVER_DOMAIN, FULL_CONFIG)
    mock_pyads_connection.return_value.write_by_name.side_effect = pyads.ADSError(
        err_code=1861
    )

    await hass.services.async_call(
        COVER_DOMAIN, CoverService.OPEN, {TargetKey.ENTITY_ID: ENTITY_ID}, blocking=True
    )

    assert (
        f"Error writing {ADS_VAR_OPEN}: ADSError: timeout elapsed (1861)" in caplog.text
    )
