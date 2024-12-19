import pytest
from homeassistant.data_entry_flow import FlowResultType

from homeassistant.config_entries import SOURCE_USER

from homeassistant.core import HomeAssistant
from homeassistant.components.imou_life.const import DOMAIN
from . import patch_async_setup_entry, USER_INPUT


@pytest.mark.usefixtures("imou_config_flow")
async def test_async_step_user_without_user_input(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"
    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1
    await hass.async_block_till_done()


@pytest.mark.usefixtures("imou_config_flow_exception")
async def test_async_step_user_with_user_input_fail(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"
    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"
    assert result["errors"]["base"] == "appIdOrSecret_invalid"


@pytest.mark.usefixtures("imou_config_flow_exception")
async def test_async_step_user_with_user_input(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"
    assert result["step_id"] == "login"
    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"
    assert result["errors"]["base"] == "appIdOrSecret_invalid"
