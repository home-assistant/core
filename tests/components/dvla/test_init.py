"""Test the DVLA integration setup."""

from unittest.mock import patch

from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test the component setup."""
    assert await async_setup_component(hass, DOMAIN, {})


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        data={CONF_REG_NUMBER: "AB12CDE"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.dvla.coordinator.DVLACoordinator._async_update_data",
            return_value={
                "registrationNumber": "AB12CDE",
                "make": "FORD",
                "taxStatus": "Taxed",
            },
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            return_value=True,
        ) as mock_forward_entry_setups,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data["coordinator"] is not None
    mock_forward_entry_setups.assert_awaited_once()


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        data={CONF_REG_NUMBER: "AB12CDE"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.dvla.coordinator.DVLACoordinator._async_update_data",
            return_value={
                "registrationNumber": "AB12CDE",
                "make": "FORD",
                "taxStatus": "Taxed",
            },
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            return_value=True,
        ),
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            return_value=True,
        ) as mock_unload_platforms,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    mock_unload_platforms.assert_awaited_once()
