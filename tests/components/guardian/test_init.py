"""Test the Elexa Guardian init module."""

import pytest

from homeassistant.components.guardian import CONF_UID, DOMAIN, GuardianData
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.fixture(name="platforms")
def platforms_fixture() -> list[Platform]:
    """Override to exercise the paired sensor entity setup."""
    return [Platform.SENSOR]


async def test_paired_sensor_via_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    setup_guardian: None,  # relies on config_entry fixture
) -> None:
    """Test that a paired sensor is linked to the valve controller via via_device_id."""
    data: GuardianData = config_entry.runtime_data

    await data.paired_sensor_manager.async_pair_sensor("AABBCCDDEEFF")
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
