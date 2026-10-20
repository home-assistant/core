"""Tests for Broadlink binary sensors."""

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.broadlink.updater import BroadlinkThermostatUpdateManager
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_device

from tests.common import async_fire_time_changed

ENTITY_ID = "binary_sensor.guest_room_heating"


@pytest.mark.parametrize(
    ("active", "expected_state"),
    [
        pytest.param(1, STATE_ON, id="heating"),
        pytest.param(0, STATE_OFF, id="idle"),
    ],
)
async def test_heating(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    active: int,
    expected_state: str,
) -> None:
    """Test the Hysen heating output binary sensor."""
    device = get_device("Guest room")
    mock_api = device.get_mock_api()
    mock_api.get_full_status.return_value = {"active": active}
    await device.setup_entry(hass, mock_api=mock_api)

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == f"{device.mac}-heating"
    assert entry.entity_category is None
    state = hass.states.get(ENTITY_ID)
    assert state.state == expected_state
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.RUNNING


async def test_heating_follows_device(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the heating output state follows the device on each poll."""
    device = get_device("Guest room")
    mock_api = device.get_mock_api()
    mock_api.get_full_status.return_value = {"active": 0}
    await device.setup_entry(hass, mock_api=mock_api)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    mock_api.get_full_status.return_value = {"active": 1}
    freezer.tick(BroadlinkThermostatUpdateManager.SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_heating_not_created_for_other_devices(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test devices other than thermostats get no binary sensors."""
    device = get_device("Office")
    mock_setup = await device.setup_entry(hass)

    assert not [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_setup.entry.entry_id
        )
        if entry.domain == "binary_sensor"
    ]
