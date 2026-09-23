"""Test the LIFX sensor platform."""

from lifx import FirmwareInfo, WifiInfo
import pytest

from homeassistant.components import lifx
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import SERIAL, async_setup_lifx_entry, async_trigger_update
from .helpers import create_mock_light


@pytest.mark.parametrize(
    ("firmware", "unit"),
    [
        pytest.param((2, 77), SIGNAL_STRENGTH_DECIBELS, id="db"),
        pytest.param((4, 0), SIGNAL_STRENGTH_DECIBELS_MILLIWATT, id="dbm"),
    ],
)
async def test_rssi_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    firmware: tuple[int, int],
    unit: str,
) -> None:
    """Test RSSI uses the public WifiInfo value and unit."""
    entity_registry.async_get_or_create(
        "sensor",
        lifx.DOMAIN,
        f"{SERIAL}_rssi",
        disabled_by=None,
        suggested_object_id="my_group_my_bulb_rssi",
    )
    device = create_mock_light()
    device.state.wifi_info = WifiInfo(0.000001, FirmwareInfo(0, *firmware))

    await async_setup_lifx_entry(hass, device)

    await async_trigger_update(hass)

    # The signal is only requested while the sensor is enabled
    assert device.fetch_wifi_info is True

    state = hass.states.get("sensor.my_group_my_bulb_rssi")
    assert state
    assert state.state == "-60"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == unit
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.SIGNAL_STRENGTH
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT


async def test_rssi_signal_is_not_read_while_the_sensor_is_disabled(
    hass: HomeAssistant,
) -> None:
    """Test the signal is left out of the poll until the sensor is enabled."""
    device = create_mock_light()

    await async_setup_lifx_entry(hass, device)

    await async_trigger_update(hass)

    assert device.fetch_wifi_info is False
