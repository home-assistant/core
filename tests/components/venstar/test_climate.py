"""The climate tests for the venstar integration."""

from collections.abc import Callable
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ClimateEntityFeature,
)
from homeassistant.components.venstar.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PLATFORM
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import VenstarColorTouchMock
from .util import async_init_integration, mock_venstar_devices

TEST_HOST = "1.1.1.1"
YAML_CONFIG = {CLIMATE_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_HOST: TEST_HOST}}

EXPECTED_BASE_SUPPORTED_FEATURES = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_OFF
    | ClimateEntityFeature.TURN_ON
)


@mock_venstar_devices
async def test_colortouch(hass: HomeAssistant) -> None:
    """Test interfacing with a venstar colortouch with attached humidifier."""

    with patch("homeassistant.components.venstar.coordinator.VENSTAR_SLEEP", new=0):
        await async_init_integration(hass)

    state = hass.states.get("climate.colortouch")
    assert state.state == "heat"

    expected_attributes = {
        "hvac_modes": ["heat", "cool", "off", "auto"],
        "min_temp": 7,
        "max_temp": 35,
        "min_humidity": 0,
        "max_humidity": 60,
        "fan_modes": ["on", "auto"],
        "preset_modes": ["none", "away", "temperature"],
        "current_temperature": 21.0,
        "temperature": 20.5,
        "current_humidity": 41,
        "humidity": 30,
        "fan_mode": "auto",
        "hvac_action": "idle",
        "preset_mode": "temperature",
        "fan_state": 0,
        "hvac_mode": 0,
        "friendly_name": "COLORTOUCH",
        "supported_features": EXPECTED_BASE_SUPPORTED_FEATURES
        | ClimateEntityFeature.TARGET_HUMIDITY,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())


@mock_venstar_devices
async def test_t2000(hass: HomeAssistant) -> None:
    """Test interfacing with a venstar T2000 presently turned off."""

    with patch("homeassistant.components.venstar.coordinator.VENSTAR_SLEEP", new=0):
        await async_init_integration(hass)

    state = hass.states.get("climate.t2000")
    assert state.state == "off"

    expected_attributes = {
        "hvac_modes": ["heat", "cool", "off", "auto"],
        "min_temp": 7,
        "max_temp": 35,
        "fan_modes": ["on", "auto"],
        "preset_modes": ["none", "away", "temperature"],
        "current_temperature": 14.0,
        "temperature": None,
        "fan_mode": "auto",
        "hvac_action": "idle",
        "preset_mode": "temperature",
        "fan_state": 0,
        "hvac_mode": 0,
        "friendly_name": "T2000",
        "supported_features": EXPECTED_BASE_SUPPORTED_FEATURES,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())


async def test_import_yaml(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a YAML configuration is imported and raises a deprecation issue."""
    with (
        patch(
            "homeassistant.components.venstar.config_flow.VenstarColorTouch.update_info",
            new=VenstarColorTouchMock.update_info,
        ),
        patch(
            "homeassistant.components.venstar.async_setup_entry",
            return_value=None,
        ),
    ):
        assert await async_setup_component(hass, CLIMATE_DOMAIN, YAML_CONFIG)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_HOST] == TEST_HOST
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_import_yaml_already_configured(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an already imported YAML configuration raises a deprecation issue."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: TEST_HOST})
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.venstar.async_setup_entry",
        return_value=None,
    ):
        assert await async_setup_component(hass, CLIMATE_DOMAIN, YAML_CONFIG)
        await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize(
    ("update_info", "reason"),
    [
        pytest.param(
            VenstarColorTouchMock.failed_update_info,
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(VenstarColorTouchMock.broken_update_info, "unknown", id="unknown"),
    ],
)
async def test_import_yaml_error(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    update_info: Callable[..., bool],
    reason: str,
) -> None:
    """Test a failed YAML import raises an import issue."""
    with patch(
        "homeassistant.components.venstar.config_flow.VenstarColorTouch.update_info",
        new=update_info,
    ):
        assert await async_setup_component(hass, CLIMATE_DOMAIN, YAML_CONFIG)
        await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []
    assert issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{reason}"
    )
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
