"""Tests for the solax config flow."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from solax.inverter import Inverter, InverterResponse
from solax.inverters import X1MiniV34

from homeassistant import config_entries
from homeassistant.components.solax.config_flow import INVERTERS_ENTRY_POINTS
from homeassistant.components.solax.const import CONF_SOLAX_INVERTER, DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def __mock_discover_success() -> MagicMock:
    return MagicMock(spec=X1MiniV34, get_data=AsyncMock(return_value=__mock_get_data()))


def __mock_get_data():
    return InverterResponse(
        data=None,
        dongle_serial_number="ABCDEFGHIJ",
        version="2.034.06",
        type=4,
        inverter_serial_number="XXXXXXX",
    )


@pytest.mark.parametrize(
    ("user_input_extra", "expected_inverters"),
    [
        pytest.param(
            {CONF_SOLAX_INVERTER: "x1_mini_v34"},
            {X1MiniV34},
            id="explicit_inverter",
        ),
        pytest.param(
            {},
            set(INVERTERS_ENTRY_POINTS.values()),
            id="auto_discovery",
        ),
    ],
)
async def test_form_success(
    hass: HomeAssistant,
    user_input_extra: dict[str, str],
    expected_inverters: set[type[Inverter]],
) -> None:
    """Test successful form."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow["type"] is FlowResultType.FORM
    assert flow["errors"] == {}

    user_input = {
        CONF_IP_ADDRESS: "192.168.1.87",
        CONF_PORT: 80,
        CONF_PASSWORD: "password",
        **user_input_extra,
    }

    with (
        patch(
            "homeassistant.components.solax.config_flow.discover",
            return_value=__mock_discover_success(),
        ) as mock_discover,
        patch(
            "homeassistant.components.solax.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        entry_result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], user_input
        )
        await hass.async_block_till_done()

    mock_discover.assert_called_once_with(
        "192.168.1.87",
        80,
        "password",
        inverters=expected_inverters,
        return_when=asyncio.FIRST_COMPLETED,
    )
    assert entry_result["type"] is FlowResultType.CREATE_ENTRY
    assert entry_result["title"] == "ABCDEFGHIJ"
    assert entry_result["data"] == user_input
    assert len(mock_setup_entry.mock_calls) == 1


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
