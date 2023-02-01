"""Tests helpers."""
from unittest.mock import patch

import pytest

from homeassistant.components.smartenergy_goecharger.const import CONF_CHARGERS, DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def charger_1() -> dict[str, str | int]:
    """Charger configuration."""
    return {
        "name": "charger1",
        "host": "http://1.1.1.1",
        "api_token": "example",
        "scan_interval": 10,
    }


@pytest.fixture
def charger_2() -> dict[str, str | int]:
    """Charger configuration."""
    return {
        "name": "charger2",
        "host": "http://1.1.1.1",
        "api_token": "example",
        "scan_interval": 10,
    }


@pytest.fixture
def charger_3() -> dict[str, str | int]:
    """Charger configuration."""
    return {
        "name": "charger3",
        "host": "http://1.1.1.2",
        "api_token": "foo",
        "scan_interval": 10,
    }


@pytest.fixture
def charger_host_prefix() -> dict[str, str | int]:
    """Wrong charger configuration."""
    return {
        "name": "charger_1",
        "host": "1.1.1.1",
        "api_token": "example",
        "scan_interval": 10,
    }


@pytest.fixture
def charger_host_suffix() -> dict[str, str | int]:
    """Wrong charger configuration."""
    return {
        "name": "charger_1",
        "host": "http://1.1.1.1/",
        "api_token": "example",
        "scan_interval": 10,
    }


@pytest.fixture
def charger_interval_min() -> dict[str, str | int]:
    """Wrong charger configuration."""
    return {
        "name": "charger_1",
        "host": "http://1.1.1.1",
        "api_token": "example",
        "scan_interval": -10,
    }


@pytest.fixture
def charger_interval_max() -> dict[str, str | int]:
    """Wrong charger configuration."""
    return {
        "name": "charger_1",
        "host": "http://1.1.1.1",
        "api_token": "example",
        "scan_interval": 60001,
    }


@pytest.fixture
def charger_auth_failed() -> dict[str, str | int]:
    """Wrong charger configuration."""
    return {
        "name": "charger_1",
        "host": "http://2.2.2.2",
        "api_token": "example",
        "scan_interval": 10,
    }


@pytest.fixture
def api_get_status() -> dict[str, str | int | bool]:
    """GET status response form the charger API."""
    return {
        "car_status": "Car is charging",
        "charger_max_current": 2,
        "charging_allowed": "on",
        "energy_since_car_connected": None,
        "energy_total": None,
        "phase_switch_mode": 1,
        "phases_number_connected": 1,
        "charger_access": False,
        "charger_force_charging": "neutral",
        "min_charging_current_limit": 1,
        "max_charging_current_limit": 30,
        "transaction": None,
    }


@pytest.fixture
def api_get_status_2() -> dict[str, str | int | bool]:
    """GET status response form the charger API."""
    return {
        "car_status": "Car is charging",
        "charger_max_current": 2,
        "charging_allowed": "on",
        "energy_since_car_connected": None,
        "energy_total": None,
        "phase_switch_mode": 1,
        "phases_number_connected": 1,
        "charger_access": False,
        "charger_force_charging": "neutral",
        "min_charging_current_limit": 5,
        "max_charging_current_limit": 4,
        "transaction": None,
    }


@pytest.fixture
def mock_config_entry(hass, charger_1) -> MockConfigEntry:
    """Mock a config entry."""
    charger_name = "test"
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="added_charger",
        data=charger_1,
        options=charger_1,
        entry_id=charger_name,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def mock_init_component_config_flow(
    hass, mock_config_entry, api_get_status
) -> None:
    """Initialize integration."""
    with patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.request_status",
        return_value=api_get_status,
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: {}},
        )
        await hass.async_block_till_done()


@pytest.fixture
async def mock_init_component(hass, charger_1, api_get_status) -> None:
    """Initialize integration."""
    with patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.request_status",
        return_value=api_get_status,
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: {CONF_CHARGERS: [[charger_1]]}},
        )
        await hass.async_block_till_done()


@pytest.fixture
async def mock_init_component_offline(hass, charger_1) -> None:
    """Initialize integration."""
    with patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.request_status",
        return_value={"success": False, "msg": "Wallbox is offline"},
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: {CONF_CHARGERS: [[charger_1]]}},
        )
        await hass.async_block_till_done()


@pytest.fixture
async def mock_init_component_limits(hass, charger_1, api_get_status_2) -> None:
    """Initialize integration."""
    with patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.request_status",
        return_value=api_get_status_2,
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: {CONF_CHARGERS: [[charger_1]]}},
        )
        await hass.async_block_till_done()
