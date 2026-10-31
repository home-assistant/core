"""Tests for the Tank Utility sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
import requests

from homeassistant.components.tank_utility.const import DOMAIN
from homeassistant.components.tank_utility.sensor import SENSOR_ATTRS
from homeassistant.const import PERCENTAGE
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import DEVICE_DATA, MOCK_DEVICE_ID, TEST_EMAIL, TEST_PASSWORD

CONFIG = {
    "sensor": {
        "platform": "tank_utility",
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "devices": [MOCK_DEVICE_ID],
    }
}


async def test_setup_platform_success(
    hass: HomeAssistant,
    mock_get_token: MagicMock,
    mock_get_device_data: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test successful setup of Tank Utility sensor via YAML import."""
    assert await async_setup_component(hass, "sensor", CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.tank_utility_{MOCK_DEVICE_ID}")
    assert state is not None
    assert state.state == "78.4"
    assert state.attributes["unit_of_measurement"] == PERCENTAGE
    for attr in SENSOR_ATTRS:
        assert attr in state.attributes

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None


@pytest.mark.usefixtures("mock_get_token", "mock_get_device_data")
async def test_setup_platform_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import when entry already exists creates deprecation issue."""
    assert await async_setup_component(hass, "sensor", CONFIG)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None


async def test_setup_platform_unauthorized(
    hass: HomeAssistant,
    mock_get_token: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import with invalid credentials (401 error)."""
    response = requests.Response()
    response.status_code = requests.codes.unauthorized
    mock_get_token.side_effect = requests.exceptions.HTTPError(response=response)

    assert await async_setup_component(hass, "sensor", CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.tank_utility_{MOCK_DEVICE_ID}")
    assert state is None
    assert (
        issue_registry.async_get_issue(
            DOMAIN, "deprecated_yaml_import_issue_invalid_auth"
        )
        is not None
    )


async def test_setup_platform_other_http_error(
    hass: HomeAssistant,
    mock_get_token: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import with another HTTP error fails cleanly."""
    response = requests.Response()
    response.status_code = requests.codes.internal_server_error
    mock_get_token.side_effect = requests.exceptions.HTTPError(response=response)

    assert await async_setup_component(hass, "sensor", CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.tank_utility_{MOCK_DEVICE_ID}")
    assert state is None
    assert (
        issue_registry.async_get_issue(
            DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
        )
        is not None
    )


async def test_setup_entry_unauthorized(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_token: MagicMock,
) -> None:
    """Test config entry sensor setup with invalid credentials (401 error)."""
    response = requests.Response()
    response.status_code = requests.codes.unauthorized
    mock_get_token.side_effect = requests.exceptions.HTTPError(response=response)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.tank_utility_{MOCK_DEVICE_ID}")
    assert state is None


async def test_setup_entry_other_http_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_token: MagicMock,
) -> None:
    """Test config entry sensor setup with another HTTP error fails cleanly."""
    response = requests.Response()
    response.status_code = requests.codes.internal_server_error
    mock_get_token.side_effect = requests.exceptions.HTTPError(response=response)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.tank_utility_{MOCK_DEVICE_ID}")
    assert state is None


async def test_sensor_update_token_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_token: MagicMock,
    mock_get_device_data: MagicMock,
) -> None:
    """Test token refresh on 401 during sensor update and re-raise on other HTTP error."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.tank_utility_{MOCK_DEVICE_ID}")
    assert state is not None
    assert state.state == "78.4"

    unauthorized_response = requests.Response()
    unauthorized_response.status_code = requests.codes.unauthorized

    updated_data = dict(DEVICE_DATA)
    updated_data["lastReading"] = dict(DEVICE_DATA["lastReading"])
    updated_data["lastReading"]["tank"] = 65.2

    mock_get_device_data.side_effect = [
        requests.exceptions.HTTPError(response=unauthorized_response),
        updated_data,
    ]

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1, seconds=1))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"sensor.tank_utility_{MOCK_DEVICE_ID}")
    assert state is not None
    assert state.state == "65.2"
    mock_get_token.assert_called_with(TEST_EMAIL, TEST_PASSWORD, force=True)

    error_response = requests.Response()
    error_response.status_code = requests.codes.internal_server_error
    mock_get_device_data.side_effect = requests.exceptions.HTTPError(
        response=error_response
    )

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=2, seconds=2))
    await hass.async_block_till_done(wait_background_tasks=True)
