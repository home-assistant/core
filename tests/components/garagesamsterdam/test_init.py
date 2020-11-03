"""Test init of Garages Amsterdam integration."""
from homeassistant.components.garagesamsterdam.const import DOMAIN
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_registry


async def test_migration(hass):
    """Test that we can migrate garagesamsterdam to stable unique ID."""
    garage_entry = MockConfigEntry(
        domain=DOMAIN, title="IJDok", data={"garage_name": "IJDok"}
    )
    garage_entry.add_to_hass(hass)
    mock_registry(
        hass,
        {
            "sensor.ijdok_free_space_short": entity_registry.RegistryEntry(
                entity_id="sensor.ijdok_free_space_short",
                unique_id="IJDok-free_space_short",
                platform="garagesamsterdam",
                config_entry_id=garage_entry.entry_id,
            )
        },
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    ent_reg = await entity_registry.async_get_registry(hass)

    sensor_garage = ent_reg.async_get("sensor.ijdok_free_space_short")
    assert sensor_garage.unique_id == "IJDok-free_space_short"

    assert hass.states.get("sensor.ijdok_free_space_short").state == "100"
    assert garage_entry.unique_id == "IJDok"
