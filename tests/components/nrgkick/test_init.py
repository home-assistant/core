"""Tests for the NRGkick integration initialization."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.nrgkick.api import (
    NRGkickApiClientAuthenticationError,
    NRGkickApiClientCommunicationError,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import async_setup_entry_with_return, create_mock_config_entry


async def test_setup_entry(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_nrgkick_api
) -> None:
    """Test successful setup of entry."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        # Use the config_entries.async_setup to properly set entry state
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None


async def test_setup_entry_failed_connection(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_nrgkick_api
) -> None:
    """Test setup entry with failed connection."""
    mock_config_entry.add_to_hass(hass)

    mock_nrgkick_api.get_info.side_effect = NRGkickApiClientCommunicationError

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_nrgkick_api
) -> None:
    """Test successful unload of entry."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        # Use proper setup to set entry state
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Use the config_entries.async_unload for proper state management
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_reload_entry(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_nrgkick_api
) -> None:
    """Test reload of entry."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        # Use proper setup to set entry state
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Test that reload calls the config_entries.async_reload
    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_coordinator_update_success(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data,
) -> None:
    """Test successful coordinator update."""
    mock_config_entry.add_to_hass(hass)

    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        # Use proper setup to set entry state
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = mock_config_entry.runtime_data
        assert coordinator.data == {
            "info": mock_info_data,
            "control": mock_control_data,
            "values": mock_values_data,
        }


async def test_coordinator_update_failed(
    hass: HomeAssistant, mock_nrgkick_api, caplog: pytest.LogCaptureFixture
) -> None:
    """Test coordinator update failed."""
    entry = create_mock_config_entry(data={CONF_HOST: "192.168.1.100"})
    entry.add_to_hass(hass)
    mock_nrgkick_api.get_values.side_effect = NRGkickApiClientCommunicationError

    with patch(
        "homeassistant.components.nrgkick.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        await async_setup_entry_with_return(hass, entry)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_auth_failed(
    hass: HomeAssistant, mock_nrgkick_api, caplog: pytest.LogCaptureFixture
) -> None:
    """Test coordinator auth failed."""
    entry = create_mock_config_entry(data={CONF_HOST: "192.168.1.100"})
    entry.add_to_hass(hass)
    mock_nrgkick_api.get_values.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        await async_setup_entry_with_return(hass, entry)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_coordinator_async_set_current(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_nrgkick_api
) -> None:
    """Test coordinator async_set_current method."""
    mock_config_entry.add_to_hass(hass)

    # Mock API to return the new current value in the response
    mock_nrgkick_api.set_current.return_value = {"current_set": 6.7}

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = mock_config_entry.runtime_data
        await coordinator.async_set_current(6.7)

        mock_nrgkick_api.set_current.assert_called_once_with(6.7)
        # Verify coordinator data was updated
        assert coordinator.data["control"]["current_set"] == 6.7


async def test_coordinator_async_set_charge_pause(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_nrgkick_api
) -> None:
    """Test coordinator async_set_charge_pause method."""
    mock_config_entry.add_to_hass(hass)

    # Mock API to return the new pause state in the response
    mock_nrgkick_api.set_charge_pause.return_value = {"charge_pause": 1}

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = mock_config_entry.runtime_data
        await coordinator.async_set_charge_pause(True)

        mock_nrgkick_api.set_charge_pause.assert_called_once_with(True)
        # Verify coordinator data was updated
        assert coordinator.data["control"]["charge_pause"] == 1


async def test_coordinator_async_set_energy_limit(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_nrgkick_api
) -> None:
    """Test coordinator async_set_energy_limit method."""
    mock_config_entry.add_to_hass(hass)

    # Mock API to return the new energy limit in the response
    mock_nrgkick_api.set_energy_limit.return_value = {"energy_limit": 50000}

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = mock_config_entry.runtime_data
        await coordinator.async_set_energy_limit(50000)

        mock_nrgkick_api.set_energy_limit.assert_called_once_with(50000)
        # Verify coordinator data was updated
        assert coordinator.data["control"]["energy_limit"] == 50000


async def test_coordinator_async_set_phase_count(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_nrgkick_api
) -> None:
    """Test coordinator async_set_phase_count method."""
    mock_config_entry.add_to_hass(hass)

    # Mock API to return the new phase count in the response
    mock_nrgkick_api.set_phase_count.return_value = {"phase_count": 1}

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = mock_config_entry.runtime_data
        await coordinator.async_set_phase_count(1)

        mock_nrgkick_api.set_phase_count.assert_called_once_with(1)
        # Verify coordinator data was updated
        assert coordinator.data["control"]["phase_count"] == 1


async def test_coordinator_command_blocked_by_solar(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_nrgkick_api
) -> None:
    """Test coordinator command blocked by solar charging."""
    mock_config_entry.add_to_hass(hass)

    # Mock API to return error response
    mock_nrgkick_api.set_charge_pause.return_value = {
        "Response": "Charging pause is blocked by solar-charging"
    }

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = mock_config_entry.runtime_data

        # Coordinator should surface a translated HomeAssistantError
        # that includes the device's message.
        with pytest.raises(HomeAssistantError) as exc_info:
            await coordinator.async_set_charge_pause(True)

        assert "blocked by solar-charging" in str(exc_info.value)


async def test_coordinator_command_unexpected_value(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_nrgkick_api
) -> None:
    """Test coordinator command returns unexpected value."""
    mock_config_entry.add_to_hass(hass)

    # Mock API to return different value than requested
    mock_nrgkick_api.set_current.return_value = {"current_set": 10.0}

    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI", return_value=mock_nrgkick_api
        ),
        patch("homeassistant.components.nrgkick.async_get_clientsession"),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = mock_config_entry.runtime_data

        # Coordinator should surface a translated HomeAssistantError
        # when the returned value doesn't match the requested value.
        with pytest.raises(HomeAssistantError) as exc_info:
            await coordinator.async_set_current(6.7)

        assert "unexpected value" in str(exc_info.value).lower()
