"""Test the Ituran coordinator."""

from unittest.mock import patch

from pyituran.exceptions import IturanApiError, IturanAuthError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import MOCK_CONFIG_ENTRY

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("ituran_fixture")
@pytest.mark.parametrize(("number_of_vehicles"), [2])
async def test_coordinator_update(hass: HomeAssistant, number_of_vehicles: int) -> None:
    """Test coordinator update."""
    config_entry = MockConfigEntry(**MOCK_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(config_entry.runtime_data.data) == number_of_vehicles


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (IturanAuthError, ConfigEntryState.SETUP_ERROR),
        (IturanApiError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_coordinator_startup_error(
    hass: HomeAssistant,
    error: Exception,
    state: ConfigEntryState,
) -> None:
    """Test coordinator with startup errors."""
    config_entry = MockConfigEntry(**MOCK_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)

    with patch(
        "pyituran.ituran.Ituran.get_vehicles",
        side_effect=error,
    ) as mock_get_vehicles:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        mock_get_vehicles.assert_called_once()

        assert config_entry.state is state


@pytest.mark.usefixtures("ituran_fixture")
@pytest.mark.parametrize(
    ("number_of_vehicles", "error", "exception"),
    [
        (2, IturanApiError, UpdateFailed),
        (2, IturanAuthError, ConfigEntryAuthFailed),
    ],
)
async def test_coordinator_update_error(
    hass: HomeAssistant,
    number_of_vehicles: int,
    error: Exception,
    exception: Exception,
) -> None:
    """Test coordinator with update error."""
    config_entry = MockConfigEntry(**MOCK_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(config_entry.runtime_data.data) == number_of_vehicles

    with patch(
        "pyituran.ituran.Ituran.get_vehicles",
        side_effect=error,
    ) as mock_get_vehicles:
        await config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

        mock_get_vehicles.assert_called_once()
        assert config_entry.runtime_data.last_update_success is False
        assert isinstance(config_entry.runtime_data.last_exception, exception)


@pytest.mark.usefixtures("ituran_fixture")
@pytest.mark.parametrize(("number_of_vehicles"), [1])
async def test_coordinator_removed_vehicle(
    hass: HomeAssistant, number_of_vehicles: int
) -> None:
    """Test coordinator with removed vehicle."""
    config_entry = MockConfigEntry(**MOCK_CONFIG_ENTRY)
    config_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(config_entry.runtime_data.data) == number_of_vehicles
    number_of_registered_devices = dr.async_entries_for_config_entry(
        device_registry, config_entry_id=config_entry.entry_id
    )
    assert len(number_of_registered_devices) == number_of_vehicles

    with patch(
        "pyituran.ituran.Ituran.get_vehicles",
        return_value=[],
    ) as mock_get_vehicles:
        await config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

        mock_get_vehicles.assert_called_once()

    number_of_registered_devices = dr.async_entries_for_config_entry(
        device_registry, config_entry_id=config_entry.entry_id
    )
    assert len(number_of_registered_devices) == 0
