"""Tests for the SunSynk sensor platform."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from custom_components.sunsynk.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REGION,
    DOMAIN,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

VALID_CONFIG = {
    CONF_REGION: 0,
    CONF_EMAIL: "test@example.com",
    CONF_PASSWORD: "secret123",
}


def _make_gateway(status: int = 1, signal: int = 80):
    """Create a mock gateway object."""
    return SimpleNamespace(
        sn="GW001",
        status=status,
        signal=signal,
    )


def _make_flow(
    pv_power: float = 1500.0,
    battery_power: float = 200.0,
    grid_power: float = -100.0,
    load_power: float = 1200.0,
    soc: float = 75.0,
    gen_power: float = 0.0,
    min_power: float = 0.0,
    smart_load_power: float = 0.0,
    home_load_power: float = 1100.0,
    ups_load_power: float = 100.0,
):
    """Create a mock plant flow object."""
    return SimpleNamespace(
        pvPower=pv_power,
        battPower=battery_power,
        gridOrMeterPower=grid_power,
        loadOrEpsPower=load_power,
        soc=soc,
        genPower=gen_power,
        minPower=min_power,
        smartLoadPower=smart_load_power,
        homeLoadPower=home_load_power,
        upsLoadPower=ups_load_power,
    )


def _make_battery():
    return SimpleNamespace(
        soc=75.0,
        voltage=52.1,
        chargeVolt=56.0,
        status="charging",
        chargeCurrentLimit=100.0,
        dischargeCurrentLimit=100.0,
        capacity=10000.0,
        current=3.8,
        power=200.0,
        etotalChg=1234.5,
        etotalDischg=1000.0,
        eDayChg=12.3,
        eDayDischg=8.7,
        bmsTemperature=25.0,
    )


def _make_grid():
    return SimpleNamespace(
        power=-100.0,
        fac=50.02,
        status=1,
        powerFactor=0.98,
        etotalTo=5000.0,
        etotalFrom=3000.0,
        eDayTo=15.0,
        eDayFrom=10.0,
        limiterTotalPower=0.0,
        vip=[SimpleNamespace(volt=230.5, current=0.43, power=-100.0)],
    )


def _make_load():
    return SimpleNamespace(
        totalPower=1200.0,
        totalUsed=50000.0,
        dailyUsed=18.5,
        fac=50.0,
        smartLoadStatus="on",
        upsPower=100.0,
        vip=[SimpleNamespace(volt=230.0, current=5.2, power=1200.0)],
    )


def _make_output():
    return SimpleNamespace(
        pac=1500,
        fac=50.01,
        vip=[SimpleNamespace(volt=230.0, current=6.5, power=1500.0)],
    )


def _make_input():
    return SimpleNamespace(
        pvPower=1500.0,
        eToday=8.5,
        eTotal=12000.0,
        pvIV=[
            SimpleNamespace(ppv=800.0, iIpv=3.2, vpv=250.0),
            SimpleNamespace(ppv=700.0, iIpv=2.8, vpv=250.0),
        ],
    )


def _make_gen():
    return SimpleNamespace(
        etotalGen=0.0,
        eDayGen=0.0,
        genPower=0.0,
        fac=0.0,
        vip=[SimpleNamespace(volt=0.0, current=0.0, power=0.0)],
    )


def _make_settings():
    return SimpleNamespace(
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
        time3on="1",
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
    )


def _make_coordinator_data():
    """Build complete mock coordinator data."""
    return {
        "plants": {
            1: {
                "info": SimpleNamespace(id=1, name="My Plant"),
                "flow": _make_flow(),
                "inverters": {
                    "SN001": {
                        "info": SimpleNamespace(sn="SN001"),
                        "output": _make_output(),
                        "input": _make_input(),
                        "battery": _make_battery(),
                        "grid": _make_grid(),
                        "load": _make_load(),
                        "gen": _make_gen(),
                        "settings": _make_settings(),
                        "temp": SimpleNamespace(
                            infos=[SimpleNamespace(dc_temp=40.0, igbt_temp=45.0)],
                        ),
                    },
                },
            },
        },
        "gateways": [_make_gateway()],
        "events": {
            1: [SimpleNamespace(msg="info event")],
            2: [],
            3: [],
        },
        "notifications": [SimpleNamespace(msg="test notification")],
        "errors": {
            "Bearer": {"count": 0, "payload": "", "date": ""},
            "Events": {"count": 0, "payload": "", "date": ""},
            "Updates": {"count": 0, "payload": "", "date": ""},
            "Flow": {"count": 0, "payload": "", "date": ""},
            "InvList": {"count": 0, "payload": "", "date": ""},
            "InvParam": {"count": 0, "payload": "", "date": ""},
        },
        "last_update": "2025-01-01T00:00:00+00:00",
    }


@pytest.fixture
def mock_data():
    """Return mock coordinator data."""
    return _make_coordinator_data()


@pytest.fixture
async def setup_integration(hass: HomeAssistant, mock_data):
    """Set up the integration with mock data and return the entry."""
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
            return_value=mock_data,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    return entry


async def test_sensor_entities_created(hass: HomeAssistant, setup_integration) -> None:
    """Test that sensor entities are created."""
    entity_reg = er.async_get(hass)
    entities = [e for e in entity_reg.entities.values() if e.platform == "sunsynk"]
    # We should have many sensor entities
    sensor_entities = [e for e in entities if e.domain == "sensor"]
    assert len(sensor_entities) > 10


async def test_sensor_no_data(hass: HomeAssistant) -> None:
    """Test sensor platform handles empty coordinator data gracefully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_CONFIG,
        options={},
    )
    entry.add_to_hass(hass)

    empty_data = {
        "plants": {},
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

    with (
        patch("custom_components.sunsynk.TokenManager"),
        patch(
            "custom_components.sunsynk.async_fetch_all_data",
            return_value=empty_data,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
