"""Test the laundrify sensor platform."""

from datetime import timedelta
import json
import logging
from unittest.mock import AsyncMock, patch

from laundrify_aio import LaundrifyDevice
import pytest

from homeassistant.components.laundrify.const import DOMAIN, MANUFACTURER, MODELS
from homeassistant.components.laundrify.sensor import LaundrifyPowerSensor
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
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture


@pytest.fixture(name="laundrify_sensor")
def laundrify_sensor_fixture() -> LaundrifyPowerSensor:
    """Return a default Laundrify power sensor mock."""
    # Load test data from machines.json
    machine_data = json.loads(load_fixture("laundrify/machines.json"))[0]

    mock_device = AsyncMock(spec=LaundrifyDevice)
    mock_device.id = machine_data["id"]
    mock_device.manufacturer = MANUFACTURER
    mock_device.model = machine_data["model"]
    mock_device.name = machine_data["name"]
    mock_device.firmwareVersion = machine_data["firmwareVersion"]
    return LaundrifyPowerSensor(mock_device)


async def test_laundrify_sensor_init(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    laundrify_sensor: LaundrifyPowerSensor,
    laundrify_config_entry: MockConfigEntry,
) -> None:
    """Test Laundrify sensor default state."""
    sensor = laundrify_sensor
    sensor_slug = slugify(sensor._device.name, separator="_")

    state = hass.states.get(f"sensor.{sensor_slug}_power")
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.POWER
    assert state.state == STATE_UNKNOWN

    device = device_registry.async_get_device({(DOMAIN, sensor._device.id)})
    assert device is not None
    assert device.name == sensor._device.name
    assert device.identifiers == {(DOMAIN, sensor._device.id)}
    assert device.manufacturer == sensor._device.manufacturer
    assert device.model == MODELS[sensor._device.model]
    assert device.sw_version == sensor._device.firmwareVersion


async def test_laundrify_sensor_update(
    hass: HomeAssistant,
    laundrify_sensor: LaundrifyPowerSensor,
    laundrify_config_entry: MockConfigEntry,
) -> None:
    """Test Laundrify sensor update."""
    sensor = laundrify_sensor
    sensor_slug = slugify(sensor._device.name, separator="_")

    state = hass.states.get(f"sensor.{sensor_slug}_power")
    assert state.state == STATE_UNKNOWN

    with patch("laundrify_aio.LaundrifyDevice.get_power", return_value=95):
        future = utcnow() + timedelta(minutes=2)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get(f"sensor.{sensor_slug}_power")
        assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfPower.WATT
        assert state.state == "95"


async def test_laundrify_sensor_update_failure(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    laundrify_sensor: LaundrifyPowerSensor,
    laundrify_config_entry: MockConfigEntry,
) -> None:
    """Test that update failures are logged."""
    caplog.set_level(logging.DEBUG)
    sensor = laundrify_sensor

    # test get_power() returning None which should cause a LaundrifyDeviceException
    with patch("laundrify_aio.LaundrifyDevice.get_power", return_value=None):
        future = utcnow() + timedelta(minutes=2)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        assert f"Couldn't load power for {sensor.unique_id}" in caplog.text
