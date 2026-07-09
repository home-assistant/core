"""Tests for TP-Link Omada integration init."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from tplink_omada_client.exceptions import (
    ConnectionFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)

from homeassistant.components.tplink_omada import config_entry_owns_controller_entities
from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

MOCK_ENTRY_DATA = {
    "host": "https://fake.omada.host",
    "verify_ssl": True,
    "site": "SiteId",
    "username": "test-username",
    "password": "test-password",
}


def _mock_controller_entry(
    hass: HomeAssistant,
    *,
    entry_id: str,
    site_id: str,
    created_at: datetime,
    state: ConfigEntryState = ConfigEntryState.NOT_LOADED,
) -> MockConfigEntry:
    entry = MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data={**MOCK_ENTRY_DATA, "site": site_id},
        entry_id=entry_id,
        unique_id=f"12345_{site_id}",
        version=2,
        state=state,
    )
    object.__setattr__(entry, "created_at", created_at)
    object.__setattr__(entry, "runtime_data", SimpleNamespace(controller_id="12345"))
    entry.add_to_hass(hass)
    return entry


@pytest.mark.parametrize(
    ("side_effect", "entry_state"),
    [
        (
            UnsupportedControllerVersion("4.0.0"),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            ConnectionFailed(),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            OmadaClientException(),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_setup_entry_login_failed_raises_configentryauthfailed(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: OmadaClientException,
    entry_state: ConfigEntryState,
) -> None:
    """Test setup entry with login failed raises ConfigEntryAuthFailed."""
    mock_omada_client.login.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is entry_state


async def test_missing_devices_removed_at_startup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_omada_client: MagicMock,
) -> None:
    """Test missing devices are removed at startup."""
    mock_config_entry = MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345_SiteId",
        version=2,
    )
    mock_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "AA:BB:CC:DD:EE:FF")},
        manufacturer="TPLink",
        name="Old Device",
        model="Some old model",
    )

    assert device_registry.async_get(device_entry.id) == device_entry

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get(device_entry.id) is None


async def test_controller_device_registered_at_startup(
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the controller is registered as a device."""
    controller_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "12345")}
    )

    assert controller_device is not None
    assert controller_device.config_entries == {init_integration.entry_id}
    assert controller_device.manufacturer == "TP-Link"
    assert controller_device.model == "OC200"
    assert controller_device.name == "OC200"
    assert controller_device.sw_version == "6.2.10.17"


async def test_omada_devices_link_to_controller_device(
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test Omada devices are linked to the controller device."""
    controller_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "12345")}
    )
    gateway_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "AA-BB-CC-DD-EE-FF")}
    )
    switch_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "54-AF-97-00-00-01")}
    )

    assert controller_device is not None
    assert gateway_device is not None
    assert switch_device is not None
    assert controller_device.config_entries == {init_integration.entry_id}
    assert gateway_device.via_device_id == controller_device.id
    assert switch_device.via_device_id == controller_device.id


@pytest.mark.parametrize(
    "active_state",
    [ConfigEntryState.LOADED, ConfigEntryState.SETUP_IN_PROGRESS],
)
async def test_controller_owner_prefers_active_entry(
    hass: HomeAssistant,
    active_state: ConfigEntryState,
) -> None:
    """Test controller entities are owned by the first active controller entry."""
    created_at = datetime(2026, 7, 8, tzinfo=UTC)
    older_inactive_entry = _mock_controller_entry(
        hass,
        entry_id="01",
        site_id="Default",
        created_at=created_at,
    )
    active_entry = _mock_controller_entry(
        hass,
        entry_id="02",
        site_id="Second",
        created_at=datetime(2026, 7, 9, tzinfo=UTC),
        state=active_state,
    )

    assert config_entry_owns_controller_entities(hass, active_entry)
    assert not config_entry_owns_controller_entities(hass, older_inactive_entry)


async def test_controller_owner_falls_back_to_all_entries(
    hass: HomeAssistant,
) -> None:
    """Test controller ownership falls back to all entries when none are active."""
    owner_entry = _mock_controller_entry(
        hass,
        entry_id="02",
        site_id="Default",
        created_at=datetime(2026, 7, 8, tzinfo=UTC),
    )
    other_entry = _mock_controller_entry(
        hass,
        entry_id="01",
        site_id="Second",
        created_at=datetime(2026, 7, 9, tzinfo=UTC),
    )

    assert config_entry_owns_controller_entities(hass, owner_entry)
    assert not config_entry_owns_controller_entities(hass, other_entry)


async def test_controller_owner_tie_breaks_by_entry_id(
    hass: HomeAssistant,
) -> None:
    """Test controller ownership tie-breaks by entry id."""
    created_at = datetime(2026, 7, 8, tzinfo=UTC)
    owner_entry = _mock_controller_entry(
        hass,
        entry_id="01",
        site_id="Default",
        created_at=created_at,
        state=ConfigEntryState.LOADED,
    )
    other_entry = _mock_controller_entry(
        hass,
        entry_id="02",
        site_id="Second",
        created_at=created_at,
        state=ConfigEntryState.LOADED,
    )

    assert config_entry_owns_controller_entities(hass, owner_entry)
    assert not config_entry_owns_controller_entities(hass, other_entry)


async def test_migrate_entry_v1_to_v2(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
) -> None:
    """Test migration of a version 1 config entry to version 2."""
    entry = MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345",
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.unique_id == "12345_SiteId"
    assert entry.state is ConfigEntryState.LOADED
