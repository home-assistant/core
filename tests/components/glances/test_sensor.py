"""Tests for glances sensors."""
import pytest

from homeassistant.components.glances.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import HA_SENSOR_DATA, MOCK_USER_INPUT

from tests.common import MockConfigEntry


async def test_sensor_states(hass: HomeAssistant) -> None:
    """Test sensor states are correctly collected from library."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    if state := hass.states.get("sensor.0_0_0_0_ssl_disk_use"):
        assert state.state == HA_SENSOR_DATA["fs"]["/ssl"]["disk_use"]

    if state := hass.states.get("sensor.0_0_0_0_cpu_thermal_1"):
        assert state.state == HA_SENSOR_DATA["sensors"]["cpu_thermal 1"]


@pytest.mark.parametrize(
    ("object_id", "old_unique_id", "new_unique_id"),
    [
        (
            "glances_ssl_used_percent",
            "0.0.0.0-Glances /ssl used percent",
            "/ssl-disk_use_percent",
        ),
        (
            "glances_cpu_thermal_1_temperature",
            "0.0.0.0-Glances cpu_thermal 1 Temperature",
            "cpu_thermal 1-temperature_core",
        ),
    ],
)
async def test_migrate_unique_id(
    hass: HomeAssistant, object_id: str, old_unique_id: str, new_unique_id: str
):
    """Test unique id migration."""
    old_config_data = {**MOCK_USER_INPUT, "name": "Glances"}
    entry = MockConfigEntry(domain=DOMAIN, data=old_config_data)
    entry.add_to_hass(hass)

    ent_reg = er.async_get(hass)

    entity: er.RegistryEntry = ent_reg.async_get_or_create(
        suggested_object_id=object_id,
        disabled_by=None,
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = ent_reg.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == f"{entry.entry_id}-{new_unique_id}"
