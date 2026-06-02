"""Tests for the Vistapool diagnostics."""

from typing import Any
from unittest.mock import AsyncMock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test diagnostics redact credentials and pool location data."""
    mock_pool_data["wifi"] = "gateway-serial-id"
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["entry"]["data"][CONF_USERNAME] == REDACTED
    assert result["entry"]["data"][CONF_PASSWORD] == REDACTED

    assert len(result["pools"]) == 1
    for pool in result["pools"]:
        assert pool["form"]["lat"] == REDACTED
        assert pool["form"]["lng"] == REDACTED
        assert pool["form"]["city"] == REDACTED
        assert pool["form"]["street"] == REDACTED
        assert pool["form"]["zipcode"] == REDACTED
        assert pool["wifi"] == REDACTED
        assert pool["main"]["temperature"] == mock_pool_data["main"]["temperature"]
