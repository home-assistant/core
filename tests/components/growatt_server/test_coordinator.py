"""Test Growatt Server coordinator invariants not reachable through services."""

import datetime as dt
from unittest.mock import MagicMock

import pytest

from homeassistant.components.growatt_server.coordinator import GrowattCoordinator
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def _get_mix_coordinator(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    mock_growatt_classic_api: MagicMock,
) -> GrowattCoordinator:
    """Set up the integration and return the coordinator for its classic-auth Mix device."""
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "MIX123456", "deviceType": "mix"}
    ]
    mock_config_entry_classic.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_classic.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry_classic.runtime_data.devices["MIX123456"]


async def test_update_ac_charge_times_classic_wrong_period_count_raises(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    mock_growatt_classic_api: MagicMock,
) -> None:
    """Test the classic charge branch rejects a periods list that isn't exactly 3 long.

    services.py always builds exactly 3 periods, so this guard can only be
    exercised by calling the coordinator directly.
    """
    coordinator = await _get_mix_coordinator(
        hass, mock_config_entry_classic, mock_growatt_classic_api
    )

    with pytest.raises(ValueError, match="exactly 3 period definitions"):
        await coordinator.update_ac_charge_times(
            100,
            100,
            True,
            [{"start_time": dt.time(0, 0), "end_time": dt.time(0, 0), "enabled": False}]
            * 2,
        )


async def test_update_ac_discharge_times_classic_wrong_period_count_raises(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    mock_growatt_classic_api: MagicMock,
) -> None:
    """Test the classic discharge branch rejects a periods list that isn't exactly 3 long.

    services.py always builds exactly 3 periods, so this guard can only be
    exercised by calling the coordinator directly.
    """
    coordinator = await _get_mix_coordinator(
        hass, mock_config_entry_classic, mock_growatt_classic_api
    )

    with pytest.raises(ValueError, match="exactly 3 period definitions"):
        await coordinator.update_ac_discharge_times(
            100,
            100,
            [{"start_time": dt.time(0, 0), "end_time": dt.time(0, 0), "enabled": False}]
            * 2,
        )
