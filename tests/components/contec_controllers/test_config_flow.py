"""Test the Contec Controllers config flow."""
from typing import Callable, Coroutine
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.contec_controllers.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult


async def test_form(hass):
    """Tests the normal config flow."""

    async def validateFlowResult(flowResult):
        assert flowResult["type"] == "create_entry"
        assert flowResult["title"] == "ContecControllers"
        assert flowResult["data"] == _flow_data()
        await hass.config_entries.async_unload(flowResult["result"].entry_id)

    await _run_config_scenario(hass, validateFlowResult, True, None)


async def test_form_cant_connect(hass):
    """Test connection issue with the controllers."""

    async def validateFlowResult(flowResult):
        assert flowResult["type"] == "form"
        assert flowResult["errors"] == {"base": "cannot_connect"}

    await _run_config_scenario(hass, validateFlowResult, False, None)


async def test_form_unexpected_error(hass):
    """Test unexpected issue."""

    async def validateFlowResult(flowResult):
        assert flowResult["type"] == "form"
        assert flowResult["errors"] == {"base": "unknown"}

    await _run_config_scenario(hass, validateFlowResult, None, Exception)


async def _run_config_scenario(
    hass: HomeAssistant,
    resultValidator: Callable[[FlowResult], Coroutine],
    isConnectedReturnValue: bool,
    isConnectedSideEffect: any,
):
    initialFlowResult: FlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert initialFlowResult["type"] == "form"
    assert initialFlowResult["errors"] is None

    with patch(
        "ContecControllers.ControllerManager.ControllerManager.IsConnected",
        return_value=_bool_coroutine(isConnectedReturnValue),
        side_effect=isConnectedSideEffect,
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
        flowResult: FlowResult = await hass.config_entries.flow.async_configure(
            initialFlowResult["flow_id"], _flow_data()
        )
        await hass.async_block_till_done()
        await resultValidator(flowResult)


def _flow_data():
    return {"ip": "1.1.1.1", "port": 1234, "numberOfControllers": 2}


def _bool_coroutine(returnValue: bool) -> bool:
    return returnValue
