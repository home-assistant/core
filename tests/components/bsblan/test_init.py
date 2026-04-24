"""Tests for the BSBLan integration."""

from datetime import timedelta
from unittest.mock import MagicMock

from bsblan import BSBLANAuthError, BSBLANConnectionError, BSBLANError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.bsblan.const import (
    CONF_HEATING_CIRCUITS,
    CONF_PASSKEY,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test the BSBLAN configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_bsblan.device.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test the bsblan configuration entry not ready."""
    mock_bsblan.state.side_effect = BSBLANConnectionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(mock_bsblan.state.mock_calls) == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_auth_failed_triggers_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that BSBLANAuthError during coordinator update triggers reauth flow."""
    # First, set up the integration successfully
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Mock BSBLANAuthError during next update
    # The coordinator calls state(), sensor(), and hot_water_state() during updates
    mock_bsblan.state.side_effect = BSBLANAuthError("Authentication failed")

    # Advance time by the coordinator's update interval to trigger update
    freezer.tick(delta=20)  # Advance beyond the 12 second scan interval + random offset
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check that a reauth flow has been started
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize(
    ("method", "exception", "expected_state", "assert_static_fallback"),
    [
        (
            "initialize",
            BSBLANError("General error"),
            ConfigEntryState.SETUP_ERROR,
            False,
        ),
        (
            "device",
            BSBLANConnectionError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
            False,
        ),
        (
            "info",
            BSBLANAuthError("Authentication failed"),
            ConfigEntryState.SETUP_ERROR,
            False,
        ),
        (
            "static_values",
            BSBLANError("General error"),
            ConfigEntryState.LOADED,
            True,
        ),
        (
            "static_values",
            TimeoutError("Connection timeout"),
            ConfigEntryState.LOADED,
            True,
        ),
    ],
)
async def test_config_entry_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    method: str,
    exception: Exception,
    expected_state: ConfigEntryState,
    assert_static_fallback: bool,
) -> None:
    """Test setup errors trigger appropriate config entry states."""
    # Mock the specified method to raise the exception
    getattr(mock_bsblan, method).side_effect = exception

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
    if assert_static_fallback:
        assert mock_config_entry.runtime_data.static == {1: None}


async def test_coordinator_dhw_config_update_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handling when DHW config update fails but keeps existing data."""
    # First, set up the integration successfully
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Mock DHW config methods to fail, but keep state/sensor working
    mock_bsblan.hot_water_config.side_effect = BSBLANConnectionError("Config failed")
    mock_bsblan.hot_water_schedule.side_effect = BSBLANAuthError("Schedule failed")

    # Advance time by 5+ minutes to trigger config update (slow polling)
    freezer.tick(delta=301)  # 5 minutes + 1 second
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # The coordinator should still be working despite config update failures
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify the error handling paths were executed
    assert mock_bsblan.hot_water_config.called
    assert mock_bsblan.hot_water_schedule.called


async def test_coordinator_slow_first_fetch_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test slow coordinator when first fetch fails."""
    # Make slow coordinator fail on first fetch
    mock_bsblan.hot_water_config.side_effect = BSBLANConnectionError("Config failed")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Integration should still load even if slow coordinator fails
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify slow coordinator was called and handled the error gracefully
    assert mock_bsblan.hot_water_config.called


async def test_config_entry_timeout_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test TimeoutError during setup raises ConfigEntryNotReady."""
    mock_bsblan.initialize.side_effect = TimeoutError("Connection timeout")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Should be in retry state due to timeout
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_fast_no_dhw_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test fast coordinator when device does not support DHW."""
    mock_bsblan.hot_water_state.side_effect = BSBLANError(
        "None of the requested parameters are valid for this section"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Integration should still load even if DHW is not supported
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # DHW data should be None in the fast coordinator
    assert mock_config_entry.runtime_data.fast_coordinator.data.dhw is None

    # No water heater entities should be registered for this config entry
    water_heater_entities = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.domain == "water_heater"
    ]
    assert not water_heater_entities


async def test_coordinator_fast_dhw_fails_on_refresh_preserves_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test fast coordinator preserves last DHW state when DHW fails on refresh."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # DHW should be available initially
    coordinator = mock_config_entry.runtime_data.fast_coordinator
    initial_dhw = coordinator.data.dhw
    assert initial_dhw is not None

    # Now make DHW fail on the next refresh
    mock_bsblan.hot_water_state.side_effect = BSBLANError(
        "None of the requested parameters are valid for this section"
    )

    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Last known DHW state should be preserved
    assert coordinator.data.dhw is initial_dhw


async def test_coordinator_slow_no_dhw_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test slow coordinator when device does not support DHW (AttributeError)."""
    # Mock that device doesn't support DHW - raises AttributeError
    mock_bsblan.hot_water_config.side_effect = AttributeError(
        "Device does not support DHW"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Integration should still load even if DHW is not supported
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify slow coordinator handled the AttributeError gracefully
    assert mock_bsblan.hot_water_config.called


async def test_configuration_url_default_port(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test configuration_url omits port 80 (HTTP default)."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, "00:80:41:19:69:90")}
    )
    assert device is not None
    assert device.configuration_url == "http://127.0.0.1"


async def test_configuration_url_non_default_port(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_bsblan: MagicMock,
) -> None:
    """Test configuration_url includes port when it differs from the default."""
    config_entry = MockConfigEntry(
        title="BSBLAN Setup",
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 8080,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
        unique_id="00:80:41:19:69:90",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, "00:80:41:19:69:90")}
    )
    assert device is not None
    assert device.configuration_url == "http://192.168.1.100:8080"


def _legacy_entry_data() -> dict:
    """Return config entry data as stored before CONF_HEATING_CIRCUITS existed."""
    return {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 80,
        CONF_PASSKEY: "1234",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "admin1234",
    }


async def test_migrate_entry_discovers_circuits(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test migration from 1.1 to 1.2 discovers available circuits."""
    mock_bsblan.get_available_circuits.return_value = [1, 2]

    entry = MockConfigEntry(
        title="BSBLAN Setup",
        domain=DOMAIN,
        data=_legacy_entry_data(),
        unique_id="00:80:41:19:69:90",
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.data[CONF_HEATING_CIRCUITS] == [1, 2]


async def test_migrate_entry_discovery_failure_falls_back(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test migration falls back to [1] when circuit discovery fails."""
    mock_bsblan.get_available_circuits.side_effect = BSBLANError("boom")

    entry = MockConfigEntry(
        title="BSBLAN Setup",
        domain=DOMAIN,
        data=_legacy_entry_data(),
        unique_id="00:80:41:19:69:90",
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.data[CONF_HEATING_CIRCUITS] == [1]


async def test_migrate_entry_discovery_timeout_falls_back(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test migration falls back to [1] when circuit discovery times out."""
    mock_bsblan.get_available_circuits.side_effect = TimeoutError

    entry = MockConfigEntry(
        title="BSBLAN Setup",
        domain=DOMAIN,
        data=_legacy_entry_data(),
        unique_id="00:80:41:19:69:90",
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.data[CONF_HEATING_CIRCUITS] == [1]


async def test_migrate_entry_future_version_aborts(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test migration refuses to downgrade from a future major version."""
    entry = MockConfigEntry(
        title="BSBLAN Setup",
        domain=DOMAIN,
        data={**_legacy_entry_data(), CONF_HEATING_CIRCUITS: [1]},
        unique_id="00:80:41:19:69:90",
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_migrate_entry_already_current(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test that an up-to-date entry is loaded without re-running discovery."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_bsblan.get_available_circuits.call_count == 0
    assert mock_config_entry.data[CONF_HEATING_CIRCUITS] == [1]
