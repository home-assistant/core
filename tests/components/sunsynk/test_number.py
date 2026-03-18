"""Tests for the SunSynk number platform."""

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
        "cap1": 20,
        "cap2": 30,
        "cap3": 40,
        "cap4": 50,
        "cap5": 60,
        "cap6": 70,
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


async def test_number_entities_created(hass: HomeAssistant, setup_integration) -> None:
    """Test that number entities are created for caps and extra numbers."""
    entity_reg = er.async_get(hass)
    number_entities = [
        e
        for e in entity_reg.entities.values()
        if e.platform == "sunsynk" and e.domain == "number"
    ]
    # 6 caps + 3 extra (restart, shutdown, max charge current)
    assert len(number_entities) == 9


async def test_cap_number_set_value(hass: HomeAssistant, setup_integration) -> None:
    """Test setting a cap number value calls async_write_settings."""
    entity_reg = er.async_get(hass)
    cap1_entities = [
        e
        for e in entity_reg.entities.values()
        if e.platform == "sunsynk" and e.domain == "number" and "cap1" in e.unique_id
    ]
    assert len(cap1_entities) == 1
    entity_id = cap1_entities[0].entity_id

    with (
        patch(
            "custom_components.sunsynk.number.async_write_settings",
        ) as mock_write,
        patch(
            "custom_components.sunsynk.async_fetch_all_data",
            return_value=_make_coordinator_data(),
        ),
    ):
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": entity_id, "value": 50},
            blocking=True,
        )

    mock_write.assert_called_once()
    call_args = mock_write.call_args
    assert call_args[0][2] == "SN001"  # serial number
    assert call_args[0][3] == {"cap1": "50"}


async def test_number_no_settings(hass: HomeAssistant) -> None:
    """Test number platform handles missing settings gracefully."""
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

    # No number entities should be created when settings are None
    entity_reg = er.async_get(hass)
    number_entities = [
        e
        for e in entity_reg.entities.values()
        if e.platform == "sunsynk" and e.domain == "number"
    ]
    assert len(number_entities) == 0
