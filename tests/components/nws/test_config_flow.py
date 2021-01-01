"""Test the National Weather Service (NWS) config flow."""
from unittest.mock import patch

import aiohttp

from homeassistant import config_entries, setup
from homeassistant.components.nws.const import DOMAIN


async def test_form(hass, mock_simple_nws_config):
    """Test we get the form."""
    hass.config.latitude = 35
    hass.config.longitude = -90

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nws.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.nws.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"api_key": "test"}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "ABC"
    assert result2["data"] == {
        "api_key": "test",
        "latitude": 35,
        "longitude": -90,
        "station": "ABC",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass, mock_simple_nws_config):
    """Test we handle cannot connect error."""
    mock_instance = mock_simple_nws_config.return_value
    mock_instance.set_station.side_effect = aiohttp.ClientError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_key": "test"},
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass, mock_simple_nws_config):
    """Test we handle unknown error."""
    mock_instance = mock_simple_nws_config.return_value
    mock_instance.set_station.side_effect = ValueError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_key": "test"},
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass, mock_simple_nws_config):
    """Test we handle duplicate entries."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nws.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.nws.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "test"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nws.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.nws.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"api_key": "test"},
        )
    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0
