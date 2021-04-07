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
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert not result["errors"]

    with patch("uvcclient.nvr.UVCRemote.index", return_value="",), patch(
        "uvcclient.nvr.UVCRemote._get_bootstrap",
        return_value={"systemInfo": {"version": "3.3.0"}},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 81,
                "ssl": True,
                "api_key": "test-key",
                "password": "pass",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_auth_failure(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert not result["errors"]

    with patch("uvcclient.nvr.UVCRemote.index", side_effect=nvr.NotAuthorized,), patch(
        "uvcclient.nvr.UVCRemote._get_bootstrap",
        return_value={"systemInfo": {"version": "0.3.0"}},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 81,
                "ssl": True,
                "api_key": "test-key",
                "password": "pass",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_cannot_connect(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert not result["errors"]

    with patch("uvcclient.nvr.UVCRemote.index", side_effect=nvr.NvrError,), patch(
        "uvcclient.nvr.UVCRemote._get_bootstrap",
        return_value={"systemInfo": {"version": "0.3.0"}},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 81,
                "ssl": True,
                "api_key": "test-key",
                "password": "pass",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_general_error(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert not result["errors"]

    with patch("uvcclient.nvr.UVCRemote.index", side_effect=Exception,), patch(
        "uvcclient.nvr.UVCRemote._get_bootstrap",
        return_value={"systemInfo": {"version": "0.3.0"}},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 81,
                "ssl": True,
                "api_key": "test-key",
                "password": "pass",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"]["base"] == "unknown"


async def test_import_yaml(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch("uvcclient.nvr.UVCRemote.index", return_value="",), patch(
        "uvcclient.nvr.UVCRemote._get_bootstrap",
        return_value={"systemInfo": {"version": "0.3.0"}},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "1.1.1.1",
                "api_key": "test-key",
                "name": "Printer",
                "port": 81,
                "ssl": True,
                "path": "/",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert "errors" not in result


async def test_import_aborts_if_configured(hass):
    """Test config import doesn't re-import unnecessarily."""

    MockConfigEntry(domain=DOMAIN, unique_id="uuid", data={}).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
