"""Tests for the SunSynk integration setup (__init__.py)."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from custom_components.sunsynk import CONSECUTIVE_FAILURE_THRESHOLD, ISSUE_API_FAILURE
from custom_components.sunsynk.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PLANT_IGNORE_LIST,
    CONF_REGION,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    SunSynkAuthError,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

VALID_CONFIG = {
    CONF_REGION: 0,
    CONF_EMAIL: "test@example.com",
    CONF_PASSWORD: "secret123",
}


def _make_coordinator_data():
    return {
        "plants": {
            1: {
                "info": SimpleNamespace(id=1, name="My Plant"),
                "flow": SimpleNamespace(
                    pvPower=0,
                    battPower=0,
                    gridOrMeterPower=0,
                    loadOrEpsPower=0,
                    soc=75,
                    genPower=0,
                    minPower=0,
                    smartLoadPower=0,
                    homeLoadPower=0,
                    upsLoadPower=0,
                ),
                "inverters": {
                    "SN001": {
                        "info": SimpleNamespace(sn="SN001"),
                        "output": SimpleNamespace(pac=0, fac=50, vip=[]),
                        "input": SimpleNamespace(
                            pvPower=0, eToday=0, eTotal=0, pvIV=[]
                        ),
                        "battery": SimpleNamespace(
                            soc=75,
                            voltage=52,
                            chargeVolt=56,
                            status="idle",
                            chargeCurrentLimit=100,
                            dischargeCurrentLimit=100,
                            capacity=10000,
                            current=0,
                            power=0,
                            etotalChg=0,
                            etotalDischg=0,
                            eDayChg=0,
                            eDayDischg=0,
                            bmsTemperature=25,
                        ),
                        "grid": SimpleNamespace(
                            power=0,
                            fac=50,
                            status=1,
                            powerFactor=1,
                            etotalTo=0,
                            etotalFrom=0,
                            eDayTo=0,
                            eDayFrom=0,
                            limiterTotalPower=0,
                            vip=[SimpleNamespace(volt=230, current=0, power=0)],
                        ),
                        "load": SimpleNamespace(
                            totalPower=0,
                            totalUsed=0,
                            dailyUsed=0,
                            fac=50,
                            smartLoadStatus="off",
                            upsPower=0,
                            vip=[SimpleNamespace(volt=230, current=0, power=0)],
                        ),
                        "gen": SimpleNamespace(
                            etotalGen=0,
                            eDayGen=0,
                            genPower=0,
                            fac=0,
                            vip=[SimpleNamespace(volt=0, current=0, power=0)],
                        ),
                        "settings": SimpleNamespace(
                            sell_time1="00:00",
                            sell_time2="06:00",
                            sell_time3="12:00",
                            sell_time4="18:00",
                            sell_time5="00:00",
                            sell_time6="00:00",
                            cap1=20,
                            cap2=30,
                            cap3=40,
                            cap4=50,
                            cap5=60,
                            cap6=70,
                            time1on="1",
                            time2on="0",
                            time3on="0",
                            time4on="0",
                            time5on="0",
                            time6on="0",
                            gen_time1on="0",
                            gen_time2on="0",
                            gen_time3on="0",
                            gen_time4on="0",
                            gen_time5on="0",
                            gen_time6on="0",
                            peak_and_vallery="1",
                            energy_mode="0",
                            sys_work_mode="1",
                            sell_time1_pac=5000,
                            sell_time2_pac=5000,
                            sell_time3_pac=5000,
                            sell_time4_pac=5000,
                            sell_time5_pac=5000,
                            sell_time6_pac=5000,
                            battery_restart_cap=15,
                            battery_shutdown_cap=10,
                            battery_max_current_charge=100,
                        ),
                        "temp": None,
                    },
                },
            },
        },
        "gateways": [],
        "events": {},
        "notifications": [],
        "errors": {
            "Bearer": {"count": 0, "payload": "", "date": ""},
            "Events": {"count": 0, "payload": "", "date": ""},
            "Updates": {"count": 0, "payload": "", "date": ""},
            "Flow": {"count": 0, "payload": "", "date": ""},
            "InvList": {"count": 0, "payload": "", "date": ""},
            "InvParam": {"count": 0, "payload": "", "date": ""},
        },
        "last_update": None,
    }


@pytest.fixture
def mock_fetch():
    """Mock async_fetch_all_data to return test data."""
    with patch(
        "custom_components.sunsynk.async_fetch_all_data",
        return_value=_make_coordinator_data(),
    ) as mock_fn:
        yield mock_fn


async def test_setup_entry(hass: HomeAssistant, mock_fetch) -> None:
    """Test successful setup of a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_CONFIG,
        options={},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.sunsynk.TokenManager",
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None
    assert entry.runtime_data.coordinator is not None


async def test_setup_entry_with_options(hass: HomeAssistant, mock_fetch) -> None:
    """Test setup respects update_interval and plant_ignore_list options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_CONFIG,
        options={
            CONF_UPDATE_INTERVAL: 120,
            CONF_PLANT_IGNORE_LIST: "99,100",
        },
    )
    entry.add_to_hass(hass)

    with patch("custom_components.sunsynk.TokenManager"):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    coordinator = entry.runtime_data.coordinator
    assert coordinator.update_interval == timedelta(seconds=120)


async def test_unload_entry(hass: HomeAssistant, mock_fetch) -> None:
    """Test unloading a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_CONFIG,
        options={},
    )
    entry.add_to_hass(hass)

    with patch("custom_components.sunsynk.TokenManager"):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_fetch_fails(hass: HomeAssistant) -> None:
    """Test setup fails when initial data fetch raises."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_CONFIG,
        options={},
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.sunsynk.TokenManager"),
        patch(
            "custom_components.sunsynk.async_fetch_all_data",
            side_effect=Exception("API down"),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_fails_triggers_reauth(hass: HomeAssistant) -> None:
    """Test that SunSynkAuthError during fetch triggers reauth flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_CONFIG,
        options={},
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.sunsynk.TokenManager"),
        patch(
            "custom_components.sunsynk.async_fetch_all_data",
            side_effect=SunSynkAuthError("token expired"),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # ConfigEntryAuthFailed should have triggered a reauth flow
    flows = hass.config_entries.flow.async_progress()
    reauth_flows = [f for f in flows if f["context"].get("source") == "reauth"]
    assert len(reauth_flows) == 1


async def test_update_listener_reloads(hass: HomeAssistant, mock_fetch) -> None:
    """Test that changing options triggers a reload."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_CONFIG,
        options={CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL},
    )
    entry.add_to_hass(hass)

    with patch("custom_components.sunsynk.TokenManager"):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Update options (triggers listener -> reload)
    hass.config_entries.async_update_entry(
        entry,
        options={CONF_UPDATE_INTERVAL: 300},
    )
    await hass.async_block_till_done()

    # Entry should still be loaded after reload
    assert entry.state is ConfigEntryState.LOADED


async def test_repair_issue_created_after_consecutive_failures(
    hass: HomeAssistant,
) -> None:
    """Test that a repair issue is created after consecutive API failures."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_CONFIG,
        options={},
    )
    entry.add_to_hass(hass)

    call_count = 0

    def _fetch_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_coordinator_data()
        raise ConnectionError("API down")

    with (
        patch("custom_components.sunsynk.TokenManager"),
        patch(
            "custom_components.sunsynk.async_fetch_all_data",
            side_effect=_fetch_side_effect,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        # Trigger enough failures to hit the threshold
        coordinator = entry.runtime_data.coordinator
        for _ in range(CONSECUTIVE_FAILURE_THRESHOLD):
            await coordinator.async_refresh()
            await hass.async_block_till_done()

    issue_reg = ir.async_get(hass)
    issue = issue_reg.async_get_issue(DOMAIN, ISSUE_API_FAILURE)
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR


async def test_repair_issue_cleared_on_recovery(
    hass: HomeAssistant,
) -> None:
    """Test that the repair issue is cleared when API communication recovers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_CONFIG,
        options={},
    )
    entry.add_to_hass(hass)

    call_count = 0
    good_data = _make_coordinator_data()

    def _fetch_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # First call succeeds (initial refresh), then fail enough times, then succeed
        if call_count == 1:
            return good_data
        if call_count <= 1 + CONSECUTIVE_FAILURE_THRESHOLD:
            raise ConnectionError("API down")
        return good_data

    with (
        patch("custom_components.sunsynk.TokenManager"),
        patch(
            "custom_components.sunsynk.async_fetch_all_data",
            side_effect=_fetch_side_effect,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        coordinator = entry.runtime_data.coordinator

        # Trigger failures to create the issue
        for _ in range(CONSECUTIVE_FAILURE_THRESHOLD):
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        issue_reg = ir.async_get(hass)
        assert issue_reg.async_get_issue(DOMAIN, ISSUE_API_FAILURE) is not None

        # Now trigger a successful update to clear the issue
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    issue_reg = ir.async_get(hass)
    assert issue_reg.async_get_issue(DOMAIN, ISSUE_API_FAILURE) is None


async def test_stale_devices_removed(hass: HomeAssistant) -> None:
    """Test that devices no longer in API response are removed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_CONFIG,
        options={},
    )
    entry.add_to_hass(hass)

    # Initial data with two inverters
    initial_data = _make_coordinator_data()
    initial_data["plants"][1]["inverters"]["SN002"] = {
        "info": SimpleNamespace(sn="SN002"),
        "output": SimpleNamespace(pac=0, fac=50, vip=[]),
        "input": SimpleNamespace(pvPower=0, eToday=0, eTotal=0, pvIV=[]),
        "battery": SimpleNamespace(
            soc=50,
            voltage=52,
            chargeVolt=56,
            status="idle",
            chargeCurrentLimit=100,
            dischargeCurrentLimit=100,
            capacity=10000,
            current=0,
            power=0,
            etotalChg=0,
            etotalDischg=0,
            eDayChg=0,
            eDayDischg=0,
            bmsTemperature=25,
        ),
        "grid": SimpleNamespace(
            power=0,
            fac=50,
            status=1,
            powerFactor=1,
            etotalTo=0,
            etotalFrom=0,
            eDayTo=0,
            eDayFrom=0,
            limiterTotalPower=0,
            vip=[SimpleNamespace(volt=230, current=0, power=0)],
        ),
        "load": SimpleNamespace(
            totalPower=0,
            totalUsed=0,
            dailyUsed=0,
            fac=50,
            smartLoadStatus="off",
            upsPower=0,
            vip=[SimpleNamespace(volt=230, current=0, power=0)],
        ),
        "gen": SimpleNamespace(
            etotalGen=0,
            eDayGen=0,
            genPower=0,
            fac=0,
            vip=[SimpleNamespace(volt=0, current=0, power=0)],
        ),
        "settings": SimpleNamespace(
            sell_time1="00:00",
            sell_time2="06:00",
            sell_time3="12:00",
            sell_time4="18:00",
            sell_time5="00:00",
            sell_time6="00:00",
            cap1=20,
            cap2=30,
            cap3=40,
            cap4=50,
            cap5=60,
            cap6=70,
            time1on="1",
            time2on="0",
            time3on="0",
            time4on="0",
            time5on="0",
            time6on="0",
            gen_time1on="0",
            gen_time2on="0",
            gen_time3on="0",
            gen_time4on="0",
            gen_time5on="0",
            gen_time6on="0",
            peak_and_vallery="1",
            energy_mode="0",
            sys_work_mode="1",
            sell_time1_pac=5000,
            sell_time2_pac=5000,
            sell_time3_pac=5000,
            sell_time4_pac=5000,
            sell_time5_pac=5000,
            sell_time6_pac=5000,
            battery_restart_cap=15,
            battery_shutdown_cap=10,
            battery_max_current_charge=100,
        ),
        "temp": None,
    }

    call_count = 0

    def _fetch_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return initial_data
        # Second call: SN002 is gone
        return _make_coordinator_data()

    with (
        patch("custom_components.sunsynk.TokenManager"),
        patch(
            "custom_components.sunsynk.async_fetch_all_data",
            side_effect=_fetch_side_effect,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        device_reg = dr.async_get(hass)
        # Both inverters should have devices
        sn001_device = device_reg.async_get_device(
            identifiers={(DOMAIN, "inverter_SN001")}
        )
        sn002_device = device_reg.async_get_device(
            identifiers={(DOMAIN, "inverter_SN002")}
        )
        assert sn001_device is not None
        assert sn002_device is not None

        # Trigger update where SN002 is no longer present
        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    device_reg = dr.async_get(hass)
    # SN001 should still exist
    assert (
        device_reg.async_get_device(identifiers={(DOMAIN, "inverter_SN001")})
        is not None
    )
    # SN002 should be removed
    assert device_reg.async_get_device(identifiers={(DOMAIN, "inverter_SN002")}) is None
