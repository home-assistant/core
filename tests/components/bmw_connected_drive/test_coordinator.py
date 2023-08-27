"""Test BMW coordinator."""
from unittest.mock import patch

from bimmer_connected.models import MyBMWAPIError, MyBMWAuthError
import respx

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import FIXTURE_CONFIG_ENTRY

from tests.common import MockConfigEntry


async def test_update_success(hass: HomeAssistant, bmw_fixture: respx.Router) -> None:
    """Test the reauth form."""
    config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.data[config_entry.domain][config_entry.entry_id].last_update_success
        is True
    )


async def test_update_failed(hass: HomeAssistant, bmw_fixture: respx.Router) -> None:
    """Test the reauth form."""
    config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[config_entry.domain][config_entry.entry_id]

    assert coordinator.last_update_success is True

    with patch(
        "bimmer_connected.account.MyBMWAccount.get_vehicles",
        side_effect=MyBMWAPIError("Test error"),
    ):
        await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed) is True


async def test_update_reauth(hass: HomeAssistant, bmw_fixture: respx.Router) -> None:
    """Test the reauth form."""
    config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[config_entry.domain][config_entry.entry_id]

    assert coordinator.last_update_success is True

    with patch(
        "bimmer_connected.account.MyBMWAccount.get_vehicles",
        side_effect=MyBMWAuthError("Test error"),
    ):
        await coordinator.async_refresh()
        assert coordinator.last_update_success is False
        assert isinstance(coordinator.last_exception, UpdateFailed) is True

        await coordinator.async_refresh()
        assert coordinator.last_update_success is False
        assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed) is True
