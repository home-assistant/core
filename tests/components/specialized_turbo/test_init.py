"""Tests for Specialized Turbo integration setup."""

import logging

import pytest
from specialized_turbo import (
    DecryptionError,
    EncryptionKeyProviderError,
    EncryptionKeyRequiredError,
)

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.specialized_turbo.const import (
    CONF_HMI_HARDWARE,
    CONF_HMI_SERIAL,
    CONF_WRAPPED_KEY,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from . import setup_integration
from .conftest import (
    ENCRYPTED_SERVICE_INFO,
    MOCK_ADDRESS,
    MOCK_ADDRESS_FORMATTED,
    NAME_ONLY_SERVICE_INFO,
    TCU1_SERVICE_INFO,
    TCX_SERVICE_INFO,
    MockLibrary,
    make_wrapped_key,
)

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
) -> None:
    """Test setup, polling, and unload through the library boundary."""
    await setup_integration(hass, mock_config_entry, TCX_SERVICE_INFO)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_library.connection.connect.assert_awaited_once()
    mock_library.monitor.start.assert_awaited_once_with(prime=False)
    mock_library.monitor.poll.assert_awaited_once()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_library.monitor.stop.assert_awaited_once()
    mock_library.connection.disconnect.assert_awaited_once()


async def test_setup_succeeds_without_bike_in_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
) -> None:
    """Test setup does not require the bike to be awake."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_library.connection_constructor.assert_not_called()


@pytest.mark.parametrize(
    "service_info",
    [TCU1_SERVICE_INFO, NAME_ONLY_SERVICE_INFO],
    ids=["tcu1", "name_only"],
)
async def test_setup_supported_bike_variants(
    hass: HomeAssistant,
    mock_library: MockLibrary,
    service_info: BluetoothServiceInfoBleak,
) -> None:
    """Test setup passes parsed advertisement metadata to the library."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        title="Mock title",
        data={CONF_ADDRESS: service_info.address},
        unique_id=format_mac(service_info.address),
    )
    await setup_integration(hass, entry, service_info)

    kwargs = mock_library.connection_constructor.call_args.kwargs
    assert kwargs["bike_info"] is not None
    mock_library.connection.connect.assert_awaited_once()


async def test_setup_encrypted_entry(
    hass: HomeAssistant,
    encrypted_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
) -> None:
    """Test stored encryption metadata reaches the library connection."""
    await setup_integration(hass, encrypted_config_entry, ENCRYPTED_SERVICE_INFO)

    kwargs = mock_library.connection_constructor.call_args.kwargs
    assert kwargs["wrapped_key"] == encrypted_config_entry.data[CONF_WRAPPED_KEY]
    assert kwargs["advertisement"].hmi_hardware == "B.3.3"
    assert kwargs["advertisement"].hmi_serial == "80005338"


@pytest.mark.parametrize(
    "error",
    [
        EncryptionKeyRequiredError("missing"),
        EncryptionKeyProviderError("invalid"),
        DecryptionError("stale"),
    ],
)
async def test_encryption_error_starts_reauthentication(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
    error: Exception,
) -> None:
    """Test missing, invalid, and stale keys start reauthentication."""
    mock_library.connection.connect.side_effect = error
    await setup_integration(hass, mock_config_entry, ENCRYPTED_SERVICE_INFO)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == config_entries.SOURCE_REAUTH
    assert mock_config_entry.data[CONF_HMI_HARDWARE] == "B.3.3"
    assert mock_config_entry.data[CONF_HMI_SERIAL] == "80005338"
    mock_library.monitor_constructor.assert_not_called()


async def test_key_error_without_hmi_does_not_start_broken_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
) -> None:
    """Test incomplete advertisements do not start an unusable reauth flow."""
    mock_library.connection.connect.side_effect = EncryptionKeyRequiredError("missing")
    await setup_integration(hass, mock_config_entry, NAME_ONLY_SERVICE_INFO)

    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN) == []


async def test_monitor_start_failure_disconnects(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
) -> None:
    """Test notification setup failure closes the partial connection."""
    mock_library.monitor.start.side_effect = RuntimeError("failed")
    await setup_integration(hass, mock_config_entry, TCX_SERVICE_INFO)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_library.connection.disconnect.assert_awaited_once()


async def test_unload_tolerates_library_cleanup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test cleanup errors do not prevent config entry unloading."""
    await setup_integration(hass, mock_config_entry, TCX_SERVICE_INFO)
    mock_library.monitor.stop.side_effect = RuntimeError("stop failed")
    mock_library.connection.disconnect.side_effect = RuntimeError("disconnect failed")

    with caplog.at_level(logging.DEBUG):
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert "Error stopping telemetry monitor" in caplog.text
    assert "Error disconnecting" in caplog.text


async def test_migrate_removes_legacy_pin(
    hass: HomeAssistant,
    mock_library: MockLibrary,
) -> None:
    """Test migration removes the unused legacy PIN."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={
            CONF_ADDRESS: MOCK_ADDRESS,
            CONF_PIN: "012345",
            CONF_HMI_HARDWARE: "B.3.3",
            CONF_HMI_SERIAL: "80005338",
            CONF_WRAPPED_KEY: make_wrapped_key(),
        },
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 3
    assert CONF_PIN not in entry.data
    assert entry.data[CONF_WRAPPED_KEY] == make_wrapped_key()
    mock_library.connection_constructor.assert_not_called()
