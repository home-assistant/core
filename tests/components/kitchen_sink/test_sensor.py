"""The tests for the kitchen_sink sensor platform."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.kitchen_sink import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
async def sensor_only() -> None:
    """Enable only the sensor platform."""
    with patch(
        "homeassistant.components.kitchen_sink.COMPONENTS_WITH_DEMO_PLATFORM",
        [Platform.SENSOR],
    ):
        yield


@pytest.fixture
async def setup_comp(hass: HomeAssistant, sensor_only):
    """Set up demo component."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()


@pytest.mark.usefixtures("setup_comp")
async def test_states(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the expected sensor entities are added."""
    states = hass.states.async_all()
    assert set(states) == snapshot


@pytest.mark.usefixtures("setup_comp")
async def test_outlet_power_sensors_on_child_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the outlet power sensors are placed on child devices of the power strip."""
    for entity_id in ("sensor.outlet_1_power", "sensor.outlet_2_power"):
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None
        child_device = device_registry.async_get(entity_entry.device_id)
        assert isinstance(child_device, dr.ChildDeviceEntry)
        parent_device = device_registry.async_get(child_device.parent_device_id)
        assert parent_device is not None
        assert not isinstance(parent_device, dr.ChildDeviceEntry)
        assert parent_device.identifiers == {(DOMAIN, "2_ch_power_strip")}


@pytest.mark.usefixtures("sensor_only")
async def test_states_with_subentry(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test the expected sensor entities are added."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={"state": 15},
                subentry_id="blabla",
                subentry_type="entity",
                title="Sensor test",
                unique_id=None,
            )
        ],
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    states = hass.states.async_all()
    assert set(states) == snapshot
