"""Test the imap_email_content sensor config flow."""
import imaplib
from unittest.mock import MagicMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.imap_email_content.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_DATA = {
    "username": "email@email.com",
    "password": "password",
    "server": "imap.server.com",
    "senders": "user1@example.com; user2@example.com",
    "port": 993,
    "folder": "INBOX",
    "value_template": "{{ subject }}",
    "verify_ssl": True,
}

MOCK_CONFIG = {
    "username": "email@email.com",
    "password": "password",
    "server": "imap.server.com",
    "senders": ["user1@example.com", "user2@example.com"],
    "port": 993,
    "folder": "INBOX",
    "value_template": "{{ subject }}",
    "verify_ssl": True,
}


async def test_config_flow_form(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.imap_email_content.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        mock_client.connect.return_value = True
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_DATA
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "email@email.com"
    assert result2["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_success(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test a successful import of yaml."""
    with patch(
        "homeassistant.components.imap_email_content.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        mock_client.connect.return_value = True
        config = MOCK_CONFIG.copy()
        config["name"] = "Test"
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=config,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test"
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
        result["flow_id"], MOCK_DATA
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_cannot_connect_imap(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test we handle imap connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client.side_effect = imaplib.IMAP4.error
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_DATA
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect_generic_error(hass: HomeAssistant) -> None:
    """Test we handle other connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.imap_email_content.sensor.EmailReader",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_DATA
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_senders(hass: HomeAssistant) -> None:
    """Test we handle invalid senders configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    config = MOCK_DATA.copy()
    config["senders"] = "invalid mail@domain.com"
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], config)

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_senders"}


async def test_options_form(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test we show the options form."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    new_data = MOCK_DATA.copy()
    new_data["senders"] = "test1@example.com; test2@example.com"
    new_config = MOCK_CONFIG.copy()
    new_config["senders"] = ["test1@example.com", "test2@example.com"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        new_data,
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert entry.data == new_config

    await hass.async_block_till_done()

    state = hass.states.get("sensor.email_email_com")
    assert state is not None
