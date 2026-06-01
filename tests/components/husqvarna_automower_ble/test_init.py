"""Test the Husqvarna Automower Bluetooth setup."""

from unittest.mock import Mock, patch

from automower_ble.protocol import ResponseResult
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.husqvarna_automower_ble.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_CLIENT_ID, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import AUTOMOWER_SERVICE_INFO_SERIAL

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_automower_client")


async def test_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{AUTOMOWER_SERVICE_INFO_SERIAL.address}_1197489078")}
    )

    assert device_entry == snapshot


async def test_setup_missing_pin(
    hass: HomeAssistant,
    mock_automower_client: Mock,
) -> None:
    """Test a setup that was created before PIN support."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="My home",
        unique_id="397678e5-9995-4a39-9d9f-ae6ba310236c",
        data={
            CONF_ADDRESS: "00000000-0000-0000-0000-000000000003",
            CONF_CLIENT_ID: "1197489078",
        },
    )

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_PIN: 1234},
    )

    assert len(hass.config_entries.flow.async_progress()) == 1
    await hass.async_block_till_done()


async def test_setup_failed_connect(
    hass: HomeAssistant,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup retries with a diagnostic reason when the device cannot connect."""

    mock_automower_client.connect.side_effect = TimeoutError

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.husqvarna_automower_ble.bluetooth."
        "async_address_reachability_diagnostics",
        return_value="mock reachability reason",
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    # A bare TimeoutError has an empty str(), so the error falls back to the
    # exception class name; both the error and the reachability reason appear.
    assert (
        f"Unable to connect to device {mock_config_entry.data[CONF_ADDRESS]} "
        "due to TimeoutError: mock reachability reason" in caplog.text
    )


async def test_setup_unknown_error(
    hass: HomeAssistant,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails when we receive an error from the device."""
    mock_automower_client.connect.return_value = ResponseResult.UNKNOWN_ERROR

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_invalid_pin(
    hass: HomeAssistant,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unable to connect due to incorrect PIN."""
    mock_automower_client.connect.return_value = ResponseResult.INVALID_PIN

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
