"""Test the QNAP config flow."""
from unittest.mock import MagicMock

import pytest
from requests.exceptions import ConnectTimeout

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.qnap import const
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from .conftest import TEST_HOST, TEST_PASSWORD, TEST_USERNAME

STANDARD_CONFIG = {
    CONF_USERNAME: TEST_USERNAME,
    CONF_PASSWORD: TEST_PASSWORD,
    CONF_HOST: TEST_HOST,
}


pytestmark = pytest.mark.usefixtures("mock_setup_entry", "qnap_connect")


async def test_config_flow(hass: HomeAssistant, qnap_connect: MagicMock) -> None:
    """Config flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    qnap_connect.get_system_stats.side_effect = ConnectTimeout("Test error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        STANDARD_CONFIG,
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    qnap_connect.get_system_stats.side_effect = TypeError("Test error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        STANDARD_CONFIG,
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    qnap_connect.get_system_stats.side_effect = Exception("Test error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        STANDARD_CONFIG,
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}

    qnap_connect.get_system_stats.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        STANDARD_CONFIG,
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test NAS name"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",
        CONF_SSL: const.DEFAULT_SSL,
        CONF_VERIFY_SSL: const.DEFAULT_VERIFY_SSL,
        CONF_PORT: const.DEFAULT_PORT,
    }


async def test_config_flow_import(hass: HomeAssistant) -> None:
    """Test import of YAML config."""
    data = STANDARD_CONFIG
    data[CONF_SSL] = const.DEFAULT_SSL
    data[CONF_VERIFY_SSL] = const.DEFAULT_VERIFY_SSL
    data[CONF_PORT] = const.DEFAULT_PORT
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=data,
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test NAS name"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",
        CONF_SSL: const.DEFAULT_SSL,
        CONF_VERIFY_SSL: const.DEFAULT_VERIFY_SSL,
        CONF_PORT: const.DEFAULT_PORT,
    }
