"""Test the Contec Controllers config flow."""
from typing import Callable, Coroutine
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.contec_controllers.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult


async def test_form(hass):
    """Tests the normal config flow."""

    async def validateFlowResult(flow_result):
        assert flow_result["type"] == "create_entry"
        assert flow_result["title"] == "ContecControllers"
        assert flow_result["data"] == _flow_data()
        await hass.config_entries.async_unload(flow_result["result"].entry_id)

    await _run_config_scenario(hass, validateFlowResult, True, None)


async def test_form_cant_connect(hass):
    """Test connection issue with the controllers."""

    async def validateFlowResult(flow_result):
        assert flow_result["type"] == "form"
        assert flow_result["errors"] == {"base": "cannot_connect"}

    await _run_config_scenario(hass, validateFlowResult, False, None)


async def test_form_unexpected_error(hass):
    """Test unexpected issue."""

    async def validateFlowResult(flow_result):
        assert flow_result["type"] == "form"
        assert flow_result["errors"] == {"base": "unknown"}

    await _run_config_scenario(hass, validateFlowResult, None, Exception)


async def _run_config_scenario(
    hass: HomeAssistant,
    result_validator: Callable[[FlowResult], Coroutine],
    is_connected_return_value: bool,
    is_connected_side_effect: any,
):
    initial_flow_result: FlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert initial_flow_result["type"] == "form"
    assert initial_flow_result["errors"] is None

    with patch(
        "ContecControllers.ControllerManager.ControllerManager.IsConnected",
        return_value=_bool_coroutine(is_connected_return_value),
        side_effect=is_connected_side_effect,
    ), patch(
        "ContecControllers.ControllerManager.ControllerManager.DiscoverEntitiesAsync",
        return_value=_bool_coroutine(True),
    ), patch(
        "ContecControllers.ControllerManager.ControllerManager.Init",
        return_value=None,
    ), patch(
        "ContecControllers.ControllerManager.ControllerManager.CloseAsync",
        return_value=_bool_coroutine(True),
    ):
        flow_result: FlowResult = await hass.config_entries.flow.async_configure(
            initial_flow_result["flow_id"], _flow_data()
        )
        await hass.async_block_till_done()
        await result_validator(flow_result)


def _flow_data():
    return {"ip": "1.1.1.1", "port": 1234, "numberOfControllers": 2}


def _bool_coroutine(return_value: bool) -> bool:
    return return_value
