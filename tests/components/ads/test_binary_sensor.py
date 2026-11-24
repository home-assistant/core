"""Test the ADS binary sensor platform."""

from typing import Any
from unittest.mock import MagicMock

import pyads
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockAdsDevice, async_run_past_first_update, setup_ads_platform

ADS_VAR = "GVL.motion"
ENTITY_ID = "binary_sensor.motion"
PLATFORM_CONFIG = {"adsvar": ADS_VAR, "name": "Motion"}

BOOL_TRUE = b"\x01"
BOOL_FALSE = b"\x00"


@pytest.mark.parametrize(
    ("platform_config", "entity_id"),
    [
        pytest.param(
            {**PLATFORM_CONFIG, "device_class": "motion"}, ENTITY_ID, id="motion"
        ),
        pytest.param(
            {"adsvar": ADS_VAR}, "binary_sensor.ads_binary_sensor", id="defaults"
        ),
    ],
)
async def test_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ads_device: MockAdsDevice,
    snapshot: SnapshotAssertion,
    platform_config: dict[str, Any],
    entity_id: str,
) -> None:
    """Test the binary sensor is created from YAML with the PLC's value."""
    mock_ads_device.values[ADS_VAR] = BOOL_TRUE

    assert await setup_ads_platform(
        hass, mock_ads_device, BINARY_SENSOR_DOMAIN, platform_config
    )

    assert entity_registry.async_get(entity_id) == snapshot(name="entry")
    assert hass.states.get(entity_id) == snapshot(name="state")


async def test_subscribes_to_a_bool(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test the binary sensor asks the PLC to notify on its variable as a BOOL."""
    mock_ads_device.values[ADS_VAR] = BOOL_TRUE

    assert await setup_ads_platform(
        hass, mock_ads_device, BINARY_SENSOR_DOMAIN, PLATFORM_CONFIG
    )

    add_device_notification = mock_pyads_connection.return_value.add_device_notification
    add_device_notification.assert_called_once()
    name, attr, _ = add_device_notification.call_args.args
    assert name == ADS_VAR
    assert attr.length == 1


async def test_state_follows_the_plc(
    hass: HomeAssistant, mock_ads_device: MockAdsDevice
) -> None:
    """Test the binary sensor follows the values the PLC pushes."""
    mock_ads_device.values[ADS_VAR] = BOOL_TRUE
    assert await setup_ads_platform(
        hass, mock_ads_device, BINARY_SENSOR_DOMAIN, PLATFORM_CONFIG
    )
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    await mock_ads_device.async_push(hass, ADS_VAR, BOOL_FALSE)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    await mock_ads_device.async_push(hass, ADS_VAR, BOOL_TRUE)
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_unavailable_until_the_first_value(
    hass: HomeAssistant, mock_ads_device: MockAdsDevice
) -> None:
    """Test the binary sensor is unavailable until the PLC delivers a value."""
    assert await async_run_past_first_update(
        hass,
        mock_ads_device,
        setup_ads_platform(
            hass, mock_ads_device, BINARY_SENSOR_DOMAIN, PLATFORM_CONFIG
        ),
    )
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    await mock_ads_device.async_push(hass, ADS_VAR, BOOL_TRUE)
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_subscription_error(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a variable the PLC refuses leaves the binary sensor unavailable."""
    mock_pyads_connection.return_value.add_device_notification.side_effect = (
        pyads.ADSError(err_code=1808)
    )

    assert await async_run_past_first_update(
        hass,
        mock_ads_device,
        setup_ads_platform(
            hass, mock_ads_device, BINARY_SENSOR_DOMAIN, PLATFORM_CONFIG
        ),
    )

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert f"Error subscribing to {ADS_VAR}" in caplog.text
