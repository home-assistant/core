"""Tests for the SunSynk diagnostics module."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from custom_components.sunsynk.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REGION,
    DOMAIN,
)
from custom_components.sunsynk.diagnostics import async_get_config_entry_diagnostics
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

VALID_CONFIG = {
    CONF_REGION: 0,
    CONF_EMAIL: "test@example.com",
    CONF_PASSWORD: "secret123",
}


def _make_mock_data():
    return {
        "plants": {
            1: {
                "inverters": {
                    "SN001": {
                        "battery": SimpleNamespace(soc=75),
                        "grid": SimpleNamespace(power=0),
                        "load": SimpleNamespace(totalPower=0),
                        "input": SimpleNamespace(
                            pvPower=0, eToday=0, eTotal=0, pvIV=[]
                        ),
                        "settings": SimpleNamespace(cap1=20),
                    },
                },
            },
        },
        "gateways": [
            SimpleNamespace(sn="GW001", status=1, signal=80),
            SimpleNamespace(sn="GW002", status=1, signal=90),
        ],
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
    """Mock fetch to return test data."""
    with patch(
        "custom_components.sunsynk.async_fetch_all_data",
        return_value=_make_mock_data(),
    ) as mock_fn:
        yield mock_fn


async def test_diagnostics_output(hass: HomeAssistant, mock_fetch) -> None:
    """Test diagnostic data structure and content."""
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

    diag = await async_get_config_entry_diagnostics(hass, entry)

    # Verify top-level keys
    assert "config_entry" in diag
    assert "coordinator" in diag
    assert "data_summary" in diag

    # Verify credentials are redacted
    config = diag["config_entry"]
    assert config["data"]["email"] == "**REDACTED**"
    assert config["data"]["password"] == "**REDACTED**"

    # Verify coordinator info
    assert "last_update_success" in diag["coordinator"]
    assert "update_interval" in diag["coordinator"]

    # Verify data summary
    assert diag["data_summary"]["plant_count"] == 1
    assert diag["data_summary"]["gateway_count"] == 2
    plants = diag["data_summary"]["plants"]
    assert "1" in plants
    assert plants["1"]["inverter_count"] == 1
    inv = plants["1"]["inverters"]["SN001"]
    assert inv["has_battery"] is True
    assert inv["has_grid"] is True
    assert inv["has_settings"] is True


async def test_diagnostics_empty_data(hass: HomeAssistant) -> None:
    """Test diagnostics when coordinator has no data."""
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
        "notifications": [],
        "errors": {},
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

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["data_summary"]["plant_count"] == 0
    assert diag["data_summary"]["gateway_count"] == 0
