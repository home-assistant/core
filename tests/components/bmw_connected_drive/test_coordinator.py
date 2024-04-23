"""Test BMW coordinator."""

from datetime import timedelta
from unittest.mock import patch

from bimmer_connected.models import MyBMWAPIError, MyBMWAuthError
from freezegun.api import FrozenDateTimeFactory
import respx

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import FIXTURE_CONFIG_ENTRY

from tests.common import MockConfigEntry, async_fire_time_changed


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


async def test_update_failed(
    hass: HomeAssistant, bmw_fixture: respx.Router, freezer: FrozenDateTimeFactory
) -> None:
    """Test the reauth form."""
    config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[config_entry.domain][config_entry.entry_id]

    assert coordinator.last_update_success is True

    freezer.tick(timedelta(minutes=5, seconds=1))

    with patch(
        "bimmer_connected.account.MyBMWAccount.get_vehicles",
        side_effect=MyBMWAPIError("Test error"),
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed) is True


async def test_update_reauth(
    hass: HomeAssistant, bmw_fixture: respx.Router, freezer: FrozenDateTimeFactory
) -> None:
    """Test the reauth form."""
    config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[config_entry.domain][config_entry.entry_id]

    assert coordinator.last_update_success is True

    freezer.tick(timedelta(minutes=5, seconds=1))
    with patch(
        "bimmer_connected.account.MyBMWAccount.get_vehicles",
        side_effect=MyBMWAuthError("Test error"),
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed) is True

    freezer.tick(timedelta(minutes=5, seconds=1))
    with patch(
        "bimmer_connected.account.MyBMWAccount.get_vehicles",
        side_effect=MyBMWAuthError("Test error"),
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed) is True
