"""Test the Zabbix Event Sensors config flow."""

from unittest.mock import patch

from pyzabbix import ZabbixAPIException

from homeassistant import config_entries
from homeassistant.components.zabbix_evt_sensors.const import DOMAIN
from homeassistant.const import (
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_USER_INPUT = {
    CONF_HOST: "test-zabbix-host",
    CONF_API_TOKEN: "test-zabbix-api-token",
    CONF_PATH: "",
    CONF_PORT: 443,
    CONF_SSL: True,
}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_integration_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow one integration per Zabbix host."""
    MockConfigEntry(domain=DOMAIN, unique_id="test-zabbix-host").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=TEST_USER_INPUT,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test for invalid API token."""
    with patch(
        "homeassistant.components.zabbix_evt_sensors.config_flow.validate_input",
        side_effect=ZabbixAPIException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, data=TEST_USER_INPUT, context={"source": config_entries.SOURCE_USER}
        )
    assert result["errors"]["base"] == "invalid_auth"


async def test_other_errors(hass: HomeAssistant) -> None:
    """Test for unexpected errors."""
    with patch(
        "homeassistant.components.zabbix_evt_sensors.config_flow.validate_input",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, data=TEST_USER_INPUT, context={"source": config_entries.SOURCE_USER}
        )
    assert result["errors"]["base"] == "unknown"
