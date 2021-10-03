"""Tests for the comfoconnect config flow."""
from unittest import mock

from pycomfoconnect import PyComfoConnectNotAllowed

from homeassistant import config_entries
from homeassistant.components.comfoconnect import CONF_USER_AGENT, DEFAULT_TOKEN
from homeassistant.components.comfoconnect.const import DOMAIN
from homeassistant.components.comfoconnect.sensor import (
    ATTR_AIR_FLOW_EXHAUST,
    ATTR_CURRENT_RMOT,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PIN, CONF_SENSORS, CONF_TOKEN


async def test_flow_works(mock_bridge, mock_comfoconnect_command, hass):
    """Test that config flow works."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "1.2.3.4",
            CONF_NAME: "foo",
            CONF_TOKEN: DEFAULT_TOKEN,
            CONF_USER_AGENT: "Home Assistant",
            CONF_PIN: "4711",
        },
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "ComfoAir 00"
    assert result["data"][CONF_HOST] == "1.2.3.4"
    assert result["data"][CONF_NAME] == "foo"
    assert result["data"][CONF_TOKEN] == DEFAULT_TOKEN
    assert result["data"][CONF_USER_AGENT] == "Home Assistant"
    assert result["data"][CONF_PIN] == "4711"


async def test_flow_connection_error(mock_bridge, mock_comfoconnect_command, hass):
    """Test connection error during config flow."""
    with mock.patch("pycomfoconnect.bridge.Bridge.discover") as mock_discover:
        mock_discover.return_value = []
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_HOST: "1.2.3.4"},
        )
        assert result["type"] == "form"
        assert result["errors"] == {CONF_HOST: "cannot_connect"}


async def test_flow_auth_failed(mock_bridge, mock_comfoconnect_command, hass):
    """Test authentication failure during config flow."""
    with mock.patch("pycomfoconnect.bridge.Bridge.discover") as mock_discover:
        mock_discover.side_effect = PyComfoConnectNotAllowed()
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_HOST: "1.2.3.4"},
        )
        assert result["type"] == "form"
        assert result["errors"] == {CONF_PIN: "invalid_auth"}


async def test_flow_unknown_error(mock_bridge, mock_comfoconnect_command, hass):
    """Test handling of unknown error during config flow."""
    mock_bridge.side_effect = Exception()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "1.2.3.4"},
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}


async def test_options_flow(
    mock_bridge, mock_comfoconnect_command, mock_config_entry, hass
):
    """Test options flow."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id,
        data={CONF_SENSORS: [ATTR_AIR_FLOW_EXHAUST, ATTR_CURRENT_RMOT]},
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {CONF_SENSORS: [ATTR_AIR_FLOW_EXHAUST, ATTR_CURRENT_RMOT]}
