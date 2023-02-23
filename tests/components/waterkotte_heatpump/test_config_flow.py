"""Test the Waterkotte Heatpump config flow."""
from unittest.mock import patch

from pywaterkotte import AuthenticationException, ConnectionException, EcotouchTags

from homeassistant import config_entries
from homeassistant.components.waterkotte_heatpump.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.waterkotte_heatpump.config_flow.Ecotouch.login",
        return_value=True,
    ), patch(
        "homeassistant.components.waterkotte_heatpump.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.waterkotte_heatpump.config_flow.Ecotouch.read_value",
        return_value=42,
    ), patch(
        "homeassistant.components.waterkotte_heatpump.config_flow.Ecotouch.decode_heatpump_series",
        return_value="heatpump type",
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "heatpump type"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.waterkotte_heatpump.config_flow.Ecotouch.login",
        side_effect=AuthenticationException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
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
        "homeassistant.components.waterkotte_heatpump.config_flow.Ecotouch.login",
        side_effect=ConnectionException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_device_already_configured(hass: HomeAssistant) -> None:
    """Test if we find out if device is configured twice."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="serial_no_123", data={"host": "1.1.1.1"}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.waterkotte_heatpump.config_flow.Ecotouch.login",
        return_value=True,
    ), patch(
        "homeassistant.components.waterkotte_heatpump.config_flow.Ecotouch.read_value",
        side_effect=lambda tag: {
            EcotouchTags.HEATPUMP_TYPE: 42,
            EcotouchTags.SERIAL_NUMBER: "serial_no_123",
        }[tag],
    ), patch(
        "homeassistant.components.waterkotte_heatpump.config_flow.Ecotouch.decode_heatpump_series",
        return_value="heatpump type",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.2.3.4",
                "username": "test-user1",
                "password": "test-pass2",
            },
        )

    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_unexpected_exception(hass: HomeAssistant) -> None:
    """Test we handle unexpected exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.waterkotte_heatpump.config_flow.Ecotouch.login",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
