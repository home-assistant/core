"""Test init of Coronavirus integration."""
from asynctest import Mock, patch

from homeassistant.components.coronavirus.const import DOMAIN, OPTION_WORLDWIDE
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_registry


async def test_migration(hass):
    """Test that we can migrate coronavirus to stable unique ID."""
    nl_entry = MockConfigEntry(domain=DOMAIN, title="Netherlands", data={"country": 34})
    nl_entry.add_to_hass(hass)
    worldwide_entry = MockConfigEntry(
        domain=DOMAIN, title="Worldwide", data={"country": OPTION_WORLDWIDE}
    )
    worldwide_entry.add_to_hass(hass)
    mock_registry(
        hass,
        {
            "sensor.netherlands_confirmed": entity_registry.RegistryEntry(
                entity_id="sensor.netherlands_confirmed",
                unique_id="34-confirmed",
                platform="coronavirus",
                config_entry_id=nl_entry.entry_id,
            ),
            "sensor.worldwide_confirmed": entity_registry.RegistryEntry(
                entity_id="sensor.worldwide_confirmed",
                unique_id="__worldwide-confirmed",
                platform="coronavirus",
                config_entry_id=worldwide_entry.entry_id,
            ),
        },
    )
    with patch(
        "coronavirus.get_cases",
        return_value=[
            Mock(country="Netherlands", confirmed=10, recovered=8, deaths=1, current=1),
            Mock(country="Germany", confirmed=1, recovered=0, deaths=0, current=0),
        ],
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    ent_reg = await entity_registry.async_get_registry(hass)

    sensor_nl = ent_reg.async_get("sensor.netherlands_confirmed")
    assert sensor_nl.unique_id == "Netherlands-confirmed"

    sensor_worldwide = ent_reg.async_get("sensor.worldwide_confirmed")
    assert sensor_worldwide.unique_id == "__worldwide-confirmed"

    assert hass.states.get("sensor.netherlands_confirmed").state == "10"
    assert hass.states.get("sensor.worldwide_confirmed").state == "11"

    assert nl_entry.unique_id == "Netherlands"
    assert worldwide_entry.unique_id == OPTION_WORLDWIDE
