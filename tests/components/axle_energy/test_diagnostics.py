"""Test Axle Energy diagnostics."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from aioaxlevpp import AxleConnectionError, GridEvent
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.axle_energy.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    "event",
    [
        pytest.param(
            GridEvent(
                start=datetime(2026, 9, 11, 17, tzinfo=UTC),
                end=datetime(2026, 9, 11, 18, tzinfo=UTC),
                direction="export",
                updated_at=datetime(2026, 9, 11, 8, tzinfo=UTC),
            ),
            id="scheduled",
        ),
        pytest.param(None, id="empty"),
    ],
)
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(None, id="healthy"),
        pytest.param(AxleConnectionError(), id="unavailable"),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    event: GridEvent | None,
    error: AxleConnectionError | None,
) -> None:
    """Redact the key and retain cached data without another API request."""
    mock_client.get_event.return_value = event
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.get_event.side_effect = error
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_client.get_event.reset_mock()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
    mock_client.get_event.assert_not_awaited()
    assert mock_config_entry.data[CONF_API_KEY] == "test-token"


async def test_diagnostics_multiple_entries(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Download only the selected feed's cached event without exposing either key."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.get_event.return_value = None
    other_entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "other-token"})
    other_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(other_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.get_event.reset_mock()

    first = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
    second = await get_diagnostics_for_config_entry(hass, hass_client, other_entry)

    assert first["data"]["direction"] == "export"
    assert second["data"] is None
    assert first["entry_data"] == second["entry_data"] == {CONF_API_KEY: "**REDACTED**"}
    mock_client.get_event.assert_not_awaited()
    assert mock_config_entry.data[CONF_API_KEY] == "test-token"
    assert other_entry.data[CONF_API_KEY] == "other-token"
