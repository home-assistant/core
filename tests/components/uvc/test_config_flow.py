"""Test the Unifi Video config flow."""
from unittest.mock import patch

from uvcclient import nvr

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.uvc.const import DOMAIN

from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.uvc.config_flow._test_connection",
        return_value=True,
    ), patch(
        "homeassistant.components.uvc.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.uvc.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "test-key",
                "password": "test-password",
                "ssl": False,
                "port": 4300,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "api_key": "test-key",
        "password": "test-password",
        "ssl": False,
        "port": 4300,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "uvcclient.nvr.UVCRemote",
        side_effect=nvr.NotAuthorized,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "test-test",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "uvcclient.nvr.UVCRemote",
        side_effect=nvr.NvrError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "test-key",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "uvcclient.nvr.UVCRemote",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "test-key",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_invalid_host(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.",
            "api_key": "test-test",
            "password": "test-password",
        },
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"host": "invalid_host"}


async def test_form_invalid_port(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "port": 0,
            "api_key": "test-test",
            "password": "test-password",
        },
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"port": "invalid_port"}


async def test_form_invalid_api_key(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "api_key": "te",
            "password": "test-password",
        },
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"api_key": "invalid_key"}


async def test_import(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.uvc.config_flow._test_connection",
        return_value=True,
    ), patch(
        "homeassistant.components.uvc.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.uvc.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "test-key",
                "password": "test-password",
                "ssl": False,
                "port": 4300,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "api_key": "test-key",
        "password": "test-password",
        "ssl": False,
        "port": 4300,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_already_config(hass):
    """Test we handle cannot connect error."""
    MockConfigEntry(domain=DOMAIN, data={}, unique_id="other").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
