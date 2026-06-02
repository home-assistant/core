"""Test the Wolf SmartSet Service."""

from unittest.mock import MagicMock, patch

from httpx import RequestError
import pytest

from homeassistant.components.wolflink.const import (
    DEVICE_ID,
    DOMAIN,
    MANUFACTURER,
    SUBENTRY_TYPE_DEVICE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

LEGACY_CONFIG = {
    "device_name": "test-device",
    "device_id": 1234,
    "device_gateway": 5678,
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


def _assert_v2_2_hub(entry: MockConfigEntry) -> None:
    """Assert an entry has been migrated to the v2.2 hub schema."""
    assert entry.version == 2
    assert entry.minor_version == 2
    assert entry.unique_id == "test-username"
    assert entry.data == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert DEVICE_ID not in entry.data


async def test_migration_v1_1_to_v2_2(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test migration from v1.1 (int unique_id, device-oriented) to v2.2 hub-with-subentries."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=1234, data=LEGACY_CONFIG, version=1, minor_version=1
    )
    config_entry.add_to_hass(hass)

    device_id = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, 1234)},
        configuration_url="https://www.wolf-smartset.com/",
        manufacturer=MANUFACTURER,
        name="test-device",
    ).id

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    _assert_v2_2_hub(config_entry)
    subentries = list(config_entry.subentries.values())
    assert len(subentries) == 1
    subentry = subentries[0]
    assert subentry.subentry_type == SUBENTRY_TYPE_DEVICE
    assert subentry.unique_id == "1234"
    assert subentry.title == "test-device"
    assert subentry.data == {DEVICE_ID: 1234}

    # The device-registry identifier was rewritten to a string and the device
    # is now attached to the new subentry.
    device = device_registry.async_get(device_id)
    assert device is not None
    assert device.identifiers == {(DOMAIN, "1234")}
    assert device.config_entries_subentries == {
        config_entry.entry_id: {subentry.subentry_id}
    }


async def test_migration_v1_2_to_v2_2(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test migration from v1.2 (str unique_id, device-oriented) to v2.2."""
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
        name="test-device",
    )

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    _assert_v2_2_hub(config_entry)
    subentries = list(config_entry.subentries.values())
    assert len(subentries) == 1
    assert subentries[0].unique_id == "1234"


async def test_migration_v1_reattaches_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test v1 migration moves existing entities onto the new device subentry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data=LEGACY_CONFIG,
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "1234")},
        manufacturer=MANUFACTURER,
        name="test-device",
    )
    entity = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="1234:6005200000",
        config_entry=config_entry,
        device_id=device.id,
    )

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    subentry_id = next(iter(config_entry.subentries))
    updated = entity_registry.async_get(entity.entity_id)
    assert updated is not None
    assert updated.config_entry_id == config_entry.entry_id
    assert updated.config_subentry_id == subentry_id


async def test_migration_v1_disabled_by_fixup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test CONFIG_ENTRY-disabled rows are converted to USER/DEVICE on migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data=LEGACY_CONFIG,
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "1234")},
        manufacturer=MANUFACTURER,
        name="test-device",
    )
    device_registry.async_update_device(
        device.id, disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY
    )
    entity = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="1234:6005200000",
        config_entry=config_entry,
        device_id=device.id,
        disabled_by=er.RegistryEntryDisabler.CONFIG_ENTRY,
    )

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert (
        device_registry.async_get(device.id).disabled_by is dr.DeviceEntryDisabler.USER
    )
    assert (
        entity_registry.async_get(entity.entity_id).disabled_by
        is er.RegistryEntryDisabler.DEVICE
    )


async def test_migration_merges_duplicate_v1_entries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test two v1 entries for the same account merge into one v2.2 entry with subentries."""
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

    # Pre-register the second entry's device so the sibling-merge path also
    # exercises the device-reattachment branch (remove_config_entry_id=other).
    device_registry.async_get_or_create(
        config_entry_id=second_entry.entry_id,
        identifiers={(DOMAIN, "5678")},
        manufacturer=MANUFACTURER,
        name="second-device",
    )

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(first_entry.entry_id)
        await second_entry.async_migrate(hass)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    surviving = entries[0]
    assert surviving.entry_id == first_entry.entry_id
    _assert_v2_2_hub(surviving)
    subentries = {s.unique_id: s for s in surviving.subentries.values()}
    assert set(subentries) == {"1234", "5678"}

    # The pre-existing device-registry row for 5678 was reattached to the
    # surviving entry and its merged subentry.
    device = device_registry.async_get_device(identifiers={(DOMAIN, "5678")})
    assert device is not None
    assert device.config_entries == {surviving.entry_id}
    assert device.config_entries_subentries == {
        surviving.entry_id: {subentries["5678"].subentry_id}
    }


@pytest.mark.parametrize(
    "stored_ids",
    [
        pytest.param([1234, 5678], id="list_of_int"),
        pytest.param(["1234", "5678"], id="list_of_str"),
    ],
)
async def test_migration_v1_with_list_device_id(
    hass: HomeAssistant, stored_ids: list[int] | list[str]
) -> None:
    """Test v1 migration tolerates DEVICE_ID stored as a list of int or str."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={**LEGACY_CONFIG, "device_id": stored_ids},
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    _assert_v2_2_hub(config_entry)
    assert sorted(s.unique_id for s in config_entry.subentries.values()) == [
        "1234",
        "5678",
    ]


async def test_migration_v2_1_to_v2_2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test v2.1 (DEVICE_ID list in entry data) migrates to v2.2 subentries."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            DEVICE_ID: [1234, 5678],
        },
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    for device_id, name in ((1234, "first"), (5678, "second")):
        device = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, str(device_id))},
            manufacturer=MANUFACTURER,
            name=name,
        )
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id=f"{device_id}:6005200000",
            config_entry=config_entry,
            device_id=device.id,
        )

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.side_effect = RequestError(
            "Unable to connect"
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

    _assert_v2_2_hub(config_entry)
    subentries_by_uid = {s.unique_id: s for s in config_entry.subentries.values()}
    assert set(subentries_by_uid) == {"1234", "5678"}
    assert subentries_by_uid["1234"].title == "first"
    assert subentries_by_uid["5678"].title == "second"

    for device_id, expected_uid in ((1234, "1234"), (5678, "5678")):
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, str(device_id))}
        )
        assert device is not None
        assert device.config_entries_subentries == {
            config_entry.entry_id: {subentries_by_uid[expected_uid].subentry_id}
        }


async def test_setup_no_devices_on_account(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup raises ConfigEntryNotReady if the account has no devices."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.WolfClient",
        autospec=True,
    ) as wolf_mock:
        wolf_mock.return_value.fetch_system_list.return_value = []
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # No subentries set up, but the entry itself loads cleanly.
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data == {}


async def test_migrate_future_version_aborts(hass: HomeAssistant) -> None:
    """Test migration refuses to downgrade a future-version entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
        version=3,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_migrate_future_minor_version_aborts(hass: HomeAssistant) -> None:
    """Test migration refuses to downgrade a future-minor-version entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
        version=2,
        minor_version=3,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_setup_fetch_parameters_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wolflink: MagicMock,
) -> None:
    """Test a subentry whose parameter fetch fails is skipped, not the whole entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wolflink.fetch_parameters",
        side_effect=RequestError("Unable to fetch parameters"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data == {}


async def test_setup_skips_subentries_with_missing_device(
    hass: HomeAssistant, mock_wolflink: MagicMock
) -> None:
    """Test subentries whose device is gone from the account are skipped."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
        version=2,
        minor_version=2,
        subentries_data=[
            {
                "data": {DEVICE_ID: 9999},
                "subentry_type": SUBENTRY_TYPE_DEVICE,
                "title": "vanished",
                "unique_id": "9999",
            }
        ],
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data == {}
