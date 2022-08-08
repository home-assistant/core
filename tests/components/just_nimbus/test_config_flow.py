"""Test the Just Nimbus config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.just_nimbus.config_flow import (
    CannotConnect,
    InvalidClientId,
)
from homeassistant.components.just_nimbus.const import DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM.value
    assert result["errors"] is None

    with patch(
        "homeassistant.components.just_nimbus.config_flow.JustNimbus.authenticate",
        return_value=True,
    ), patch(
        "homeassistant.components.just_nimbus.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test_name",
                CONF_CLIENT_ID: "test_id",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY.value
    assert result2["title"] == "test_name"
    assert result2["data"] == {
        CONF_NAME: "test_name",
        CONF_CLIENT_ID: "test_id",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.just_nimbus.config_flow.JustNimbus.authenticate",
        side_effect=InvalidClientId,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test_name",
                CONF_CLIENT_ID: "test_id",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.just_nimbus.config_flow.JustNimbus.authenticate",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test_name",
                CONF_CLIENT_ID: "test_id",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
