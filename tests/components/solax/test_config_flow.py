"""Tests for the solax config flow."""

import asyncio
from unittest.mock import patch

import pytest
from solax.inverter import Inverter, InverterResponse
from solax.inverters import X1Boost, X1MiniV34

from homeassistant import config_entries
from homeassistant.components.solax.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_MODEL, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

CONNECTION_INPUT: dict[str, str | int] = {
    CONF_IP_ADDRESS: "192.168.1.87",
    CONF_PORT: 80,
    CONF_PASSWORD: "password",
}


def _build_inverter(inverter_cls: type[Inverter]) -> Inverter:
    """Build a real inverter instance to use as a discover() return value."""
    return next(
        iter(
            inverter_cls.build_all_variants(
                CONNECTION_INPUT[CONF_IP_ADDRESS],
                CONNECTION_INPUT[CONF_PORT],
                CONNECTION_INPUT[CONF_PASSWORD],
            )
        )
    )


def __mock_get_data() -> InverterResponse:
    return InverterResponse(
        data=None,
        dongle_serial_number="ABCDEFGHIJ",
        version="2.034.06",
        type=4,
        inverter_serial_number="XXXXXXX",
    )


@pytest.mark.parametrize(
    ("discovered_inverter_classes", "steps", "expected_model"),
    [
        pytest.param({X1MiniV34}, [CONNECTION_INPUT], "x1_mini_v34", id="single_match"),
        pytest.param(
            {X1MiniV34, X1Boost},
            [CONNECTION_INPUT, {CONF_MODEL: "x1_mini_v34"}],
            "x1_mini_v34",
            id="multiple_matches",
        ),
    ],
)
async def test_form_success(
    hass: HomeAssistant,
    discovered_inverter_classes: set[type[Inverter]],
    steps: list[dict[str, str | int]],
    expected_model: str,
) -> None:
    """Test successful discovery and entry creation, with/without a model choice."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow["type"] is FlowResultType.FORM
    assert flow["errors"] is None

    discovered = {_build_inverter(cls) for cls in discovered_inverter_classes}

    with (
        patch(
            "homeassistant.components.solax.config_flow.discover",
            return_value=discovered,
        ) as mock_discover,
        patch("solax.RealTimeAPI.get_data", return_value=__mock_get_data()),
        patch(
            "homeassistant.components.solax.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = flow
        for step_input in steps:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], step_input
            )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ABCDEFGHIJ"
    assert result["data"] == {**CONNECTION_INPUT, CONF_MODEL: expected_model}
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_discover.call_count == 1
    assert mock_discover.call_args.kwargs == {"return_when": asyncio.ALL_COMPLETED}


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(ConnectionError, "cannot_connect", id="cannot_connect"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_form_discover_error(
    hass: HomeAssistant, side_effect: type[Exception], expected_error: str
) -> None:
    """Test discovery failures redisplay the user step with an error."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert flow["type"] is FlowResultType.FORM
    assert flow["errors"] is None

    with patch(
        "homeassistant.components.solax.config_flow.discover", side_effect=side_effect
    ):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], CONNECTION_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(ConnectionError, "cannot_connect", id="cannot_connect"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
@pytest.mark.parametrize(
    ("discovered_inverter_classes", "steps", "expected_step_id"),
    [
        pytest.param({X1MiniV34}, [CONNECTION_INPUT], "user", id="single_match"),
        pytest.param(
            {X1MiniV34, X1Boost},
            [CONNECTION_INPUT, {CONF_MODEL: "x1_mini_v34"}],
            "select_model",
            id="multiple_matches",
        ),
    ],
)
async def test_form_finalize_error(
    hass: HomeAssistant,
    discovered_inverter_classes: set[type[Inverter]],
    steps: list[dict[str, str | int]],
    expected_step_id: str,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test serial-number fetch failures redisplay the current step with an error."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    discovered = {_build_inverter(cls) for cls in discovered_inverter_classes}

    with (
        patch(
            "homeassistant.components.solax.config_flow.discover",
            return_value=discovered,
        ),
        patch("solax.RealTimeAPI.get_data", side_effect=side_effect),
    ):
        result = flow
        for step_input in steps:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], step_input
            )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == expected_step_id
    assert result["errors"] == {"base": expected_error}


async def test_form_select_model_step_options(hass: HomeAssistant) -> None:
    """Test the select_model step only lists the discovered inverter models."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    discovered = {_build_inverter(X1MiniV34), _build_inverter(X1Boost)}

    with patch(
        "homeassistant.components.solax.config_flow.discover",
        return_value=discovered,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], CONNECTION_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_model"
    assert result["data_schema"].schema[CONF_MODEL].config["options"] == [
        "x1_boost",
        "x1_mini_v34",
    ]
