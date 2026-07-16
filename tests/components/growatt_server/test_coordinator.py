"""Test Growatt Server coordinator write operations."""

import datetime as dt
from unittest.mock import MagicMock

import growattServer
from growattServer import GrowattV1ApiErrorCode
import pytest
from requests import RequestException

from homeassistant.components.growatt_server.coordinator import GrowattCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


async def _setup_and_get_coordinator(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    api: MagicMock,
    device_sn: str,
    device_type: str,
) -> GrowattCoordinator:
    """Set up the integration with a single device and return its coordinator."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for coordinator in entry.runtime_data.devices.values():
        if coordinator.device_id == device_sn:
            assert coordinator.device_type == device_type
            return coordinator
    pytest.fail(f"No coordinator found for {device_sn}")


async def _get_mix_coordinator(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    mock_growatt_classic_api: MagicMock,
) -> GrowattCoordinator:
    """Return the coordinator for a single classic-auth Mix device."""
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "MIX123456", "deviceType": "mix"}
    ]
    return await _setup_and_get_coordinator(
        hass, mock_config_entry_classic, mock_growatt_classic_api, "MIX123456", "mix"
    )


async def _get_sph_coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_v1_api: MagicMock,
) -> GrowattCoordinator:
    """Return the coordinator for a single V1-auth SPH device."""
    mock_growatt_v1_api.device_list.return_value = {
        "devices": [{"device_sn": "SPH123456", "type": 5}]
    }
    return await _setup_and_get_coordinator(
        hass, mock_config_entry, mock_growatt_v1_api, "SPH123456", "sph"
    )


async def test_update_ac_charge_times_classic_encodes_params(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    mock_growatt_classic_api: MagicMock,
) -> None:
    """Test the classic charge-time write encodes all periods as positional params."""
    coordinator = await _get_mix_coordinator(
        hass, mock_config_entry_classic, mock_growatt_classic_api
    )

    await coordinator.update_ac_charge_times(
        80,
        95,
        True,
        [
            {"start_time": dt.time(1, 30), "end_time": dt.time(5, 45), "enabled": True},
            {
                "start_time": dt.time(13, 0),
                "end_time": dt.time(17, 15),
                "enabled": True,
            },
            {"start_time": dt.time(0, 0), "end_time": dt.time(0, 0), "enabled": False},
        ],
    )

    mock_growatt_classic_api.update_mix_inverter_setting.assert_called_once_with(
        "MIX123456",
        "mix_ac_charge_time_period",
        [
            "80",
            "95",
            "1",
            "1",
            "30",
            "5",
            "45",
            "1",
            "13",
            "0",
            "17",
            "15",
            "1",
            "0",
            "0",
            "0",
            "0",
            "0",
        ],
    )


async def test_update_ac_discharge_times_classic_encodes_params(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    mock_growatt_classic_api: MagicMock,
) -> None:
    """Test the classic discharge-time write encodes all periods as positional params."""
    coordinator = await _get_mix_coordinator(
        hass, mock_config_entry_classic, mock_growatt_classic_api
    )

    await coordinator.update_ac_discharge_times(
        60,
        20,
        [
            {
                "start_time": dt.time(16, 0),
                "end_time": dt.time(20, 30),
                "enabled": True,
            },
            {"start_time": dt.time(0, 0), "end_time": dt.time(0, 0), "enabled": False},
            {"start_time": dt.time(0, 0), "end_time": dt.time(0, 0), "enabled": False},
        ],
    )

    mock_growatt_classic_api.update_mix_inverter_setting.assert_called_once_with(
        "MIX123456",
        "mix_ac_discharge_time_period",
        [
            "60",
            "20",
            "16",
            "0",
            "20",
            "30",
            "1",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
        ],
    )


async def test_update_ac_charge_times_classic_success_false_raises(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    mock_growatt_classic_api: MagicMock,
) -> None:
    """Test a classic write reporting success=False raises HomeAssistantError."""
    coordinator = await _get_mix_coordinator(
        hass, mock_config_entry_classic, mock_growatt_classic_api
    )

    mock_growatt_classic_api.update_mix_inverter_setting.return_value = {
        "success": False,
        "msg": "device offline",
    }

    with pytest.raises(HomeAssistantError):
        await coordinator.update_ac_charge_times(
            100,
            100,
            True,
            [
                {
                    "start_time": dt.time(0, 0),
                    "end_time": dt.time(0, 0),
                    "enabled": False,
                }
            ]
            * 3,
        )


async def test_update_ac_charge_times_classic_api_exception_raises(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    mock_growatt_classic_api: MagicMock,
) -> None:
    """Test a classic write raising a library error surfaces as HomeAssistantError."""
    coordinator = await _get_mix_coordinator(
        hass, mock_config_entry_classic, mock_growatt_classic_api
    )

    mock_growatt_classic_api.update_mix_inverter_setting.side_effect = (
        growattServer.GrowattError("connection reset")
    )

    with pytest.raises(HomeAssistantError):
        await coordinator.update_ac_charge_times(
            100,
            100,
            True,
            [
                {
                    "start_time": dt.time(0, 0),
                    "end_time": dt.time(0, 0),
                    "enabled": False,
                }
            ]
            * 3,
        )


async def test_update_ac_discharge_times_classic_api_exception_raises(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    mock_growatt_classic_api: MagicMock,
) -> None:
    """Test a classic discharge write raising a library error surfaces as HomeAssistantError."""
    coordinator = await _get_mix_coordinator(
        hass, mock_config_entry_classic, mock_growatt_classic_api
    )

    mock_growatt_classic_api.update_mix_inverter_setting.side_effect = (
        growattServer.GrowattError("connection reset")
    )

    with pytest.raises(HomeAssistantError):
        await coordinator.update_ac_discharge_times(
            100,
            100,
            [
                {
                    "start_time": dt.time(0, 0),
                    "end_time": dt.time(0, 0),
                    "enabled": False,
                }
            ]
            * 3,
        )


async def test_update_ac_charge_times_classic_missing_success_key_raises(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    mock_growatt_classic_api: MagicMock,
) -> None:
    """Test a classic write response missing the success key raises HomeAssistantError."""
    coordinator = await _get_mix_coordinator(
        hass, mock_config_entry_classic, mock_growatt_classic_api
    )

    mock_growatt_classic_api.update_mix_inverter_setting.return_value = {
        "msg": "malformed response"
    }

    with pytest.raises(HomeAssistantError):
        await coordinator.update_ac_charge_times(
            100,
            100,
            True,
            [
                {
                    "start_time": dt.time(0, 0),
                    "end_time": dt.time(0, 0),
                    "enabled": False,
                }
            ]
            * 3,
        )


async def test_update_ac_charge_times_classic_request_exception_raises(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    mock_growatt_classic_api: MagicMock,
) -> None:
    """Test a classic write raising a transport error surfaces as HomeAssistantError."""
    coordinator = await _get_mix_coordinator(
        hass, mock_config_entry_classic, mock_growatt_classic_api
    )

    mock_growatt_classic_api.update_mix_inverter_setting.side_effect = RequestException(
        "connection reset"
    )

    with pytest.raises(HomeAssistantError):
        await coordinator.update_ac_charge_times(
            100,
            100,
            True,
            [
                {
                    "start_time": dt.time(0, 0),
                    "end_time": dt.time(0, 0),
                    "enabled": False,
                }
            ]
            * 3,
        )


async def test_update_ac_discharge_times_classic_updates_cache(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    mock_growatt_classic_api: MagicMock,
) -> None:
    """Test a successful classic discharge write updates the coordinator cache."""
    coordinator = await _get_mix_coordinator(
        hass, mock_config_entry_classic, mock_growatt_classic_api
    )

    await coordinator.update_ac_discharge_times(
        60,
        20,
        [
            {
                "start_time": dt.time(16, 0),
                "end_time": dt.time(20, 30),
                "enabled": True,
            },
            {"start_time": dt.time(0, 0), "end_time": dt.time(0, 0), "enabled": False},
            {"start_time": dt.time(0, 0), "end_time": dt.time(0, 0), "enabled": False},
        ],
    )

    assert coordinator.data["disChargePowerCommand"] == 60
    assert coordinator.data["wdisChargeSOCLowLimit"] == 20
    assert coordinator.data["forcedDischargeTimeStart1"] == "16:00"
    assert coordinator.data["forcedDischargeTimeStop1"] == "20:30"
    assert coordinator.data["forcedDischargeStopSwitch1"] == 1


async def test_update_ac_charge_times_v1_calls_sph_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_v1_api: MagicMock,
) -> None:
    """Test the V1 charge-time write delegates to the SPH named-payload API."""
    coordinator = await _get_sph_coordinator(
        hass, mock_config_entry, mock_growatt_v1_api
    )

    periods = [
        {"start_time": dt.time(2, 0), "end_time": dt.time(6, 0), "enabled": True},
        {"start_time": dt.time(0, 0), "end_time": dt.time(0, 0), "enabled": False},
        {"start_time": dt.time(0, 0), "end_time": dt.time(0, 0), "enabled": False},
    ]

    await coordinator.update_ac_charge_times(90, 80, False, periods)

    mock_growatt_v1_api.sph_write_ac_charge_times.assert_called_once_with(
        "SPH123456", 90, 80, False, periods
    )


async def test_update_ac_charge_times_v1_api_error_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_growatt_v1_api: MagicMock,
) -> None:
    """Test a V1 write raising GrowattV1ApiError surfaces as HomeAssistantError."""
    coordinator = await _get_sph_coordinator(
        hass, mock_config_entry, mock_growatt_v1_api
    )

    mock_growatt_v1_api.sph_write_ac_charge_times.side_effect = (
        growattServer.GrowattV1ApiError(
            "rate limited",
            error_code=GrowattV1ApiErrorCode.RATE_LIMITED,
            error_msg="Too many requests",
        )
    )

    with pytest.raises(HomeAssistantError):
        await coordinator.update_ac_charge_times(
            90,
            80,
            False,
            [
                {
                    "start_time": dt.time(0, 0),
                    "end_time": dt.time(0, 0),
                    "enabled": False,
                }
            ]
            * 3,
        )


async def test_read_ac_charge_times_classic_reads_via_get_mix_inverter_settings(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    mock_growatt_classic_api: MagicMock,
) -> None:
    """Test the classic read path calls getMixSetParams, not the telemetry poll."""
    coordinator = await _get_mix_coordinator(
        hass, mock_config_entry_classic, mock_growatt_classic_api
    )

    result = await coordinator.read_ac_charge_times()

    mock_growatt_classic_api.get_mix_inverter_settings.assert_called_once_with(
        "MIX123456"
    )
    assert result["charge_power"] == 100
    assert result["charge_stop_soc"] == 100
    assert result["mains_enabled"] is True


async def test_read_ac_charge_times_classic_settings_request_exception_raises(
    hass: HomeAssistant,
    mock_config_entry_classic: MockConfigEntry,
    mock_growatt_classic_api: MagicMock,
) -> None:
    """Test a transport failure fetching classic settings surfaces as HomeAssistantError."""
    coordinator = await _get_mix_coordinator(
        hass, mock_config_entry_classic, mock_growatt_classic_api
    )

    mock_growatt_classic_api.get_mix_inverter_settings.side_effect = RequestException(
        "connection reset"
    )

    with pytest.raises(HomeAssistantError):
        await coordinator.read_ac_charge_times()
