"""Test the Rainforest Eagle-200 config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.rainforest_eagle.const import (
    CONF_CLOUD_ID,
    CONF_INSTALL_CODE,
    DOMAIN,
    TYPE_EAGLE_200,
)
from homeassistant.components.rainforest_eagle.data import CannotConnect, InvalidAuth
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.rainforest_eagle.data.get_type",
        return_value=TYPE_EAGLE_200,
    ), patch(
        "homeassistant.components.rainforest_eagle.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_CLOUD_ID: "abcdef", CONF_INSTALL_CODE: "123456"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "abcdef"
    assert result2["data"] == {
        CONF_TYPE: TYPE_EAGLE_200,
        CONF_CLOUD_ID: "abcdef",
        CONF_INSTALL_CODE: "123456",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.rainforest_eagle.data.get_type",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_CLOUD_ID: "abcdef", CONF_INSTALL_CODE: "123456"},
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.rainforest_eagle.data.get_type",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_CLOUD_ID: "abcdef", CONF_INSTALL_CODE: "123456"},
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_import(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.rainforest_eagle.data.get_type",
        return_value=TYPE_EAGLE_200,
    ), patch(
        "homeassistant.components.rainforest_eagle.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data={CONF_CLOUD_ID: "abcdef", CONF_INSTALL_CODE: "123456"},
            context={"source": config_entries.SOURCE_IMPORT},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "abcdef"
    assert result["data"] == {
        CONF_TYPE: TYPE_EAGLE_200,
        CONF_CLOUD_ID: "abcdef",
        CONF_INSTALL_CODE: "123456",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    # Second time we should get already_configured
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={CONF_CLOUD_ID: "abcdef", CONF_INSTALL_CODE: "123456"},
        context={"source": config_entries.SOURCE_IMPORT},
    )

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "already_configured"
