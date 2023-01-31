"""Test the Imazu Wall Pad config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.imazu_wall_pad.const import DOMAIN
from homeassistant.components.imazu_wall_pad.helper import format_host
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

USER_INPUT_DATA = {CONF_HOST: "192.168.100.107", CONF_PORT: 8899}


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.imazu_wall_pad.config_flow.async_validate_connection",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT_DATA.copy(),
        )
        await hass.async_block_till_done()

    assert "errors" not in result
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == USER_INPUT_DATA[CONF_HOST]
    assert result["data"] == USER_INPUT_DATA
    assert result["options"] == {}

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.title == USER_INPUT_DATA[CONF_HOST]
    assert config_entry.unique_id == format_host(str(USER_INPUT_DATA[CONF_HOST]))
    assert config_entry.data == USER_INPUT_DATA
    assert config_entry.options == {}


@pytest.mark.parametrize("error", ("cannot_connect",))
async def test_config_flow_connect_error(hass: HomeAssistant, error) -> None:
    """Test for connect error the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_DATA.copy(),
    )
    await hass.async_block_till_done()

    assert result["errors"]

    errors = result["errors"]
    assert errors["base"] == error
