"""The tests for the utility_meter select platform."""

from homeassistant.components.utility_meter.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_select_entity_name_config_entry(
    hass: HomeAssistant,
) -> None:
    """Test for Utility Meter select platform."""

    config_entry_config = {
        "cycle": "none",
        "delta_values": False,
        "name": "Energy bill",
        "net_consumption": False,
        "offset": 0,
        "periodically_resetting": True,
        "source": "sensor.energy",
        "tariffs": ["peak", "offpeak"],
    }

    source_config_entry = MockConfigEntry()
    source_config_entry.add_to_hass(hass)
    utility_meter_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options=config_entry_config,
        title=config_entry_config["name"],
    )

    utility_meter_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(utility_meter_config_entry.entry_id)

    await hass.async_block_till_done()

    state = hass.states.get("select.energy_bill")
    assert state is not None
    assert state.attributes.get("friendly_name") == "Energy bill"


async def test_select_entity_name_yaml(
    hass: HomeAssistant,
) -> None:
    """Test for Utility Meter select platform."""

    yaml_config = {
        "utility_meter": {
            "energy_bill": {
                "name": "Energy bill",
                "source": "sensor.energy",
                "tariffs": ["peak", "offpeak"],
                "unique_id": "1234abcd",
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, yaml_config)

    await hass.async_block_till_done()

    state = hass.states.get("select.energy_bill")
    assert state is not None
    assert state.attributes.get("friendly_name") == "Energy bill"


async def test_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for source entity device for Utility Meter."""
    source_config_entry = MockConfigEntry()
    source_config_entry.add_to_hass(hass)
    source_device_entry = device_registry.async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        identifiers={("sensor", "identifier_test")},
        connections={("mac", "30:31:32:33:34:35")},
    )
    source_entity = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source",
        config_entry=source_config_entry,
        device_id=source_device_entry.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("sensor.test_source") is not None

    utility_meter_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "cycle": "monthly",
            "delta_values": False,
            "name": "Energy",
            "net_consumption": False,
            "offset": 0,
            "periodically_resetting": True,
            "source": "sensor.test_source",
            "tariffs": ["peak", "offpeak"],
        },
        title="Energy",
    )

    utility_meter_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(utility_meter_config_entry.entry_id)
    await hass.async_block_till_done()

    utility_meter_entity_select = entity_registry.async_get("select.energy")
    assert utility_meter_entity_select is not None
    assert utility_meter_entity_select.device_id == source_entity.device_id
