"""Test the imap config flow."""
import asyncio
from unittest.mock import patch

from aioimaplib import AioImapException

from homeassistant import config_entries
from homeassistant.components.imap.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry

MOCK_CONFIG = {
    "username": "email@email.com",
    "password": "password",
    "server": "imap.server.com",
    "port": 993,
    "charset": "utf-8",
    "folder": "INBOX",
    "search": "UnSeen UnDeleted",
}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server", return_value=True
    ), patch(
        "homeassistant.components.imap.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "email@email.com"
    assert result2["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml."""
    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server", return_value=True
    ), patch(
        "homeassistant.components.imap.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "name": "IMAP",
                "username": "email@email.com",
                "password": "password",
                "server": "imap.server.com",
                "port": 993,
                "charset": "utf-8",
                "folder": "INBOX",
                "search": "UnSeen UnDeleted",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "IMAP"
    assert result2["data"] == {
        "name": "IMAP",
        "username": "email@email.com",
        "password": "password",
        "server": "imap.server.com",
        "port": 993,
        "charset": "utf-8",
        "folder": "INBOX",
        "search": "UnSeen UnDeleted",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_device_already_configured(hass: HomeAssistant) -> None:
    """Test aborting if the device is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "email@email.com",
            "password": "password",
            "server": "imap.server.com",
            "port": 993,
            "charset": "utf-8",
            "folder": "INBOX",
            "search": "UnSeen UnDeleted",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "already_configured"


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server",
        side_effect=AioImapException(""),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server",
        side_effect=asyncio.TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=MOCK_CONFIG,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {CONF_USERNAME: "email@email.com"}

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server", return_value=True
    ), patch(
        "homeassistant.components.imap.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "reauth_successful"


async def test_reauth_failed(hass: HomeAssistant) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=MOCK_CONFIG,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server",
        side_effect=AioImapException(""),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "test-wrong-password",
            },
        )

        assert result2["type"] == RESULT_TYPE_FORM
        assert result2["errors"] == {
            "base": "invalid_auth",
        }


async def test_reauth_failed_conn_error(hass: HomeAssistant) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=MOCK_CONFIG,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server",
        side_effect=asyncio.TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "test-wrong-password",
            },
        )

        assert result2["type"] == RESULT_TYPE_FORM
        assert result2["errors"] == {"base": "cannot_connect"}
