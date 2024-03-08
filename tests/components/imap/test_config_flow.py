"""Test the imap config flow."""
import ssl
from unittest.mock import AsyncMock, patch

from aioimaplib import AioImapException
import pytest
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
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

MOCK_OPTIONS = {
    "folder": "INBOX",
    "search": "UnSeen UnDeleted",
}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server"
    ) as mock_client:
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
    ("exc", "error"),
    [
        (TimeoutError, "cannot_connect"),
        (AioImapException(""), "cannot_connect"),
        (ssl.SSLError, "ssl_error"),
    ],
)
async def test_form_cannot_connect(
    hass: HomeAssistant, exc: Exception, error: str
) -> None:
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
    assert result2["errors"] == {"base": error}

    # make sure we do not lose the user input if somethings gets wrong
    assert {
        key: key.description.get("suggested_value")
        for key in result2["data_schema"].schema
    } == MOCK_CONFIG


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
        mock_client.return_value.search.return_value = ("BAD", [b"Invalid search"])
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_SEARCH: "invalid_search"}


async def test_reauth_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
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
    ) as mock_client:
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
        await hass.async_block_till_done()

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
        side_effect=TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "test-wrong-password",
            },
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_options_form(hass: HomeAssistant) -> None:
    """Test we show the options form."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    new_config = MOCK_OPTIONS.copy()
    new_config["folder"] = "INBOX.Notifications"
    new_config["search"] = "UnSeen UnDeleted!!INVALID"

    # simulate initial search setup error
    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server"
    ) as mock_client:
        mock_client.return_value.search.return_value = ("BAD", [b"Invalid search"])
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], new_config
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_SEARCH: "invalid_search"}

    new_config["search"] = "UnSeen UnDeleted"

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server"
    ) as mock_client:
        mock_client.return_value.search.return_value = ("OK", [b""])
        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            new_config,
        )
        await hass.async_block_till_done()
    assert result3["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result3["data"] == {}
    for key, value in new_config.items():
        assert entry.data[key] == value


async def test_key_options_in_options_form(hass: HomeAssistant) -> None:
    """Test we cannot change options if that would cause duplicates."""

    entry1 = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry1.add_to_hass(hass)
    await hass.config_entries.async_setup(entry1.entry_id)

    config2 = MOCK_CONFIG.copy()
    config2["folder"] = "INBOX.Notifications"
    entry2 = MockConfigEntry(domain=DOMAIN, data=config2)
    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)

    # Now try to set back the folder option of entry2
    # so that it conflicts with that of entry1
    result = await hass.config_entries.options.async_init(entry2.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    new_config = MOCK_OPTIONS.copy()

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server"
    ) as mock_client:
        mock_client.return_value.search.return_value = ("OK", [b""])
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            new_config,
        )
        await hass.async_block_till_done()
    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "already_configured"}


@pytest.mark.parametrize(
    ("advanced_options", "assert_result"),
    [
        ({"max_message_size": 8192}, data_entry_flow.FlowResultType.CREATE_ENTRY),
        ({"max_message_size": 1024}, data_entry_flow.FlowResultType.FORM),
        ({"max_message_size": 65536}, data_entry_flow.FlowResultType.FORM),
        (
            {"custom_event_data_template": "{{ subject }}"},
            data_entry_flow.FlowResultType.CREATE_ENTRY,
        ),
        (
            {"custom_event_data_template": "{{ invalid_syntax"},
            data_entry_flow.FlowResultType.FORM,
        ),
        ({"enable_push": True}, data_entry_flow.FlowResultType.CREATE_ENTRY),
        ({"enable_push": False}, data_entry_flow.FlowResultType.CREATE_ENTRY),
    ],
    ids=[
        "valid_message_size",
        "invalid_message_size_low",
        "invalid_message_size_high",
        "valid_template",
        "invalid_template",
        "enable_push_true",
        "enable_push_false",
    ],
)
async def test_advanced_options_form(
    hass: HomeAssistant,
    advanced_options: dict[str, str],
    assert_result: data_entry_flow.FlowResultType,
) -> None:
    """Test we show the advanced options."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    new_config = MOCK_OPTIONS.copy()
    new_config.update(advanced_options)

    try:
        with patch(
            "homeassistant.components.imap.config_flow.connect_to_server"
        ) as mock_client:
            mock_client.return_value.search.return_value = ("OK", [b""])
            # Option update should fail if FlowResultType.FORM is expected
            result2 = await hass.config_entries.options.async_configure(
                result["flow_id"], new_config
            )
            assert result2["type"] == assert_result

            if result2.get("errors") is not None:
                assert assert_result == data_entry_flow.FlowResultType.FORM
            else:
                # Check if entry was updated
                for key, value in new_config.items():
                    assert entry.data[key] == value
    except vol.Invalid:
        # Check if form was expected with these options
        assert assert_result == data_entry_flow.FlowResultType.FORM


@pytest.mark.parametrize("cipher_list", ["python_default", "modern", "intermediate"])
@pytest.mark.parametrize("verify_ssl", [False, True])
async def test_config_flow_with_cipherlist_and_ssl_verify(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, cipher_list: str, verify_ssl: True
) -> None:
    """Test with alternate cipherlist or disabled ssl verification."""
    config = MOCK_CONFIG.copy()
    config["ssl_cipher_list"] = cipher_list
    config["verify_ssl"] = verify_ssl
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server"
    ) as mock_client:
        mock_client.return_value.search.return_value = (
            "OK",
            [b""],
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "email@email.com"
    assert result2["data"] == config
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_from_with_advanced_settings(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test if advanced settings show correctly."""
    config = MOCK_CONFIG.copy()
    config["ssl_cipher_list"] = "python_default"
    config["verify_ssl"] = True
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server",
        side_effect=TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"
    assert "ssl_cipher_list" in result2["data_schema"].schema

    config["ssl_cipher_list"] = "modern"
    with patch(
        "homeassistant.components.imap.config_flow.connect_to_server"
    ) as mock_client:
        mock_client.return_value.search.return_value = (
            "OK",
            [b""],
        )
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], config
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "email@email.com"
    assert result3["data"] == config
    assert len(mock_setup_entry.mock_calls) == 1
