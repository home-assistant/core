"""Test the laundrify sensor platform."""

from datetime import timedelta
import logging
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from laundrify_aio import LaundrifyDevice
from laundrify_aio.exceptions import LaundrifyDeviceException
import pytest

from homeassistant.components.laundrify.const import (
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MODELS,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import slugify

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_laundrify_sensor_init(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_device: LaundrifyDevice,
    laundrify_config_entry: MockConfigEntry,
) -> None:
    """Test Laundrify sensor default state."""
    device_slug = slugify(mock_device.name, separator="_")

    state = hass.states.get(f"sensor.{device_slug}_power")
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.POWER
    assert state.state == STATE_UNKNOWN

    device = device_registry.async_get_device({(DOMAIN, mock_device.id)})
    assert device is not None
    assert device.name == mock_device.name
    assert device.identifiers == {(DOMAIN, mock_device.id)}
    assert device.manufacturer == mock_device.manufacturer
    assert device.model == MODELS[mock_device.model]
    assert device.sw_version == mock_device.firmwareVersion


async def test_laundrify_sensor_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_device: LaundrifyDevice,
    laundrify_config_entry: MockConfigEntry,
) -> None:
    """Test Laundrify sensor update."""
    device_slug = slugify(mock_device.name, separator="_")

    state = hass.states.get(f"sensor.{device_slug}_power")
    assert state.state == STATE_UNKNOWN

    with patch("laundrify_aio.LaundrifyDevice.get_power", return_value=95):
        freezer.tick(timedelta(seconds=DEFAULT_POLL_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get(f"sensor.{device_slug}_power")
        assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfPower.WATT
        assert state.state == "95"


async def test_laundrify_sensor_update_failure(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
    mock_device: LaundrifyDevice,
    laundrify_config_entry: MockConfigEntry,
) -> None:
    """Test that update failures are logged."""
    caplog.set_level(logging.DEBUG)

    # test get_power() to raise a LaundrifyDeviceException
    with patch(
        "laundrify_aio.LaundrifyDevice.get_power",
        side_effect=LaundrifyDeviceException("Raising error to test update failure."),
    ):
        freezer.tick(timedelta(seconds=DEFAULT_POLL_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert f"Couldn't load power for {mock_device.id}_power" in caplog.text
