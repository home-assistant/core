"""Test the DVLA integration setup."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, patch

from aio_dvla_vehicle_enquiry import DVLAError

from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

VEHICLE_DATA = {
    "registrationNumber": "AB12CDE",
    "make": "FORD",
    "taxStatus": "Taxed",
}


async def test_setup_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setting up a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        data={CONF_REG_NUMBER: "AB12CDE"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dvla.coordinator.DVLAClient.async_get_vehicle",
        return_value=VEHICLE_DATA,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None
    assert entry.runtime_data.reg_number == "AB12CDE"

    entity_entries = er.async_entries_for_config_entry(
        entity_registry,
        entry.entry_id,
    )
    assert entity_entries

    entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        "AB12CDE-taxStatus",
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "taxed"


async def test_unload_entry(
    hass: HomeAssistant,
    setup_dvla_entry: Callable[
        [dict[str, Any] | None],
        Awaitable[MockConfigEntry],
    ],
) -> None:
    """Test unloading a config entry."""
    entry = await setup_dvla_entry()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_first_refresh_failure(hass: HomeAssistant) -> None:
    """Test config entry setup retries when the first refresh fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        data={CONF_REG_NUMBER: "AB12CDE"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dvla.coordinator.DVLAClient.async_get_vehicle",
        side_effect=DVLAError("DVLA unavailable"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_retries_on_dvla_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dvla_client: AsyncMock,
) -> None:
    """Test setup retries when DVLA update fails."""
    mock_config_entry.add_to_hass(hass)
    mock_dvla_client.side_effect = DVLAError("DVLA unavailable")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
