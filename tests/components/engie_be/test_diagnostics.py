"""Test the diagnostics of the ENGIE Belgium integration."""

from datetime import datetime
from unittest.mock import MagicMock

from aioengiebelgium import EngieBeCommunicationError, EpexGranularity, EpexPayload
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import build_epex_payload, setup_dynamic_entry, setup_entry


def _build_payload_without_final_quarter(
    start: datetime, end: datetime, granularity: EpexGranularity
) -> EpexPayload:
    """Build a payload that drops the last quarter-hourly slot of the window."""
    payload = build_epex_payload(start, end, granularity)
    if granularity is not EpexGranularity.QUARTER_HOURLY:
        return payload
    return EpexPayload(slots=payload.slots[:-1], slot_duration=payload.slot_duration)


@pytest.mark.usefixtures("frozen_afternoon", "mock_engie_client")
async def test_diagnostics_fixed_tariff(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics of a household on a fixed tariff."""
    await setup_entry(hass, mock_config_entry)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    ) == snapshot(exclude=props("entry_id", "created_at", "modified_at"))


@pytest.mark.usefixtures("frozen_afternoon")
async def test_diagnostics_dynamic_tariff(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics of a household on a dynamic tariff."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    ) == snapshot(exclude=props("entry_id", "created_at", "modified_at"))


@pytest.mark.usefixtures("frozen_afternoon")
async def test_diagnostics_setup_retry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics of an entry whose first relations fetch failed."""
    mock_engie_client.return_value.async_get_customer_account_relations.side_effect = (
        EngieBeCommunicationError("boom")
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    ) == snapshot(exclude=props("entry_id", "created_at", "modified_at"))


@pytest.mark.usefixtures("frozen_afternoon")
async def test_diagnostics_prices_failure(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics of a household whose prices fetch failed."""
    mock_engie_client.return_value.async_get_prices.side_effect = (
        EngieBeCommunicationError("boom")
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    ) == snapshot(exclude=props("entry_id", "created_at", "modified_at"))


@pytest.mark.usefixtures("frozen_afternoon")
async def test_diagnostics_epex_truncated_quarter_hour(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics when the quarter-hourly slots end before the hourly ones."""
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        _build_payload_without_final_quarter
    )
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    ) == snapshot(exclude=props("entry_id", "created_at", "modified_at"))
