"""Test the AirNow config flow."""
from unittest.mock import patch

from pyairnow.errors import AirNowError, InvalidKeyError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.airnow.const import DOMAIN


async def test_form(hass, config, setup_airnow):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.airnow.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )

        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["data"] == config
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass, config):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("pyairnow.WebServiceAPI._get", side_effect=InvalidKeyError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_invalid_location(hass, config):
    """Test we handle invalid location."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("pyairnow.WebServiceAPI._get", return_value={}):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_location"}


async def test_form_cannot_connect(hass, config):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("pyairnow.WebServiceAPI._get", side_effect=AirNowError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unexpected(hass, config):
    """Test we handle an unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.airnow.config_flow.validate_input",
        side_effect=RuntimeError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_entry_already_exists(hass, config, config_entry):
    """Test that the form aborts if the Lat/Lng is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
