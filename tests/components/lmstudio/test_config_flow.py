"""Test the LM Studio config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components import lmstudio
from homeassistant.components.lmstudio import const
from homeassistant.components.lmstudio.client import (
    LMStudioAuthError,
    LMStudioConnectionError,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import TEST_USER_DATA

from tests.common import MockConfigEntry


async def test_form_success(hass: HomeAssistant) -> None:
    """Test flow when configuring URL and API key."""
    result = await hass.config_entries.flow.async_init(
        lmstudio.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.lmstudio.config_flow.LMStudioClient.async_list_models",
        return_value=[{"key": "test-model"}],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_USER_DATA[CONF_URL],
                CONF_API_KEY: TEST_USER_DATA[CONF_API_KEY],
            },
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == TEST_USER_DATA


async def test_invalid_url(hass: HomeAssistant) -> None:
    """Test invalid URL handling."""
    result = await hass.config_entries.flow.async_init(
        lmstudio.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "not a url"}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_url"


async def test_cannot_connect(hass: HomeAssistant) -> None:
    """Test we show cannot_connect for connection errors."""
    result = await hass.config_entries.flow.async_init(
        lmstudio.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lmstudio.config_flow.LMStudioClient.async_list_models",
        side_effect=LMStudioConnectionError("nope"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: TEST_USER_DATA[CONF_URL]}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test we show invalid_auth for auth errors."""
    result = await hass.config_entries.flow.async_init(
        lmstudio.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lmstudio.config_flow.LMStudioClient.async_list_models",
        side_effect=LMStudioAuthError("bad"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: TEST_USER_DATA[CONF_URL]}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_auth"


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test we abort on duplicate config entry."""
    MockConfigEntry(
        domain=lmstudio.DOMAIN,
        data={CONF_URL: TEST_USER_DATA[CONF_URL]},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        lmstudio.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.lmstudio.config_flow.LMStudioClient.async_list_models",
        return_value=[{"key": "test-model"}],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: TEST_USER_DATA[CONF_URL]}
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reauth_flow_updates_entry(hass: HomeAssistant) -> None:
    """Test reauthentication flow updates the entry."""
    entry = MockConfigEntry(domain=lmstudio.DOMAIN, data=TEST_USER_DATA)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        lmstudio.DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.lmstudio.config_flow.LMStudioClient.async_list_models",
        return_value=[{"key": "test-model"}],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_USER_DATA[CONF_URL],
                CONF_API_KEY: TEST_USER_DATA[CONF_API_KEY],
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_subentry_reconfigure(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test reconfiguring a subentry."""
    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch(
        "homeassistant.components.lmstudio.config_flow.LMStudioClient.async_list_models",
        return_value=[{"key": "test-model", "display_name": "Test Model"}],
    ):
        options_flow = await mock_config_entry.start_subentry_reconfigure_flow(
            hass, subentry.subentry_id
        )
        assert options_flow["type"] is FlowResultType.FORM

        result = await hass.config_entries.subentries.async_configure(
            options_flow["flow_id"],
            {
                const.CONF_MODEL: "test-model",
                const.CONF_PROMPT: "test prompt",
                const.CONF_MAX_HISTORY: 7,
                const.CONF_TEMPERATURE: 0.7,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert subentry.data[const.CONF_MODEL] == "test-model"
    assert subentry.data[const.CONF_PROMPT] == "test prompt"
    assert subentry.data[const.CONF_MAX_HISTORY] == 7.0
    assert subentry.data[const.CONF_TEMPERATURE] == 0.7


async def test_subentry_cannot_connect(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test subentry setup aborts on connection errors."""
    with patch(
        "homeassistant.components.lmstudio.config_flow.LMStudioClient.async_list_models",
        side_effect=LMStudioConnectionError("offline"),
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_create_new_conversation_subentry(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test creating a new conversation subentry includes name field."""
    with patch(
        "homeassistant.components.lmstudio.config_flow.LMStudioClient.async_list_models",
        return_value=[{"key": "test-model"}],
    ):
        new_flow = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )
        assert new_flow["type"] is FlowResultType.FORM

        result = await hass.config_entries.subentries.async_configure(
            new_flow["flow_id"],
            {
                CONF_NAME: "New LM Studio Conversation",
                const.CONF_MODEL: "test-model",
                const.CONF_PROMPT: "test prompt",
                const.CONF_MAX_HISTORY: 2,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "New LM Studio Conversation"
    assert result["data"][const.CONF_MODEL] == "test-model"


async def test_create_subentry_not_loaded(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test creating a subentry when entry is not loaded."""
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"
