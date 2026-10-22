"""Tests for TP-Link Omada integration init."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from functools import partial
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
)
from tplink_omada_client.clients import OmadaWirelessClient
from tplink_omada_client.exceptions import (
    ConnectionFailed,
    LoginFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)

from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.coordinator import (
    OmadaCoordinator,
    async_cleanup_client_trackers,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

MOCK_ENTRY_DATA = {
    "host": "https://fake.omada.host",
    "verify_ssl": True,
    "site": "SiteId",
    "username": "test-username",
    "password": "test-password",
}


@pytest.mark.parametrize(
    ("side_effect", "entry_state", "translation_key"),
    [
        (
            UnsupportedControllerVersion("4.0.0"),
            ConfigEntryState.SETUP_ERROR,
            "unsupported_controller",
        ),
        (
            LoginFailed(401, "invalid credentials"),
            ConfigEntryState.SETUP_ERROR,
            "auth_failed",
        ),
        (
            ConnectionFailed(),
            ConfigEntryState.SETUP_RETRY,
            "cannot_connect",
        ),
        (
            OmadaClientException(),
            ConfigEntryState.SETUP_RETRY,
            "unexpected_error",
        ),
    ],
)
async def test_setup_entry_login_failed_raises_configentryauthfailed(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: OmadaClientException,
    entry_state: ConfigEntryState,
    translation_key: str,
) -> None:
    """Test setup entry with login failed raises ConfigEntryAuthFailed."""
    mock_omada_client.login.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is entry_state
    assert mock_config_entry.error_reason_translation_key == translation_key
    assert mock_config_entry.error_reason_translation_placeholders is None


async def test_coordinator_update_failure_is_translated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_site_client: MagicMock,
) -> None:
    """Test coordinator API failures raise a translated UpdateFailed."""
    coordinator = OmadaCoordinator(
        hass, mock_config_entry, mock_omada_site_client, "test"
    )
    with (
        patch.object(
            OmadaCoordinator,
            "poll_update",
            side_effect=OmadaClientException("boom"),
        ),
        pytest.raises(UpdateFailed) as err,
    ):
        await coordinator._async_update_data()

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "api_error"


async def test_automatic_missing_client_cleanup(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test missing client trackers are removed during initial startup cleanup.

    This validates the cleanup mechanism scheduled immediately on entry setup,
    which runs as a background task.
    """

    mock_config_entry = MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345",
    )
    mock_config_entry.add_to_hass(hass)

    tracker = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_SiteId_11-11-11-11-11-11",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    assert entity_registry.async_get(tracker.entity_id)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entity_registry.async_get(tracker.entity_id) is None


async def test_cleanup_helpers_remove_unknown_clients(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test cleanup helper removes device_tracker entities for unknown clients."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    controller = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data

    all_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    device_trackers = [e for e in all_entities if e.domain == "device_tracker"]
    assert device_trackers, "Setup should have created device_tracker entities"

    unknown_client_entity_1 = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_99-99-99-99-99-99",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    unknown_client_entity_2 = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_88-88-88-88-88-88",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    enabled_unknown_client_entity = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_66-66-66-66-66-66",
        config_entry=mock_config_entry,
    )

    already_disabled_entity = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_77-77-77-77-77-77",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    sensor_entity = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="some_sensor",
        config_entry=mock_config_entry,
    )

    # Device tracker whose unique_id does not start with "scanner_" — MAC is unparsable
    malformed_no_prefix = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="tracker_00-11-22-33-44-55",
        config_entry=mock_config_entry,
    )

    # Device tracker whose unique_id has only two underscore-separated parts — MAC is unparsable
    malformed_wrong_parts = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_notype",
        config_entry=mock_config_entry,
    )

    # Device tracker whose parsed suffix is not a MAC — skipped, not removed
    malformed_mac = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_not-a-mac",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    # Device tracker whose parsed suffix has non-hex octets — skipped, not removed
    malformed_hex = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_zz-zz-zz-zz-zz-zz",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    # Device tracker whose parsed suffix has noncanonical octets — skipped, not removed
    malformed_octets = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_0:000:00:00:00:00",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    await async_cleanup_client_trackers(hass, controller)

    assert entity_registry.async_get(unknown_client_entity_1.entity_id) is None
    assert entity_registry.async_get(unknown_client_entity_2.entity_id) is None
    assert (
        entity_registry.async_get(enabled_unknown_client_entity.entity_id) is not None
    )
    assert entity_registry.async_get(already_disabled_entity.entity_id) is not None
    assert entity_registry.async_get(sensor_entity.entity_id) is not None
    assert entity_registry.async_get(malformed_no_prefix.entity_id) is not None
    assert entity_registry.async_get(malformed_wrong_parts.entity_id) is not None
    assert entity_registry.async_get(malformed_mac.entity_id) is not None
    assert entity_registry.async_get(malformed_hex.entity_id) is not None
    assert entity_registry.async_get(malformed_octets.entity_id) is not None


async def _get_known_clients_without(
    hass: HomeAssistant, excluded_mac: str
) -> AsyncGenerator[OmadaWirelessClient]:
    """Yield wireless clients from the known-clients fixture, skipping one MAC."""
    known_clients_data = await async_load_json_array_fixture(
        hass, "known-clients.json", DOMAIN
    )
    for client in known_clients_data:
        if client["mac"] != excluded_mac and client["wireless"]:
            yield OmadaWirelessClient(client)


async def _get_no_known_clients() -> AsyncGenerator[OmadaWirelessClient]:
    """Yield no known clients."""
    for client in ():
        yield client


async def test_cleanup_runs_hourly(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a client removed from the controller is cleaned up on the hourly interval."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Client present in the known-clients.json fixture at startup
    removed_mac = "2C-71-FF-ED-34-83"
    tracker = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id=f"scanner_Default_{removed_mac}",
        config_entry=mock_config_entry,
    )
    assert entity_registry.async_get(tracker.entity_id) is not None

    # Remove the client from the controller's known-clients list
    site_client = mock_omada_clients_only_client.get_site_client.return_value
    site_client.get_known_clients.side_effect = partial(
        _get_known_clients_without, hass, removed_mac
    )

    # Fire the 1-hour interval to trigger cleanup
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(hours=1, seconds=1),
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entity_registry.async_get(tracker.entity_id) is None


async def test_cleanup_recreates_tracker_when_client_reappears(
    hass: HomeAssistant,
    mock_omada_clients_only_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a tracker removed by cleanup is recreated when the client returns."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    removed_mac = "2C-71-FF-ED-34-83"
    tracker_unique_id = f"scanner_Default_{removed_mac}"
    site_client = mock_omada_clients_only_client.get_site_client.return_value

    # Remove the client from the controller's known-clients list and clean up
    site_client.get_known_clients.side_effect = partial(
        _get_known_clients_without, hass, removed_mac
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1, seconds=1))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (
        entity_registry.async_get_entity_id("device_tracker", DOMAIN, tracker_unique_id)
        is None
    )

    # Client returns to the controller — the next interval run recreates the tracker
    site_client.get_known_clients.side_effect = partial(
        _get_known_clients_without, hass, ""
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=2, seconds=1))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (
        entity_registry.async_get_entity_id("device_tracker", DOMAIN, tracker_unique_id)
        is not None
    )


async def test_preserved_tracker_recreated_when_client_returns(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a preserved tracker is instantiated when its client returns."""
    mock_config_entry.add_to_hass(hass)

    client_mac = "2C-71-FF-ED-34-83"
    tracker = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id=f"scanner_Default_{client_mac}",
        config_entry=mock_config_entry,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(tracker.entity_id) is None

    # Client becomes known to the controller — the next interval run
    # instantiates the preserved tracker
    site_client = mock_omada_client.get_site_client.return_value
    site_client.get_known_clients.side_effect = partial(
        _get_known_clients_without, hass, ""
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1, seconds=1))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(tracker.entity_id) is not None


async def test_cleanup_trackers_on_empty_known_clients(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test tracker cleanup removes integration-disabled trackers on an empty known list."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    tracker = entity_registry.async_get_or_create(
        domain="device_tracker",
        platform=DOMAIN,
        unique_id="scanner_Default_55-55-55-55-55-55",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    site_client = mock_omada_client.get_site_client.return_value
    site_client.get_known_clients.return_value = _get_no_known_clients()

    # The hourly cleanup refreshes the known clients before pruning trackers.
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entity_registry.async_get(tracker.entity_id) is None


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
