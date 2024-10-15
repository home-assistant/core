"""Test the Tami4 component."""

import pytest
from Tami4EdgeAPI import exceptions

from homeassistant.components.tami4.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .conftest import create_config_entry


async def test_init_success(mock_api, hass: HomeAssistant) -> None:
    """Test setup and that we can create the entry."""

    entry = await create_config_entry(hass)
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "mock_get_device", [exceptions.APIRequestFailedException], indirect=True
)
async def test_init_with_api_error(mock_api, hass: HomeAssistant) -> None:
    """Test init with api error."""

    entry = await create_config_entry(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("mock__get_devices_metadata", "expected_state"),
    [
        (
            exceptions.RefreshTokenExpiredException,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            exceptions.TokenRefreshFailedException,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    indirect=["mock__get_devices_metadata"],
)
async def test_init_error_raised(
    mock_api, hass: HomeAssistant, expected_state: ConfigEntryState
) -> None:
    """Test init when an error is raised."""

    entry = await create_config_entry(hass)
    assert entry.state == expected_state


async def test_load_unload(mock_api, hass: HomeAssistant) -> None:
    """Config entry can be unloaded."""

    entry = await create_config_entry(hass)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_prepare_drink(mock_api, mock_prepare_drink, hass: HomeAssistant) -> None:
    """Prepare valid drink."""

    entry = await create_config_entry(hass)
    assert entry.state is ConfigEntryState.LOADED

    drinks = await hass.services.async_call(
        DOMAIN,
        "get_drinks",
        {"entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )

    assert "drinks" in drinks
    assert len(drinks["drinks"]) == 1

    await hass.services.async_call(
        DOMAIN,
        "prepare_drink",
        {"entry_id": entry.entry_id, "drink_id": drinks["drinks"][0]["id"]},
        blocking=True,
    )

    await hass.async_block_till_done()


@pytest.mark.parametrize("mock_prepare_drink", [KeyError], indirect=True)
async def test_prepare_drink_not_exist(
    mock_api, mock_prepare_drink, hass: HomeAssistant
) -> None:
    """Prepare drink that doesn't exist."""
    entry = await create_config_entry(hass)
    assert entry.state is ConfigEntryState.LOADED

    with pytest.raises(ConfigEntryError) as config_error:
        await hass.services.async_call(
            DOMAIN,
            "prepare_drink",
            {"entry_id": entry.entry_id, "drink_id": "test"},
            blocking=True,
        )
    assert "Drink id doesn't exist" in config_error.value.args
