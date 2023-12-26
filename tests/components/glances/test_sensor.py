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

    if state := hass.states.get("sensor.0_0_0_0_ssl_used"):
        assert state.state == str(HA_SENSOR_DATA["fs"]["/ssl"]["disk_use"])
    if state := hass.states.get("sensor.0_0_0_0_cpu_thermal_1_temperature"):
        assert state.state == str(
            HA_SENSOR_DATA["sensors"]["cpu_thermal 1"]["temperature_core"]
        )
    if state := hass.states.get("sensor.0_0_0_0_err_temp_temperature"):
        assert state.state == str(
            HA_SENSOR_DATA["sensors"]["err_temp"]["temperature_hdd"]
        )
    if state := hass.states.get("sensor.0_0_0_0_na_temp_temperature"):
        assert state.state == str(
            HA_SENSOR_DATA["sensors"]["na_temp"]["temperature_hdd"]
        )
    if state := hass.states.get("sensor.0_0_0_0_ram_used_percent"):
        assert state.state == str(HA_SENSOR_DATA["mem"]["memory_use_percent"])
    if state := hass.states.get("sensor.0_0_0_0_containers_active"):
        assert state.state == str(HA_SENSOR_DATA["docker"]["docker_active"])
    if state := hass.states.get("sensor.0_0_0_0_containers_cpu_used"):
        assert state.state == str(HA_SENSOR_DATA["docker"]["docker_cpu_use"])
    if state := hass.states.get("sensor.0_0_0_0_containers_ram_used"):
        assert state.state == str(HA_SENSOR_DATA["docker"]["docker_memory_use"])
    if state := hass.states.get("sensor.0_0_0_0_md3_raid_available"):
        assert state.state == str(HA_SENSOR_DATA["raid"]["md3"]["available"])
    if state := hass.states.get("sensor.0_0_0_0_md3_raid_used"):
        assert state.state == str(HA_SENSOR_DATA["raid"]["md3"]["used"])
    if state := hass.states.get("sensor.0_0_0_0_md1_raid_available"):
        assert state.state == str(HA_SENSOR_DATA["raid"]["md1"]["available"])
    if state := hass.states.get("sensor.0_0_0_0_md1_raid_used"):
        assert state.state == str(HA_SENSOR_DATA["raid"]["md1"]["used"])


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
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    object_id: str,
    old_unique_id: str,
    new_unique_id: str,
) -> None:
    """Test unique id migration."""
    old_config_data = {**MOCK_USER_INPUT, "name": "Glances"}
    entry = MockConfigEntry(domain=DOMAIN, data=old_config_data)
    entry.add_to_hass(hass)

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
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

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == f"{entry.entry_id}-{new_unique_id}"
