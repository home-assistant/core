"""The test for the min/max sensor platform."""

from homeassistant.components.min_max.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
import homeassistant.helpers.entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

VALUES = [17, 20, 15.3]
MIN_VALUE = min(VALUES)


async def test_sensor_setup_entry_to_group_sensor(hass: HomeAssistant) -> None:
    """Test the sensor imported to Group sensor."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "test_min",
            "type": "min",
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "round_digits": 2,
        },
        title="test_min",
    )

    entity_ids = config_entry.options["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_integration")
    assert issue

    state = hass.states.get("sensor.sensor_group_test_min")
    assert state.state == str(MIN_VALUE)

    entity_reg = er.async_get(hass)
    entity = entity_reg.async_get("sensor.sensor_group_test_min")

    assert entity.config_entry_id != config_entry
    assert entity.platform == "group"


async def test_sensor_setup_yaml_to_group_sensor(hass: HomeAssistant) -> None:
    """Test the sensor to Group sensor from YAML."""
    config = {
        "sensor": {
            "platform": DOMAIN,
            "name": "test_min",
            "type": "min",
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id",
        }
    }

    entity_ids = config["sensor"]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_integration_yaml")
    assert issue

    state = hass.states.get("sensor.test_min")
    assert state.state == str(MIN_VALUE)

    entity_reg = er.async_get(hass)
    entity = entity_reg.async_get("sensor.test_min")

    assert entity.unique_id == "very_unique_id"
    assert entity.platform == "min_max"
