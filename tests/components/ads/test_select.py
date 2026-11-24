"""Test the ADS select platform."""

import struct
from typing import Any
from unittest.mock import MagicMock

import pyads
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectService,
    SelectServiceArgument,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockAdsDevice, async_run_past_first_update, setup_ads_platform

ADS_VAR = "GVL.mode"
ENTITY_ID = "select.mode"
OPTIONS = ["off", "day", "night"]
PLATFORM_CONFIG = {"adsvar": ADS_VAR, "name": "Mode", "options": OPTIONS}


def int_payload(value: int) -> bytes:
    """Encode a value as the PLC sends an INT."""
    return struct.pack("<h", value)


@pytest.mark.parametrize(
    ("platform_config", "entity_id"),
    [
        pytest.param(PLATFORM_CONFIG, ENTITY_ID, id="named"),
        pytest.param(
            {"adsvar": ADS_VAR, "options": OPTIONS}, "select.ads_select", id="defaults"
        ),
    ],
)
async def test_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ads_device: MockAdsDevice,
    snapshot: SnapshotAssertion,
    platform_config: dict[str, Any],
    entity_id: str,
) -> None:
    """Test the select is created from YAML with the PLC's option."""
    mock_ads_device.values[ADS_VAR] = int_payload(1)

    assert await setup_ads_platform(hass, SELECT_DOMAIN, platform_config)

    assert entity_registry.async_get(entity_id) == snapshot(name="entry")
    assert hass.states.get(entity_id) == snapshot(name="state")


async def test_subscribes_twice(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test the select registers two notifications on its variable as an INT."""
    mock_ads_device.values[ADS_VAR] = int_payload(1)

    assert await setup_ads_platform(hass, SELECT_DOMAIN, PLATFORM_CONFIG)

    calls = mock_pyads_connection.return_value.add_device_notification.call_args_list
    assert [(c.args[0], c.args[1].length) for c in calls] == [
        (ADS_VAR, 2),
        (ADS_VAR, 2),
    ]


@pytest.mark.parametrize(
    ("pushed", "expected"),
    [
        pytest.param(2, "night", id="in_range"),
        pytest.param(3, "day", id="past_the_end"),
        pytest.param(-1, "day", id="negative"),
    ],
)
async def test_option_follows_the_plc(
    hass: HomeAssistant,
    mock_ads_device: MockAdsDevice,
    pushed: int,
    expected: str,
) -> None:
    """Test the option follows the PLC, keeping the last one for out of range values."""
    mock_ads_device.values[ADS_VAR] = int_payload(1)
    assert await setup_ads_platform(hass, SELECT_DOMAIN, PLATFORM_CONFIG)
    assert hass.states.get(ENTITY_ID).state == "day"

    await mock_ads_device.async_push(hass, ADS_VAR, int_payload(pushed))

    assert hass.states.get(ENTITY_ID).state == expected


async def test_unknown_for_an_out_of_range_first_value(
    hass: HomeAssistant, mock_ads_device: MockAdsDevice
) -> None:
    """Test a first value with no matching option leaves the select unknown."""
    mock_ads_device.values[ADS_VAR] = int_payload(7)

    assert await setup_ads_platform(hass, SELECT_DOMAIN, PLATFORM_CONFIG)

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN


async def test_unavailable_until_the_first_value(
    hass: HomeAssistant, mock_ads_device: MockAdsDevice
) -> None:
    """Test the select is unavailable until the PLC delivers a value."""
    assert await async_run_past_first_update(
        hass, mock_ads_device, setup_ads_platform(hass, SELECT_DOMAIN, PLATFORM_CONFIG)
    )
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    await mock_ads_device.async_push(hass, ADS_VAR, int_payload(2))
    assert hass.states.get(ENTITY_ID).state == "night"


async def test_select_option_writes_the_index(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test selecting an option writes its index, and the option is assumed."""
    mock_ads_device.values[ADS_VAR] = int_payload(0)
    assert await setup_ads_platform(hass, SELECT_DOMAIN, PLATFORM_CONFIG)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {TargetKey.ENTITY_ID: ENTITY_ID, SelectServiceArgument.OPTION: "night"},
        blocking=True,
    )

    mock_pyads_connection.return_value.write_by_name.assert_called_once_with(
        ADS_VAR, 2, pyads.PLCTYPE_INT
    )
    # The assumed option only shows once the PLC sends an out of range value,
    # which leaves it in place.
    assert hass.states.get(ENTITY_ID).state == "off"
    await mock_ads_device.async_push(hass, ADS_VAR, int_payload(9))
    assert hass.states.get(ENTITY_ID).state == "night"


async def test_write_error(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing write is logged instead of raised at the caller."""
    mock_ads_device.values[ADS_VAR] = int_payload(0)
    assert await setup_ads_platform(hass, SELECT_DOMAIN, PLATFORM_CONFIG)
    mock_pyads_connection.return_value.write_by_name.side_effect = pyads.ADSError(
        err_code=1861
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {TargetKey.ENTITY_ID: ENTITY_ID, SelectServiceArgument.OPTION: "night"},
        blocking=True,
    )

    assert f"Error writing {ADS_VAR}: ADSError: timeout elapsed (1861)" in caplog.text
