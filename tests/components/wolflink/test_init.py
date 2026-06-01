"""Test the Wolf SmartSet Service."""

from unittest.mock import patch

from httpx import RequestError

from homeassistant.components.wolflink.const import DEVICE_ID, DOMAIN, MANUFACTURER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

LEGACY_CONFIG = {
    "device_name": "test-device",
    "device_id": 1234,
    "device_gateway": 5678,
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


async def test_migration_v1_1_to_v2(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test migration from v1.1 (int unique_id, device-oriented) to v2 (hub-oriented)."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=1234, data=LEGACY_CONFIG, version=1, minor_version=1
    )
    config_entry.add_to_hass(hass)

    device_id = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, 1234)},
        configuration_url="https://www.wolf-smartset.com/",
        manufacturer=MANUFACTURER,
    ).id

    assert config_entry.version == 1
    assert config_entry.minor_version == 1
    assert config_entry.unique_id == 1234
    assert device_registry.async_get(device_id).identifiers == {(DOMAIN, 1234)}

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert config_entry.unique_id == "test-username"
    assert config_entry.data == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        DEVICE_ID: [1234],
    }

    assert device_registry.async_get(device_id).identifiers == {(DOMAIN, "1234")}


async def test_migration_v1_2_to_v2(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test migration from v1.2 (str unique_id, device-oriented) to v2 (hub-oriented)."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data=LEGACY_CONFIG,
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "1234")},
        configuration_url="https://www.wolf-smartset.com/",
        manufacturer=MANUFACTURER,
    )

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert config_entry.unique_id == "test-username"
    assert config_entry.data == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        DEVICE_ID: [1234],
    }


async def test_migration_merges_duplicate_v1_entries(hass: HomeAssistant) -> None:
    """Test that migrating two v1 entries for the same account merges them into one v2 entry."""
    first_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={**LEGACY_CONFIG, "device_id": 1234},
        version=1,
        minor_version=2,
    )
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="5678",
        data={**LEGACY_CONFIG, "device_id": 5678},
        version=1,
        minor_version=2,
    )
    first_entry.add_to_hass(hass)
    second_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        # Migrate the first entry — becomes the v2 hub entry.
        await hass.config_entries.async_setup(first_entry.entry_id)
        # Migrate the second entry — should merge into the first and be removed.
        await second_entry.async_migrate(hass)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    surviving = entries[0]
    assert surviving.entry_id == first_entry.entry_id
    assert surviving.unique_id == "test-username"
    assert surviving.version == 2
    assert surviving.minor_version == 1
    assert sorted(surviving.data[DEVICE_ID]) == [1234, 5678]
