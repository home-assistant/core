"""Tests for the solax config flow."""
from unittest.mock import patch

from solax import RealTimeAPI
from solax.inverter import InverterResponse
from solax.inverters import X1MiniV34

from homeassistant import config_entries
from homeassistant.components.solax.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant


def __mock_real_time_api_success():
    return RealTimeAPI(X1MiniV34)


def __mock_get_data():
    return InverterResponse(
        data=None, serial_number="ABCDEFGHIJ", version="2.034.06", type=4
    )


async def test_form_success(hass: HomeAssistant) -> None:
    """Test successful form."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow["type"] == "form"
    assert flow["errors"] == {}

    with patch(
        "homeassistant.components.solax.config_flow.real_time_api",
        return_value=__mock_real_time_api_success(),
    ), patch("solax.RealTimeAPI.get_data", return_value=__mock_get_data()), patch(
        "homeassistant.components.solax.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        entry_result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {CONF_IP_ADDRESS: "192.168.1.87", CONF_PORT: 80, CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

    assert entry_result["type"] == "create_entry"
    assert entry_result["title"] == "ABCDEFGHIJ"
    assert entry_result["data"] == {
        CONF_IP_ADDRESS: "192.168.1.87",
        CONF_PORT: 80,
        CONF_PASSWORD: "password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_connect_error(hass: HomeAssistant) -> None:
    """Test cannot connect form."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow["type"] == "form"
    assert flow["errors"] == {}

    with patch(
        "homeassistant.components.solax.config_flow.real_time_api",
        side_effect=ConnectionError,
    ):
        entry_result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {CONF_IP_ADDRESS: "192.168.1.87", CONF_PORT: 80, CONF_PASSWORD: "password"},
        )

    assert entry_result["type"] == "form"
    assert entry_result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown error form."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow["type"] == "form"
    assert flow["errors"] == {}

    with patch(
        "homeassistant.components.solax.config_flow.real_time_api",
        side_effect=Exception,
    ):
        entry_result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {CONF_IP_ADDRESS: "192.168.1.87", CONF_PORT: 80, CONF_PASSWORD: "password"},
        )

    assert entry_result["type"] == "form"
    assert entry_result["errors"] == {"base": "unknown"}
