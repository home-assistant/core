"""Test the ihc config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.ihc.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.ihc.config_flow.IHCController.is_ihc_controller",
        return_value=True,
    ), patch(
        "homeassistant.components.ihc.config_flow.IHCController.authenticate",
        return_value=True,
    ), patch(
        "homeassistant.components.ihc.config_flow.IHCController.disconnect",
        return_value=None,
    ), patch(
        "homeassistant.components.ihc.config_flow.get_controller_serial",
        return_value="123",
    ), patch(
        "homeassistant.components.ihc.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "use_groups": True,
                "auto_setup": True,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "IHC Controller"
    assert result2["data"] == {
        "url": "http://1.1.1.1",
        "username": "test-username",
        "password": "test-password",
        "use_groups": True,
        "auto_setup": True,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ihc.config_flow.IHCController.is_ihc_controller",
        return_value=True,
    ), patch(
        "homeassistant.components.ihc.config_flow.IHCController.authenticate",
        return_value=False,
    ), patch(
        "homeassistant.components.ihc.config_flow.IHCController.disconnect",
        return_value=None,
    ), patch(
        "homeassistant.components.ihc.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "use_groups": True,
                "auto_setup": True,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ihc.config_flow.IHCController.is_ihc_controller",
        return_value=False,
    ), patch(
        "homeassistant.components.ihc.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "use_groups": True,
                "auto_setup": True,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
