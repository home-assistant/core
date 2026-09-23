"""Test the Elexa Guardian init module."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.guardian import CONF_UID, DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(name="platforms")
def platforms_fixture() -> list[Platform]:
    """Override to exercise the paired sensor entity setup."""
    return [Platform.SENSOR]


async def test_paired_sensor_via_device_id(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    setup_guardian: None,  # relies on config_entry fixture
) -> None:
    """Test that a paired sensor is linked to the valve controller via via_device_id."""
    # Advance time so the sensor pair dump coordinator refreshes and discovers the
    # paired sensor from the fixture data:
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    valve_controller_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, config_entry.data[CONF_UID]), config_entry.entry_id
    )
    paired_sensor_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "AABBCCDDEEFF"), config_entry.entry_id
    )

    assert valve_controller_device is not None
    assert paired_sensor_device is not None
    assert paired_sensor_device.via_device_id == valve_controller_device.id
