"""Tests for the SABnzbd Integration."""
from unittest.mock import patch

import pytest

from homeassistant.components import sabnzbd
from homeassistant.components.sabnzbd import DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType

from tests.common import MockConfigEntry, mock_device_registry, mock_registry

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


@pytest.fixture
def device_registry(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_registry(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


async def test_unique_id_migrate(hass, device_registry, entity_registry):
    """Test that config flow entry is migrated correctly."""
    # Start with the config entry at Version 1.
    manager = hass.config_entries
    mock_entry = MOCK_ENTRY_VERSION_1
    mock_entry.add_to_manager(manager)

    mock_d_entry = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, DOMAIN)},
        name=DEFAULT_NAME,
        entry_type=DeviceEntryType.SERVICE,
    )

    mock_entity_id = f"sabnzbd.sabnzbd_{MOCK_UNIQUE_ID}"
    mock_e_entry = entity_registry.async_get_or_create(
        DOMAIN,
        DOMAIN,
        unique_id=MOCK_UNIQUE_ID,
        config_entry=mock_entry,
        device_id=mock_d_entry.id,
    )
    assert len(entity_registry.entities) == 1
    assert mock_e_entry.entity_id == mock_entity_id
    assert mock_e_entry.unique_id == MOCK_UNIQUE_ID

    with patch(
        "homeassistant.helpers.device_registry.async_get",
        return_value=device_registry,
    ), patch(
        "homeassistant.helpers.entity_registry.async_get",
        return_value=entity_registry,
    ), patch(
        "homeassistant.components.sabnzbd.sab.SabnzbdApi.check_available",
        return_value=True,
    ):
        await sabnzbd.migrate_unique_id(hass, mock_entry)

    await hass.async_block_till_done()

    assert len(entity_registry.entities) == 1
    mock_entity = entity_registry.entities.data.popitem()[1]

    assert mock_entity.entity_id == mock_entity_id
    assert mock_entity.unique_id == f"{MOCK_ENTRY_ID}_{MOCK_UNIQUE_ID}"
    assert mock_entity.device_id == mock_d_entry.id

    sabnzbd.update_device_identifiers(hass, mock_entry)

    assert device_registry.devices[mock_d_entry.id].identifiers == {
        (DOMAIN, mock_entry.entry_id)
    }
