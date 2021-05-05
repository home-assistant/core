"""Tests for the buienradar component."""
from unittest.mock import patch

from homeassistant.components.buienradar import async_setup
from homeassistant.components.buienradar.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers.entity_registry import async_get_registry

from tests.common import MockConfigEntry

TEST_LATITUDE = 51.5288504
TEST_LONGITUDE = 5.4002156


async def test_import_all(hass):
    """Test import of all platforms."""
    config = {
        "weather 1": [{"platform": "buienradar", "name": "test1"}],
        "sensor 1": [{"platform": "buienradar", "timeframe": 30, "name": "test2"}],
        "camera 1": [
            {
                "platform": "buienradar",
                "country_code": "BE",
                "delta": 300,
                "name": "test3",
            }
        ],
    }

    with patch(
        "homeassistant.components.buienradar.async_setup_entry", return_value=True
    ):
        await async_setup(hass, config)
        await hass.async_block_till_done()

    conf_entries = hass.config_entries.async_entries(DOMAIN)

    assert len(conf_entries) == 1

    entry = conf_entries[0]

    assert entry.state == "loaded"
    assert entry.data == {
        "latitude": hass.config.latitude,
        "longitude": hass.config.longitude,
        "timeframe": 30,
        "country_code": "BE",
        "delta": 300,
        "name": "test2",
    }


async def test_import_camera(hass):
    """Test import of camera platform."""
    entity_registry = await async_get_registry(hass)
    entity_registry.async_get_or_create(
        domain="camera",
        platform="buienradar",
        unique_id="512_NL",
        original_name="test_name",
    )
    await hass.async_block_till_done()

    config = {
        "camera 1": [{"platform": "buienradar", "country_code": "NL", "dimension": 512}]
    }

    with patch(
        "homeassistant.components.buienradar.async_setup_entry", return_value=True
    ):
        await async_setup(hass, config)
        await hass.async_block_till_done()

    conf_entries = hass.config_entries.async_entries(DOMAIN)

    assert len(conf_entries) == 1

    entry = conf_entries[0]

    assert entry.state == "loaded"
    assert entry.data == {
        "latitude": hass.config.latitude,
        "longitude": hass.config.longitude,
        "timeframe": 60,
        "country_code": "NL",
        "delta": 600,
        "name": "Buienradar",
    }

    entity_id = entity_registry.async_get_entity_id(
        "camera",
        "buienradar",
        f"{hass.config.latitude:2.6f}{hass.config.longitude:2.6f}",
    )
    assert entity_id
    entity = entity_registry.async_get(entity_id)
    assert entity.original_name == "test_name"


async def test_load_unload(hass):
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LATITUDE: TEST_LATITUDE,
            CONF_LONGITUDE: TEST_LONGITUDE,
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == "loaded"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == "not_loaded"
