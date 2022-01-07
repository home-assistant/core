"""Test the UniFi Protect config flow."""
from __future__ import annotations

from unittest.mock import patch

from pyunifiprotect import NotAuthorized, NvrError
from pyunifiprotect.data.nvr import NVR

from homeassistant import config_entries
from homeassistant.components.unifiprotect.const import (
    CONF_ALL_UPDATES,
    CONF_DISABLE_RTSP,
    CONF_OVERRIDE_CHOST,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.helpers import device_registry as dr

from .conftest import MAC_ADDR

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_nvr: NVR) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_nvr",
        return_value=mock_nvr,
    ), patch(
        "homeassistant.components.unifiprotect.async_setup_entry",
        return_value=True,
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

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "UnifiProtect"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "username": "test-username",
        "password": "test-password",
        "id": "UnifiProtect",
        "port": 443,
        "verify_ssl": False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_version_too_old(hass: HomeAssistant, mock_old_nvr: NVR) -> None:
    """Test we handle the version being too old."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_nvr",
        return_value=mock_old_nvr,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "protect_version"}


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_nvr",
        side_effect=NotAuthorized,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"password": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_nvr",
        side_effect=NvrError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_reauth_auth(hass: HomeAssistant, mock_nvr: NVR) -> None:
    """Test we handle reauth auth."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
            "id": "UnifiProtect",
            "port": 443,
            "verify_ssl": False,
        },
        unique_id=dr.format_mac(MAC_ADDR),
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_nvr",
        side_effect=NotAuthorized,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"password": "invalid_auth"}
    assert result2["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_nvr",
        return_value=mock_nvr,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result3["type"] == RESULT_TYPE_ABORT
    assert result3["reason"] == "reauth_successful"


async def test_form_options(hass: HomeAssistant, mock_client) -> None:
    """Test we handle options flows."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
            "id": "UnifiProtect",
            "port": 443,
            "verify_ssl": False,
        },
        version=2,
        unique_id=dr.format_mac(MAC_ADDR),
    )
    mock_config.add_to_hass(hass)

    with patch("homeassistant.components.unifiprotect.ProtectApiClient") as mock_api:
        mock_api.return_value = mock_client

        await hass.config_entries.async_setup(mock_config.entry_id)
        await hass.async_block_till_done()
        assert mock_config.state == config_entries.ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(mock_config.entry_id)
    assert result["type"] == RESULT_TYPE_FORM
    assert not result["errors"]
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_DISABLE_RTSP: True, CONF_ALL_UPDATES: True, CONF_OVERRIDE_CHOST: True},
    )

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == {
        "all_updates": True,
        "disable_rtsp": True,
        "override_connection_host": True,
    }
