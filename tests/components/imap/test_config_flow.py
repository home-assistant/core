"""Test the imap config flow."""
import asyncio
from unittest.mock import patch

from aioimaplib import AioImapException
import pytest

from homeassistant import config_entries
from homeassistant.components.imap.const import (
    CONF_CHARSET,
    CONF_FOLDER,
    CONF_SEARCH,
    DOMAIN,
)
from homeassistant.components.imap.errors import InvalidAuth, InvalidFolder
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

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
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server"
    ) as mock_client, patch(
        "homeassistant.components.imap.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        mock_client.return_value.search.return_value = (
            "OK",
            [b""],
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "email@email.com"
    assert result2["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml."""
    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server"
    ) as mock_client, patch(
        "homeassistant.components.imap.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        mock_client.return_value.search.return_value = (
            "OK",
            [b""],
        )
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

    assert result2["type"] == FlowResultType.CREATE_ENTRY
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


async def test_entry_already_configured(hass: HomeAssistant) -> None:
    """Test aborting if the entry is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

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

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {
        CONF_USERNAME: "invalid_auth",
        CONF_PASSWORD: "invalid_auth",
    }


@pytest.mark.parametrize(
    "exc",
    [asyncio.TimeoutError, AioImapException("")],
)
async def test_form_cannot_connect(hass: HomeAssistant, exc: Exception) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server",
        side_effect=exc,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_charset(hass: HomeAssistant) -> None:
    """Test we handle invalid charset."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server"
    ) as mock_client:
        mock_client.return_value.search.return_value = (
            "NO",
            [b"The specified charset is not supported"],
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_CHARSET: "invalid_charset"}


async def test_form_invalid_folder(hass: HomeAssistant) -> None:
    """Test we handle invalid folder selection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server",
        side_effect=InvalidFolder,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_FOLDER: "invalid_folder"}


async def test_form_invalid_search(hass: HomeAssistant) -> None:
    """Test we handle invalid search."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server"
    ) as mock_client:
        mock_client.return_value.search.return_value = (
            "BAD",
            [b"Invalid search"],
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_SEARCH: "invalid_search"}


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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {CONF_USERNAME: "email@email.com"}

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server"
    ) as mock_client, patch(
        "homeassistant.components.imap.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        mock_client.return_value.search.return_value = (
            "OK",
            [b""],
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1


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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "test-wrong-password",
            },
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {
            CONF_USERNAME: "invalid_auth",
            CONF_PASSWORD: "invalid_auth",
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

    assert result["type"] == FlowResultType.FORM
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

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}
