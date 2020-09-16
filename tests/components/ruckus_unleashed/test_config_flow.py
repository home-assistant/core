"""Test the Ruckus Unleashed config flow."""
from pyruckus.exceptions import AuthenticationError

from homeassistant import config_entries, setup
from homeassistant.components.ruckus_unleashed.const import DOMAIN

from tests.async_mock import patch
from tests.components.ruckus_unleashed import CONFIG, DEFAULT_TITLE


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.connect",
        return_value=None,
    ), patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.mesh_name",
        return_value=DEFAULT_TITLE,
    ), patch(
        "homeassistant.components.ruckus_unleashed.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.ruckus_unleashed.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == DEFAULT_TITLE
    assert result2["data"] == CONFIG
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.connect",
        side_effect=AuthenticationError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.connect",
        side_effect=ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass):
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ruckus_unleashed.Ruckus.connect",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
