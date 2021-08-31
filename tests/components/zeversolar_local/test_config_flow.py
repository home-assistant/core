"""Test the Local access to the zeversolar invertor config flow."""
from unittest.mock import patch

import pytest
from zeversolarlocal.api import ZeverError

from homeassistant import config_entries
from homeassistant.components.zeversolar_local.const import DOMAIN, ZEVER_INVERTER_ID
from homeassistant.const import CONF_HOST, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    host = "1.1.1.1"
    inverter_id = "abcd"

    config_entry_data = {
        ZEVER_INVERTER_ID: inverter_id,
        CONF_URL: f"http://{host}/home.cgi",
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.zeversolar_local.config_flow.api.inverter_id",
        return_value=inverter_id,
    ), patch(
        "homeassistant.components.zeversolar_local.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: host,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == f"Inverter - {inverter_id}"
    assert result2["data"] == config_entry_data
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "side_effect,error", [(ZeverError, "cannot_connect"), (Exception, "unknown")]
)
async def test_form_cannot_connect(side_effect, error, hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.zeversolar_local.config_flow.api.inverter_id",
        side_effect=side_effect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": error}
