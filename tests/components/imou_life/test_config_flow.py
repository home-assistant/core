import pytest
from homeassistant.data_entry_flow import FlowResultType

from homeassistant.config_entries import SOURCE_USER

from homeassistant.core import HomeAssistant
from homeassistant.components.imou_life.const import DOMAIN
from tests.components.imou_life import patch_async_setup_entry, user_input


@pytest.mark.usefixtures("imou_config_flow")
async def test_async_step_user_without_user_input(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            None
        )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"
    assert result["errors"] == {}


@pytest.mark.usefixtures("imou_config_flow")
async def test_async_step_user_with_user_input_success(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input
        )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == user_input
