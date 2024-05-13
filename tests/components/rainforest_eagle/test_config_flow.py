"""Test the Rainforest Eagle config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.rainforest_eagle.const import (
    CONF_CLOUD_ID,
    CONF_HARDWARE_ADDRESS,
    CONF_INSTALL_CODE,
    DOMAIN,
    TYPE_EAGLE_200,
)
from homeassistant.components.rainforest_eagle.data import CannotConnect, InvalidAuth
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.rainforest_eagle.data.async_get_type",
        return_value=(TYPE_EAGLE_200, "mock-hw"),
    ), patch(
        "homeassistant.components.rainforest_eagle.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "abcdef"
    assert result2["data"] == {
        CONF_TYPE: TYPE_EAGLE_200,
        CONF_HOST: "192.168.1.55",
        CONF_CLOUD_ID: "abcdef",
        CONF_INSTALL_CODE: "123456",
        CONF_HARDWARE_ADDRESS: "mock-hw",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aioeagle.EagleHub.get_device_list",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
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
        "aioeagle.EagleHub.get_device_list",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
