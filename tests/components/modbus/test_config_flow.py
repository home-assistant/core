"""Test the Modbus config flow."""

from unittest import mock

from homeassistant.components.modbus.config_flow import ModbusConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE

from .conftest import TEST_MODBUS_HOST, TEST_MODBUS_NAME, TEST_PORT_TCP


async def test_config_flow_step_user() -> None:
    """Test that user step aborts with not_supported."""
    flow = ModbusConfigFlow()
    result = await flow.async_step_user()
    assert result["type"] == "abort"
    assert result["reason"] == "not_supported"


async def test_config_flow_step_import() -> None:
    """Test the import flow from YAML."""
    flow = ModbusConfigFlow()
    user_input = {
        CONF_NAME: TEST_MODBUS_NAME,
        CONF_TYPE: "tcp",
        CONF_HOST: TEST_MODBUS_HOST,
        CONF_PORT: TEST_PORT_TCP,
    }

    with (
        mock.patch.object(flow, "async_set_unique_id"),
        mock.patch.object(flow, "_abort_if_unique_id_configured"),
    ):
        result = await flow.async_step_import(user_input)

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_MODBUS_NAME
    assert result["data"] == user_input
