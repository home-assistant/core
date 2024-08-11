"""Tests for the Jewish Calendar component's init."""

from hdate import Location

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSORS
from homeassistant.components.jewish_calendar import get_unique_prefix
from homeassistant.components.jewish_calendar.const import (
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_DIASPORA,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_DIASPORA,
    DEFAULT_LANGUAGE,
    DOMAIN,
)
from homeassistant.const import CONF_LANGUAGE, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er
from homeassistant.setup import async_setup_component


async def test_import_unique_id_migration(hass: HomeAssistant) -> None:
    """Test unique_id migration."""
    yaml_conf = {
        DOMAIN: {
            CONF_NAME: "test",
            CONF_DIASPORA: DEFAULT_DIASPORA,
            CONF_LANGUAGE: DEFAULT_LANGUAGE,
            CONF_CANDLE_LIGHT_MINUTES: 20,
            CONF_HAVDALAH_OFFSET_MINUTES: 50,
            CONF_LATITUDE: 31.76,
            CONF_LONGITUDE: 35.235,
        }
    }

    # Create an entry in the entity registry with the data from conf
    ent_reg = er.async_get(hass)
    location = Location(
        latitude=yaml_conf[DOMAIN][CONF_LATITUDE],
        longitude=yaml_conf[DOMAIN][CONF_LONGITUDE],
        timezone=hass.config.time_zone,
        diaspora=DEFAULT_DIASPORA,
    )
    old_prefix = get_unique_prefix(location, DEFAULT_LANGUAGE, 20, 50)
    sample_entity = ent_reg.async_get_or_create(
        BINARY_SENSORS,
        DOMAIN,
        unique_id=f"{old_prefix}_erev_shabbat_hag",
        suggested_object_id=f"{DOMAIN}_erev_shabbat_hag",
    )
    # Save the existing unique_id, DEFAULT_LANGUAGE should be part of it
    old_unique_id = sample_entity.unique_id
    assert DEFAULT_LANGUAGE in old_unique_id

    # Simulate HomeAssistant setting up the component
    assert await async_setup_component(hass, DOMAIN, yaml_conf.copy())
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    for entry_key, entry_val in entries[0].data.items():
        assert entry_val == yaml_conf[DOMAIN][entry_key]
    for entry_key, entry_val in entries[0].options.items():
        assert entry_val == yaml_conf[DOMAIN][entry_key]

    # Assert that the unique_id was updated
    new_unique_id = ent_reg.async_get(sample_entity.entity_id).unique_id
    assert new_unique_id != old_unique_id
    assert DEFAULT_LANGUAGE not in new_unique_id

    # Confirm that when the component is reloaded, the unique_id is not changed
    assert ent_reg.async_get(sample_entity.entity_id).unique_id == new_unique_id

    # Confirm that all the unique_ids are prefixed correctly
    await hass.config_entries.async_reload(entries[0].entry_id)
    er_entries = er.async_entries_for_config_entry(ent_reg, entries[0].entry_id)
    assert all(entry.unique_id.startswith(entries[0].entry_id) for entry in er_entries)
