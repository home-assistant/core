"""Test the NeoPool diagnostics."""

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.neopool.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("mock_neopool_client")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry diagnostics output is stable and redacts host/port."""
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot(
        exclude=props(
            "created_at",
            "modified_at",
            "entry_id",
            "update_interval",
        )
    )


@pytest.mark.usefixtures("mock_neopool_client")
async def test_entry_diagnostics_redacts_serial_in_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """MBF_PAR_SERNUM is the device serial; ensure it is redacted in data."""
    await setup_integration(hass, mock_config_entry)
    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert result["coordinator"]["data"]["MBF_PAR_SERNUM"] == "**REDACTED**"


@pytest.mark.usefixtures("mock_neopool_client")
async def test_entry_diagnostics_exposes_only_exception_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """last_exception exposes the type only, never the raw message.

    The client embeds host:port in connection error messages, so the raw
    text must never be serialized into diagnostics.
    """
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator.last_exception = ConnectionError(
        "Modbus client connection failed to 192.0.2.15:502"
    )
    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert result["coordinator"]["last_exception"] == "ConnectionError"
    assert "192.0.2.15" not in str(result)


async def test_entry_diagnostics_without_runtime_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Diagnostics returns 'not loaded' when the entry has no coordinator yet.

    This branch is reached if diagnostics is queried for an entry that has
    been added but never loaded (e.g. it failed setup and was retried).
    """
    mock_config_entry.add_to_hass(hass)
    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert result["coordinator"] == {"status": "not loaded"}
    assert result["config_entry"]["data"]["host"] == "**REDACTED**"


async def test_entry_diagnostics_redacts_host_in_title(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """entry.title holds the raw host; ensure it is redacted."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, title="192.0.2.15")
    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert result["config_entry"]["title"] == "**REDACTED**"


async def test_entry_diagnostics_redacts_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """entry.unique_id is the device serial number; ensure it is redacted."""
    mock_config_entry.add_to_hass(hass)
    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert result["config_entry"]["unique_id"] == "**REDACTED**"
