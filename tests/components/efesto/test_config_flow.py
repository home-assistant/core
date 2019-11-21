"""Tests for the Efesto config flow."""
from unittest.mock import patch
from efestoclient import (  # pylint: disable=redefined-builtin
    ConnectionError,
    Error,
    InvalidURLError,
    UnauthorizedError,
)

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.efesto.const import DOMAIN
from homeassistant.const import (
    CONF_URL,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_DEVICE,
    CONF_NAME,
)

from tests.common import mock_coro


async def test_full_form_flow(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("efestoclient.EfestoClient") as client, patch(
        "efestoclient.EfestoClient.get_status",
        side_effect=client,
        return_value=mock_coro(True),
    ), patch(
        "homeassistant.components.efesto.async_setup", return_value=mock_coro(True)
    ) as mock_setup, patch(
        "homeassistant.components.efesto.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "http://example.com",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_DEVICE: "AABBCCDDEEFF",
                CONF_NAME: "MyHeater",
            },
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "MyHeater"
    assert result2["data"] == {
        CONF_URL: "http://example.com",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_DEVICE: "AABBCCDDEEFF",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_abort_if_device_already_configured(hass):
    """Test we abort if device is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.efesto.config_flow.EfestoConfigFlow._entry_in_configuration_exists",
        return_value=mock_coro(True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "http://example.com",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_DEVICE: "AABBCCDDEEFF",
                CONF_NAME: "MyHeater",
            },
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result2["reason"] == "device_already_configured"


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "efestoclient.EfestoClient", side_effect=UnauthorizedError("explanation"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "http://example.com",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_DEVICE: "AABBCCDDEEFF",
                CONF_NAME: "MyHeater",
            },
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unauthorized"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "efestoclient.EfestoClient", side_effect=ConnectionError("explanation"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "http://example.com",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_DEVICE: "AABBCCDDEEFF",
                CONF_NAME: "MyHeater",
            },
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "connection_error"}


async def test_form_invalid_url(hass):
    """Test we handle invalid url error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "efestoclient.EfestoClient", side_effect=InvalidURLError("explanation"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "http://example.com",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_DEVICE: "AABBCCDDEEFF",
                CONF_NAME: "MyHeater",
            },
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_url"}


async def test_form_unknown_error(hass):
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "efestoclient.EfestoClient", side_effect=Error("explanation"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "http://example.com",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_DEVICE: "AABBCCDDEEFF",
                CONF_NAME: "MyHeater",
            },
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown_error"}
