"""Tests for Mill local config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.mill_local.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS

from tests.common import MockConfigEntry


@pytest.fixture(name="mill_local_setup", autouse=True)
def mill_setup_fixture():
    """Patch mill setup entry."""
    with patch(
        "homeassistant.components.mill_local.async_setup_entry", return_value=True
    ):
        yield


async def test_show_config_form(hass):
    """Test show configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_create_entry(hass):
    """Test create entry from user input."""
    test_data = {
        CONF_IP_ADDRESS: "192.168.1.59",
    }

    with patch(
        "mill_local.Mill.get_status",
        return_value={
            "name": "panel heater gen. 3",
            "version": "0x210927",
            "operation_key": "",
            "status": "ok",
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
        )

    assert result["type"] == "create_entry"
    assert result["title"] == test_data[CONF_IP_ADDRESS]
    assert result["data"] == test_data


async def test_flow_entry_already_exists(hass):
    """Test user input for config_entry that already exists."""

    test_data = {
        CONF_IP_ADDRESS: "192.168.1.59",
    }

    first_entry = MockConfigEntry(
        domain="mill_local",
        data=test_data,
        unique_id=test_data[CONF_IP_ADDRESS],
    )
    first_entry.add_to_hass(hass)

    with patch(
        "mill_local.Mill.get_status",
        return_value={
            "name": "panel heater gen. 3",
            "version": "0x210927",
            "operation_key": "",
            "status": "ok",
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_connection_error(hass):
    """Test connection error."""

    test_data = {
        CONF_IP_ADDRESS: "192.168.1.59",
    }

    first_entry = MockConfigEntry(
        domain="mill_local",
        data=test_data,
        unique_id=test_data[CONF_IP_ADDRESS],
    )
    first_entry.add_to_hass(hass)

    with patch("mill_local.Mill.get_status", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
        )

    assert result["type"] == "form"
    assert result["errors"]["cannot_connect"] == "cannot_connect"
