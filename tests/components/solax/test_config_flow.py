"""Tests for the solax config flow."""

from unittest.mock import patch

import pytest
from solax.inverter import InverterResponse
from solax.inverters import X1MiniV34

from homeassistant import config_entries
from homeassistant.components.solax.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_MODEL, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def __mock_get_data():
    return InverterResponse(
        data=None,
        dongle_serial_number="ABCDEFGHIJ",
        version="2.034.06",
        type=4,
        inverter_serial_number="XXXXXXX",
    )


@pytest.mark.parametrize(
    ("user_input", "expected_inverters"),
    [
        pytest.param(
            {CONF_IP_ADDRESS: "192.168.1.87", CONF_PORT: 80, CONF_PASSWORD: "password"},
            None,
            id="auto_detect",
        ),
        pytest.param(
            {
                CONF_IP_ADDRESS: "192.168.1.87",
                CONF_PORT: 80,
                CONF_PASSWORD: "password",
                CONF_MODEL: "x1_mini_v34",
            },
            [X1MiniV34],
            id="model_selected",
        ),
    ],
)
async def test_form_success(
    hass: HomeAssistant,
    user_input: dict[str, str | int],
    expected_inverters: list[type] | None,
) -> None:
    """Test successful form."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow["type"] is FlowResultType.FORM
    assert flow["errors"] == {}

    with (
        patch(
            "homeassistant.components.solax.config_flow.discover",
            return_value=X1MiniV34,
        ) as mock_discover,
        patch("solax.RealTimeAPI.get_data", return_value=__mock_get_data()),
        patch(
            "homeassistant.components.solax.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        entry_result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], user_input
        )
        await hass.async_block_till_done()

    assert entry_result["type"] is FlowResultType.CREATE_ENTRY
    assert entry_result["title"] == "ABCDEFGHIJ"
    assert entry_result["data"] == user_input
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_discover.call_args.kwargs.get("inverters") == expected_inverters


async def test_form_connect_error(hass: HomeAssistant) -> None:
    """Test cannot connect form."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow["type"] is FlowResultType.FORM
    assert flow["errors"] == {}

    with patch(
        "homeassistant.components.solax.config_flow.discover",
        side_effect=ConnectionError,
    ):
        entry_result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {CONF_IP_ADDRESS: "192.168.1.87", CONF_PORT: 80, CONF_PASSWORD: "password"},
        )

    assert entry_result["type"] is FlowResultType.FORM
    assert entry_result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown error form."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow["type"] is FlowResultType.FORM
    assert flow["errors"] == {}

    with patch(
        "homeassistant.components.solax.config_flow.discover",
        side_effect=Exception,
    ):
        entry_result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {CONF_IP_ADDRESS: "192.168.1.87", CONF_PORT: 80, CONF_PASSWORD: "password"},
        )

    assert entry_result["type"] is FlowResultType.FORM
    assert entry_result["errors"] == {"base": "unknown"}
