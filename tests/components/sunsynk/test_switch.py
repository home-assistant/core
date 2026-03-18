"""Tests for the SunSynk switch platform."""

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


def _make_settings(**overrides):
    defaults = {
        "sell_time1": "00:00",
        "sell_time2": "06:00",
        "sell_time3": "12:00",
        "sell_time4": "18:00",
        "sell_time5": "00:00",
        "sell_time6": "00:00",
        "cap1": 20,
        "cap2": 30,
        "cap3": 40,
        "cap4": 50,
        "cap5": 60,
        "cap6": 70,
        "time1on": "1",
        "time2on": "0",
        "time3on": "0",
        "time4on": "0",
        "time5on": "0",
        "time6on": "0",
        "gen_time1on": "0",
        "gen_time2on": "0",
        "gen_time3on": "0",
        "gen_time4on": "0",
        "gen_time5on": "0",
        "gen_time6on": "0",
        "peak_and_vallery": "1",
        "energy_mode": "0",
        "sys_work_mode": "1",
        "sell_time1_pac": 5000,
        "sell_time2_pac": 5000,
        "sell_time3_pac": 5000,
        "sell_time4_pac": 5000,
        "sell_time5_pac": 5000,
        "sell_time6_pac": 5000,
        "battery_restart_cap": 15,
        "battery_shutdown_cap": 10,
        "battery_max_current_charge": 100,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_coordinator_data(settings=None):
    if settings is None:
        settings = _make_settings()
    return {
        "plants": {
            1: {
                "info": SimpleNamespace(id=1, name="Plant"),
                "flow": SimpleNamespace(),
                "inverters": {
                    "SN001": {
                        "info": SimpleNamespace(sn="SN001"),
                        "output": SimpleNamespace(),
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
                        "settings": settings,
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
async def setup_integration(hass: HomeAssistant):
    """Set up the integration with mock data."""
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
            return_value=_make_coordinator_data(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    return entry


async def test_switch_entities_created(hass: HomeAssistant, setup_integration) -> None:
    """Test that switch entities are created."""
    entity_reg = er.async_get(hass)
    switch_entities = [
        e
        for e in entity_reg.entities.values()
        if e.platform == "sunsynk" and e.domain == "switch"
    ]
    # 6 timer + 6 gen timer + 2 simple (use_timer, energy_mode) = 14
    assert len(switch_entities) == 14


async def test_paired_timer_turn_on(hass: HomeAssistant, setup_integration) -> None:
    """Test turning on a paired timer switch sends both toggle values."""
    entity_reg = er.async_get(hass)
    timer1_entities = [
        e
        for e in entity_reg.entities.values()
        if e.platform == "sunsynk"
        and e.domain == "switch"
        and e.translation_key == "timer_1_on"
    ]
    assert len(timer1_entities) == 1
    entity_id = timer1_entities[0].entity_id

    with (
        patch(
            "custom_components.sunsynk.switch.async_write_settings",
        ) as mock_write,
        patch(
            "custom_components.sunsynk.async_fetch_all_data",
            return_value=_make_coordinator_data(),
        ),
    ):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )

    mock_write.assert_called_once()
    call_args = mock_write.call_args
    payload = call_args[0][3]
    # Should send both time1on and genTime1on
    assert "time1on" in payload
    assert "genTime1on" in payload
    assert payload["time1on"] == "1"


async def test_paired_timer_turn_off(hass: HomeAssistant, setup_integration) -> None:
    """Test turning off a paired timer switch."""
    entity_reg = er.async_get(hass)
    timer1_entities = [
        e
        for e in entity_reg.entities.values()
        if e.platform == "sunsynk"
        and e.domain == "switch"
        and e.translation_key == "timer_1_on"
    ]
    entity_id = timer1_entities[0].entity_id

    with (
        patch(
            "custom_components.sunsynk.switch.async_write_settings",
        ) as mock_write,
        patch(
            "custom_components.sunsynk.async_fetch_all_data",
            return_value=_make_coordinator_data(),
        ),
    ):
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )

    mock_write.assert_called_once()
    payload = mock_write.call_args[0][3]
    assert payload["time1on"] == "0"


async def test_simple_switch_turn_on(hass: HomeAssistant, setup_integration) -> None:
    """Test turning on a simple switch (use_timer)."""
    entity_reg = er.async_get(hass)
    use_timer_entities = [
        e
        for e in entity_reg.entities.values()
        if e.platform == "sunsynk"
        and e.domain == "switch"
        and "peak_and_vallery" in e.unique_id
    ]
    assert len(use_timer_entities) == 1
    entity_id = use_timer_entities[0].entity_id

    with (
        patch(
            "custom_components.sunsynk.switch.async_write_settings",
        ) as mock_write,
        patch(
            "custom_components.sunsynk.async_fetch_all_data",
            return_value=_make_coordinator_data(),
        ),
    ):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )

    mock_write.assert_called_once()
    payload = mock_write.call_args[0][3]
    assert payload == {"peakAndVallery": "1"}


async def test_simple_switch_turn_off(hass: HomeAssistant, setup_integration) -> None:
    """Test turning off a simple switch."""
    entity_reg = er.async_get(hass)
    use_timer_entities = [
        e
        for e in entity_reg.entities.values()
        if e.platform == "sunsynk"
        and e.domain == "switch"
        and "peak_and_vallery" in e.unique_id
    ]
    entity_id = use_timer_entities[0].entity_id

    with (
        patch(
            "custom_components.sunsynk.switch.async_write_settings",
        ) as mock_write,
        patch(
            "custom_components.sunsynk.async_fetch_all_data",
            return_value=_make_coordinator_data(),
        ),
    ):
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )

    mock_write.assert_called_once()
    payload = mock_write.call_args[0][3]
    assert payload == {"peakAndVallery": "0"}


async def test_switch_no_settings(hass: HomeAssistant) -> None:
    """Test switch platform handles missing settings."""
    data = _make_coordinator_data()
    data["plants"][1]["inverters"]["SN001"]["settings"] = None

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
            return_value=data,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_reg = er.async_get(hass)
    switch_entities = [
        e
        for e in entity_reg.entities.values()
        if e.platform == "sunsynk" and e.domain == "switch"
    ]
    assert len(switch_entities) == 0
