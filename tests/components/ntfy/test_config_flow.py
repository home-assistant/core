"""Test the ntfy config flow."""

from typing import Any
from unittest.mock import AsyncMock

from aiontfy.exceptions import (
    NtfyException,
    NtfyHTTPError,
    NtfyUnauthorizedAuthenticationError,
)
import pytest

from homeassistant.components.ntfy.const import CONF_TOPIC, DOMAIN, SECTION_AUTH
from homeassistant.config_entries import SOURCE_USER, ConfigSubentry
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("user_input", "entry_data"),
    [
        (
            {
                CONF_URL: "https://ntfy.sh",
                SECTION_AUTH: {CONF_USERNAME: "username", CONF_PASSWORD: "password"},
            },
            {
                CONF_URL: "https://ntfy.sh/",
                CONF_USERNAME: "username",
                CONF_TOKEN: "token",
            },
        ),
        (
            {CONF_URL: "https://ntfy.sh", SECTION_AUTH: {}},
            {CONF_URL: "https://ntfy.sh/", CONF_USERNAME: None, CONF_TOKEN: "token"},
        ),
    ],
)
@pytest.mark.usefixtures("mock_aiontfy")
async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    user_input: dict[str, Any],
    entry_data: dict[str, Any],
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ntfy.sh"
    assert result["data"] == entry_data
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            NtfyHTTPError(418001, 418, "I'm a teapot", ""),
            "cannot_connect",
        ),
        (
            NtfyUnauthorizedAuthenticationError(
                40101,
                401,
                "unauthorized",
                "https://ntfy.sh/docs/publish/#authentication",
            ),
            "invalid_auth",
        ),
        (NtfyException, "cannot_connect"),
        (TypeError, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_aiontfy: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_aiontfy.account.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://ntfy.sh",
            SECTION_AUTH: {CONF_USERNAME: "username", CONF_PASSWORD: "password"},
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_aiontfy.account.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://ntfy.sh",
            SECTION_AUTH: {CONF_USERNAME: "username", CONF_PASSWORD: "password"},
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ntfy.sh"
    assert result["data"] == {
        CONF_URL: "https://ntfy.sh/",
        CONF_USERNAME: "username",
        CONF_TOKEN: "token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_aiontfy")
async def test_form_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test we abort when entry is already configured."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: "https://ntfy.sh", SECTION_AUTH: {}},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_aiontfy")
async def test_add_topic_flow(hass: HomeAssistant) -> None:
    """Test add topic subentry flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://ntfy.sh/", CONF_USERNAME: None},
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "topic"),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.MENU
    assert "add_topic" in result["menu_options"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "add_topic"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_topic"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_TOPIC: "mytopic"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry_id = list(config_entry.subentries)[0]
    assert config_entry.subentries == {
        subentry_id: ConfigSubentry(
            data={CONF_TOPIC: "mytopic"},
            subentry_id=subentry_id,
            subentry_type="topic",
            title="mytopic",
            unique_id="mytopic",
        )
    }

    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_aiontfy")
async def test_generated_topic(hass: HomeAssistant, mock_random: AsyncMock) -> None:
    """Test add topic subentry flow with generated topic name."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://ntfy.sh/"},
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "topic"),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.MENU
    assert "generate_topic" in result["menu_options"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "generate_topic"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_topic"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_TOPIC: ""},
    )

    mock_random.assert_called_once()

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_TOPIC: "randomtopic", CONF_NAME: "mytopic"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry_id = list(config_entry.subentries)[0]
    assert config_entry.subentries == {
        subentry_id: ConfigSubentry(
            data={CONF_TOPIC: "randomtopic", CONF_NAME: "mytopic"},
            subentry_id=subentry_id,
            subentry_type="topic",
            title="mytopic",
            unique_id="randomtopic",
        )
    }


@pytest.mark.usefixtures("mock_aiontfy")
async def test_invalid_topic(hass: HomeAssistant, mock_random: AsyncMock) -> None:
    """Test add topic subentry flow with invalid topic name."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://ntfy.sh/"},
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "topic"),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.MENU
    assert "add_topic" in result["menu_options"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "add_topic"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_topic"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_TOPIC: "invalid,topic"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_topic"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_TOPIC: "mytopic"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry_id = list(config_entry.subentries)[0]
    assert config_entry.subentries == {
        subentry_id: ConfigSubentry(
            data={CONF_TOPIC: "mytopic"},
            subentry_id=subentry_id,
            subentry_type="topic",
            title="mytopic",
            unique_id="mytopic",
        )
    }


@pytest.mark.usefixtures("mock_aiontfy")
async def test_topic_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test we abort when entry is already configured."""

    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "topic"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    assert "add_topic" in result["menu_options"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "add_topic"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_topic"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_TOPIC: "mytopic"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
