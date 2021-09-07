"""Common methods used across tests for Poolstation."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.poolstation.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def mock_config_entry(uniqe_id: str, entry_id: str = "an_entry_id") -> MockConfigEntry:
    """Return a mock Config Entry for the Poolstation integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="name@example.com",
        unique_id=uniqe_id,
        data={CONF_TOKEN: "an_auth_token"},
        entry_id=entry_id,
    )


def mock_pool(
    id: int,
    alias: str = "Home",
    temperature: float = 26.5,
    salt_concentration: float = 5.5,
    current_ph: float = 7.11,
    target_ph: float = 7.22,
    percentage_electrolysis: int = 88,
    target_percentage_electrolysis: int = 90,
    relays=[],
) -> MagicMock:
    """Return a mock Pool initialized with the given data."""
    pool_mock = MagicMock()
    pool_mock.id = id
    pool_mock.alias = alias
    pool_mock.temperature = temperature
    pool_mock.salt_concentration = salt_concentration
    pool_mock.current_ph = current_ph
    pool_mock.target_ph = target_ph
    pool_mock.percentage_electrolysis = percentage_electrolysis
    pool_mock.target_percentage_electrolysis = target_percentage_electrolysis
    pool_mock.relays = relays
    pool_mock.sync_info = AsyncMock()
    return pool_mock


async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pools: list[MagicMock] = [mock_pool(id=123, alias="my_pool")],
) -> None:
    """Initialize the Poolstation integration with the given Config Entry and Pool list."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.poolstation.Pool.get_all_pools",
        return_value=mock_pools,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert hass.data[DOMAIN]

    await hass.async_block_till_done()
