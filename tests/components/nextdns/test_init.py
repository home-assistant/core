"""Test init of NextDNS integration."""

from unittest.mock import AsyncMock

from nextdns import ApiError, InvalidApiKeyError
import pytest
from tenacity import RetryError

from homeassistant.components.nextdns.const import (
    CONF_PROFILE_ID,
    DOMAIN,
    SUBENTRY_TYPE_PROFILE,
)
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.const import CONF_API_KEY, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test a successful setup entry."""
    await init_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.fake_profile_dns_queries_blocked_ratio")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "20.0"


@pytest.mark.parametrize(
    "exc", [ApiError("API Error"), RetryError("Retry Error"), TimeoutError]
)
async def test_config_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns: AsyncMock,
    exc: Exception,
) -> None:
    """Test for setup failure if the connection to the service fails."""
    mock_nextdns.create.side_effect = exc

    await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
    mock_nextdns: AsyncMock,
) -> None:
    """Test successful unload of entry."""
    await init_integration(hass, mock_config_entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns: AsyncMock,
) -> None:
    """Test for setup failure if the auth fails."""
    mock_nextdns.create.side_effect = InvalidApiKeyError

    await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id


async def test_migrate_entry_v1_to_v2(
    hass: HomeAssistant,
    mock_config_entry_v1: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test migration from version 1 to version 2."""
    # Create old device with old-style identifiers before migration
    device_registry = dr.async_get(hass)
    mock_config_entry_v1.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_v1.entry_id,
        identifiers={(DOMAIN, "xyz12")},
        manufacturer="NextDNS Inc.",
        name="Fake Profile",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    await hass.config_entries.async_setup(mock_config_entry_v1.entry_id)
    await hass.async_block_till_done()

    # Verify migration was successful
    assert mock_config_entry_v1.version == 2
    assert mock_config_entry_v1.title == "NextDNS"
    assert mock_config_entry_v1.state is ConfigEntryState.LOADED

    # Verify data was migrated correctly
    assert CONF_PROFILE_ID not in mock_config_entry_v1.data
    assert mock_config_entry_v1.data[CONF_API_KEY] == "fake_api_key"

    # Verify subentry was created
    assert len(mock_config_entry_v1.subentries) == 1
    subentry = list(mock_config_entry_v1.subentries.values())[0]
    assert subentry.subentry_type == SUBENTRY_TYPE_PROFILE
    assert subentry.title == "Fake Profile"
    assert subentry.data[CONF_PROFILE_ID] == "xyz12"
    assert subentry.unique_id == "xyz12"

    # Verify device was migrated to new identifiers and subentry
    device = device_registry.async_get_device(
        identifiers={
            (DOMAIN, f"{mock_config_entry_v1.entry_id}_{subentry.subentry_id}")
        }
    )
    assert device is not None
    assert device.config_entries_subentries == {
        mock_config_entry_v1.entry_id: {subentry.subentry_id}
    }

    # Verify old device no longer exists
    old_device = device_registry.async_get_device(identifiers={(DOMAIN, "xyz12")})
    assert old_device is None


async def test_migrate_entry_v1_to_v2_merge_same_api_key(
    hass: HomeAssistant,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test migration merges v1 entries with the same API key."""
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        title="Profile One",
        unique_id="abc11",
        data={CONF_API_KEY: "fake_api_key", CONF_PROFILE_ID: "abc11"},
        entry_id="entry1_id",
        version=1,
    )
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        title="Profile Two",
        unique_id="def22",
        data={CONF_API_KEY: "fake_api_key", CONF_PROFILE_ID: "def22"},
        entry_id="entry2_id",
        version=1,
    )
    entry1.add_to_hass(hass)
    entry2.add_to_hass(hass)

    # Create old devices with old-style identifiers
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry1.entry_id,
        identifiers={(DOMAIN, "abc11")},
        manufacturer="NextDNS Inc.",
        name="Profile One",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    device_registry.async_get_or_create(
        config_entry_id=entry2.entry_id,
        identifiers={(DOMAIN, "def22")},
        manufacturer="NextDNS Inc.",
        name="Profile Two",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    # Create old entities for entry2 to verify they are migrated
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "profile_two_dns_queries",
        config_entry=entry2,
    )

    await hass.config_entries.async_setup(entry1.entry_id)
    await hass.async_block_till_done()

    # Verify entry1 was migrated and is loaded
    assert entry1.version == 2
    assert entry1.title == "NextDNS"
    assert entry1.state is ConfigEntryState.LOADED
    assert CONF_PROFILE_ID not in entry1.data
    assert entry1.data[CONF_API_KEY] == "fake_api_key"

    # Verify entry2 was removed
    assert hass.config_entries.async_get_entry(entry2.entry_id) is None

    # Verify entry1 has two subentries (both profiles merged)
    assert len(entry1.subentries) == 2
    subentries = list(entry1.subentries.values())
    profile_ids = {s.data[CONF_PROFILE_ID] for s in subentries}
    assert profile_ids == {"abc11", "def22"}
    titles = {s.title for s in subentries}
    assert titles == {"Profile One", "Profile Two"}

    # Verify devices were migrated to new identifiers under entry1
    for sub in subentries:
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, f"{entry1.entry_id}_{sub.subentry_id}")}
        )
        assert device is not None
        assert entry1.entry_id in device.config_entries

    # Verify old devices no longer exist
    assert device_registry.async_get_device(identifiers={(DOMAIN, "abc11")}) is None
    assert device_registry.async_get_device(identifiers={(DOMAIN, "def22")}) is None

    # Verify entity from entry2 was migrated to entry1
    entity_entry = entity_registry.async_get("sensor.nextdns_profile_two_dns_queries")
    assert entity_entry is not None
    assert entity_entry.config_entry_id == entry1.entry_id
    assert entity_entry.config_subentry_id is not None


async def test_migrate_entry_v1_to_v2_disabled_entry(
    hass: HomeAssistant,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test migration updates disabled_by when merging disabled and enabled entries."""
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        title="Profile One",
        unique_id="abc11",
        data={CONF_API_KEY: "fake_api_key", CONF_PROFILE_ID: "abc11"},
        entry_id="entry1_id",
        version=1,
    )
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        title="Profile Two",
        unique_id="def22",
        data={CONF_API_KEY: "fake_api_key", CONF_PROFILE_ID: "def22"},
        entry_id="entry2_id",
        version=1,
        disabled_by=ConfigEntryDisabler.USER,
    )
    entry1.add_to_hass(hass)
    entry2.add_to_hass(hass)

    # Create device and entity for disabled entry2 with CONFIG_ENTRY disabled_by
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry1.entry_id,
        identifiers={(DOMAIN, "abc11")},
        manufacturer="NextDNS Inc.",
        name="Profile One",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    device2 = device_registry.async_get_or_create(
        config_entry_id=entry2.entry_id,
        identifiers={(DOMAIN, "def22")},
        manufacturer="NextDNS Inc.",
        name="Profile Two",
        entry_type=dr.DeviceEntryType.SERVICE,
        disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY,
    )

    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "profile_two_dns_queries",
        config_entry=entry2,
        device_id=device2.id,
        disabled_by=er.RegistryEntryDisabler.CONFIG_ENTRY,
    )

    await hass.config_entries.async_setup(entry1.entry_id)
    await hass.async_block_till_done()

    # Verify entry1 was migrated and entry2 was removed
    assert entry1.version == 2
    assert entry1.state is ConfigEntryState.LOADED
    assert hass.config_entries.async_get_entry(entry2.entry_id) is None

    # Find the subentry for the disabled profile
    subentry2 = next(
        s for s in entry1.subentries.values() if s.data[CONF_PROFILE_ID] == "def22"
    )

    # Verify device disabled_by was changed from CONFIG_ENTRY to USER
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{entry1.entry_id}_{subentry2.subentry_id}")}
    )
    assert device is not None
    assert device.disabled_by is dr.DeviceEntryDisabler.USER

    # Verify entity disabled_by was changed from CONFIG_ENTRY to DEVICE
    entity_entry = entity_registry.async_get("sensor.nextdns_profile_two_dns_queries")
    assert entity_entry is not None
    assert entity_entry.config_entry_id == entry1.entry_id
    assert entity_entry.config_subentry_id == subentry2.subentry_id
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.DEVICE
