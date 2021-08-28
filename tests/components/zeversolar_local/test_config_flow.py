"""Test the Local access to the zeversolar invertor config flow."""
from unittest.mock import patch

from zeversolarlocal.api import ZeverError

from homeassistant import config_entries, setup
from homeassistant.components.zeversolar_local.const import (
    DOMAIN,
    ZEVER_HOST,
    ZEVER_INVERTER_ID,
    ZEVER_URL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    config_entry_data = {
        "title": "Zeversolar invertor.",
        ZEVER_INVERTER_ID: "inverterid",
        ZEVER_URL: "http://0.0.0.0",
    }

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.zeversolar_local.config_flow.validate_input",
        return_value=config_entry_data,
    ), patch(
        "homeassistant.components.zeversolar_local.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                ZEVER_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Zeversolar invertor."
    assert result2["data"] == config_entry_data
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.zeversolar_local.config_flow.validate_input",
        side_effect=ZeverError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                ZEVER_HOST: "1.1.1.1",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}
