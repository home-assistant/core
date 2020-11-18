"""Test cases for the initialisation of the Huisbaasje integration."""
from homeassistant.components import huisbaasje
from homeassistant.config_entries import (
    CONN_CLASS_CLOUD_POLL,
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ConfigEntry,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_setup(hass: HomeAssistant):
    """Test for successfully setting up the platform."""
    assert await async_setup_component(hass, huisbaasje.DOMAIN, {})
    await hass.async_block_till_done()
    assert huisbaasje.DOMAIN in hass.config.components


async def test_setup_entry(hass: HomeAssistant):
    """Test for successfully setting a config entry."""
    hass.config.components.add(huisbaasje.DOMAIN)
    config_entry = ConfigEntry(
        1,
        huisbaasje.DOMAIN,
        "userId",
        {
            huisbaasje.CONF_ID: "userId",
            huisbaasje.CONF_USERNAME: "username",
            huisbaasje.CONF_PASSWORD: "password",
        },
        "test",
        CONN_CLASS_CLOUD_POLL,
        system_options={},
    )
    hass.config_entries._entries.append(config_entry)

    assert config_entry.state == ENTRY_STATE_NOT_LOADED
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Assert integration is loaded
    assert config_entry.state == ENTRY_STATE_LOADED
    assert huisbaasje.DOMAIN in hass.config.components
    assert huisbaasje.DOMAIN in hass.data
    assert "userId" in hass.data[huisbaasje.DOMAIN]

    # Assert entities are loaded
    entities = hass.states.async_entity_ids("sensor")
    assert len(entities) == 8
    assert hass.states.get("sensor.huisbaasje_current_power").state == "unavailable"
    assert hass.states.get("sensor.huisbaasje_current_power_in").state == "unavailable"
    assert (
        hass.states.get("sensor.huisbaasje_current_power_in_low").state == "unavailable"
    )
    assert hass.states.get("sensor.huisbaasje_current_power_out").state == "unavailable"
    assert (
        hass.states.get("sensor.huisbaasje_current_power_out_low").state
        == "unavailable"
    )
    assert hass.states.get("sensor.huisbaasje_current_gas").state == "unavailable"
    assert hass.states.get("sensor.huisbaasje_energy_today").state == "unavailable"
    assert hass.states.get("sensor.huisbaasje_gas_today").state == "unavailable"


async def test_unload_entry(hass: HomeAssistant):
    """Test for successfully unloading the config entry."""
    hass.config.components.add(huisbaasje.DOMAIN)
    config_entry = ConfigEntry(
        1,
        huisbaasje.DOMAIN,
        "userId",
        {
            huisbaasje.CONF_ID: "userId",
            huisbaasje.CONF_USERNAME: "username",
            huisbaasje.CONF_PASSWORD: "password",
        },
        "test",
        CONN_CLASS_CLOUD_POLL,
        system_options={},
    )
    hass.config_entries._entries.append(config_entry)

    # Load config entry
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state == ENTRY_STATE_LOADED
    entities = hass.states.async_entity_ids("sensor")
    assert len(entities) == 8

    # Unload config entry
    await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state == ENTRY_STATE_NOT_LOADED
    entities = hass.states.async_entity_ids("sensor")
    assert len(entities) == 0
