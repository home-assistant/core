"""Test the AirNow config flow."""
from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.airnow.config_flow import (
    CannotConnect,
    InvalidAuth,
    InvalidLocation,
)
from homeassistant.components.airnow.const import DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
)

from tests.async_mock import patch

CONFIG = {
    CONF_API_KEY: "abc123",
    CONF_LATITUDE: 34.053718,
    CONF_LONGITUDE: -118.244842,
    CONF_RADIUS: 75,
    CONF_NAME: "Home",
}


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.airnow.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.airnow.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.airnow.config_flow.validate_input",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    print(result2)

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Home"
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
        "homeassistant.components.airnow.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_invalid_location(hass):
    """Test we handle invalid location."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.airnow.config_flow.validate_input",
        side_effect=InvalidLocation,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_location"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.airnow.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
