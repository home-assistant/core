"""Tests for the SABnzbd Integration."""
from unittest.mock import patch

from homeassistant.components.sabnzbd import DEFAULT_NAME, DOMAIN, OLD_SENSOR_KEYS
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

MOCK_ENTRY_ID = "mock_entry_id"

MOCK_UNIQUE_ID = "someuniqueid"

MOCK_DEVICE_ID = "somedeviceid"

MOCK_DATA_VERSION_1 = {
    CONF_API_KEY: "api_key",
    CONF_URL: "http://127.0.0.1:8080",
    CONF_NAME: "name",
}

MOCK_ENTRY_VERSION_1 = MockConfigEntry(
    domain=DOMAIN, data=MOCK_DATA_VERSION_1, entry_id=MOCK_ENTRY_ID, version=1
)


async def test_unique_id_migrate(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that config flow entry is migrated correctly."""
    # Start with the config entry at Version 1.
    mock_entry = MOCK_ENTRY_VERSION_1
    mock_entry.add_to_hass(hass)

    mock_d_entry = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, DOMAIN)},
        name=DEFAULT_NAME,
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    entity_id_sensor_key = []

    for sensor_key in OLD_SENSOR_KEYS:
        mock_entity_id = f"{SENSOR_DOMAIN}.{DOMAIN}_{sensor_key}"
        entity_registry.async_get_or_create(
            SENSOR_DOMAIN,
            DOMAIN,
            unique_id=sensor_key,
            config_entry=mock_entry,
            device_id=mock_d_entry.id,
        )
        entity = entity_registry.async_get(mock_entity_id)
        assert entity.entity_id == mock_entity_id
        assert entity.unique_id == sensor_key
        entity_id_sensor_key.append((mock_entity_id, sensor_key))

    with patch(
        "homeassistant.components.sabnzbd.sab.SabnzbdApi.check_available",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)

        await hass.async_block_till_done()

    for mock_entity_id, sensor_key in entity_id_sensor_key:
        entity = entity_registry.async_get(mock_entity_id)
        assert entity.unique_id == f"{MOCK_ENTRY_ID}_{sensor_key}"

    assert device_registry.async_get(mock_d_entry.id).identifiers == {
        (DOMAIN, MOCK_ENTRY_ID)
    }
