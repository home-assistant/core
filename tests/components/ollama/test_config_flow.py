"""Test the Ollama config flow."""

import asyncio
from unittest.mock import patch

from httpx import ConnectError
import pytest

from homeassistant import config_entries
from homeassistant.components import ollama
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_MODEL = "test_model:latest"


async def test_form(hass: HomeAssistant) -> None:
    """Test flow when configuring URL only."""
    # Pretend we already set up a config entry.
    hass.config.components.add(ollama.DOMAIN)
    MockConfigEntry(
        domain=ollama.DOMAIN,
        state=config_entries.ConfigEntryState.LOADED,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        ollama.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.ollama.config_flow.ollama.AsyncClient.list",
            return_value={"models": [{"model": TEST_MODEL}]},
        ),
        patch(
            "homeassistant.components.ollama.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {ollama.CONF_URL: "http://localhost:11434"}
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        ollama.CONF_URL: "http://localhost:11434",
    }
    # No subentries created by default
    assert len(result2.get("subentries", [])) == 0
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test we abort on duplicate config entry."""
    MockConfigEntry(
        domain=ollama.DOMAIN,
        data={
            ollama.CONF_URL: "http://localhost:11434",
            ollama.CONF_MODEL: "test_model",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        ollama.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.ollama.config_flow.ollama.AsyncClient.list",
        return_value={"models": [{"model": "test_model"}]},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                ollama.CONF_URL: "http://localhost:11434",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_subentry_options(
    hass: HomeAssistant, mock_config_entry, mock_init_component
) -> None:
    """Test the subentry options form."""
    subentry = next(iter(mock_config_entry.subentries.values()))

    # Test reconfiguration
    with patch(
        "ollama.AsyncClient.list",
        return_value={"models": [{"model": TEST_MODEL}]},
    ):
        options_flow = await mock_config_entry.start_subentry_reconfigure_flow(
            hass, subentry.subentry_id
        )

        assert options_flow["type"] is FlowResultType.FORM
        assert options_flow["step_id"] == "set_options"

        options = await hass.config_entries.subentries.async_configure(
            options_flow["flow_id"],
            {
                ollama.CONF_MODEL: TEST_MODEL,
                ollama.CONF_PROMPT: "test prompt",
                ollama.CONF_MAX_HISTORY: 100,
                ollama.CONF_NUM_CTX: 32768,
                ollama.CONF_THINK: True,
            },
        )
    await hass.async_block_till_done()

    assert options["type"] is FlowResultType.ABORT
    assert options["reason"] == "reconfigure_successful"
    assert subentry.data == {
        ollama.CONF_MODEL: TEST_MODEL,
        ollama.CONF_PROMPT: "test prompt",
        ollama.CONF_MAX_HISTORY: 100.0,
        ollama.CONF_NUM_CTX: 32768.0,
        ollama.CONF_THINK: True,
    }


async def test_creating_new_conversation_subentry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test creating a new conversation subentry includes name field."""
    # Start a new subentry flow
    with patch(
        "ollama.AsyncClient.list",
        return_value={"models": [{"model": TEST_MODEL}]},
    ):
        new_flow = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

        assert new_flow["type"] is FlowResultType.FORM
        assert new_flow["step_id"] == "set_options"

        # Configure the new subentry with name field
        result = await hass.config_entries.subentries.async_configure(
            new_flow["flow_id"],
            {
                ollama.CONF_MODEL: TEST_MODEL,
                CONF_NAME: "New Test Conversation",
                ollama.CONF_PROMPT: "new test prompt",
                ollama.CONF_MAX_HISTORY: 50,
                ollama.CONF_NUM_CTX: 16384,
                ollama.CONF_THINK: False,
            },
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "New Test Conversation"
    assert result["data"] == {
        ollama.CONF_MODEL: TEST_MODEL,
        ollama.CONF_PROMPT: "new test prompt",
        ollama.CONF_MAX_HISTORY: 50.0,
        ollama.CONF_NUM_CTX: 16384.0,
        ollama.CONF_THINK: False,
    }


async def test_creating_conversation_subentry_not_loaded(
    hass: HomeAssistant,
    mock_init_component,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation subentry when entry is not loaded."""
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


async def test_subentry_need_download(
    hass: HomeAssistant,
    mock_init_component,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test subentry creation when model needs to be downloaded."""

    async def delayed_pull(self, model: str) -> None:
        """Simulate a delayed model download."""
        assert model == "llama3.2:latest"
        await asyncio.sleep(0)  # yield the event loop 1 iteration

    with (
        patch(
            "ollama.AsyncClient.list",
            return_value={"models": [{"model": TEST_MODEL}]},
        ),
        patch("ollama.AsyncClient.pull", delayed_pull),
    ):
        new_flow = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

        assert new_flow["type"] is FlowResultType.FORM, new_flow
        assert new_flow["step_id"] == "set_options"

        # Configure the new subentry with a model that needs downloading
        result = await hass.config_entries.subentries.async_configure(
            new_flow["flow_id"],
            {
                ollama.CONF_MODEL: "llama3.2:latest",  # not cached
                CONF_NAME: "New Test Conversation",
                ollama.CONF_PROMPT: "new test prompt",
                ollama.CONF_MAX_HISTORY: 50,
                ollama.CONF_NUM_CTX: 16384,
                ollama.CONF_THINK: False,
            },
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "download"
        assert result["progress_action"] == "download"

        await hass.async_block_till_done()

        result = await hass.config_entries.subentries.async_configure(
            new_flow["flow_id"], {}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "New Test Conversation"
    assert result["data"] == {
        ollama.CONF_MODEL: "llama3.2:latest",
        ollama.CONF_PROMPT: "new test prompt",
        ollama.CONF_MAX_HISTORY: 50.0,
        ollama.CONF_NUM_CTX: 16384.0,
        ollama.CONF_THINK: False,
    }


async def test_subentry_download_error(
    hass: HomeAssistant,
    mock_init_component,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test subentry creation when model download fails."""

    async def delayed_pull(self, model: str) -> None:
        """Simulate a delayed model download."""
        await asyncio.sleep(0)  # yield

        raise RuntimeError("Download failed")

    with (
        patch(
            "ollama.AsyncClient.list",
            return_value={"models": [{"model": TEST_MODEL}]},
        ),
        patch("ollama.AsyncClient.pull", delayed_pull),
    ):
        new_flow = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

        assert new_flow["type"] is FlowResultType.FORM
        assert new_flow["step_id"] == "set_options"

        # Configure with a model that needs downloading but will fail
        result = await hass.config_entries.subentries.async_configure(
            new_flow["flow_id"],
            {
                ollama.CONF_MODEL: "llama3.2:latest",
                CONF_NAME: "New Test Conversation",
                ollama.CONF_PROMPT: "new test prompt",
                ollama.CONF_MAX_HISTORY: 50,
                ollama.CONF_NUM_CTX: 16384,
                ollama.CONF_THINK: False,
            },
        )

        # Should show progress flow result for download
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "download"
        assert result["progress_action"] == "download"

        # Wait for download task to complete (with error)
        await hass.async_block_till_done()

        # Submit the progress flow - should get failure
        result = await hass.config_entries.subentries.async_configure(
            new_flow["flow_id"], {}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "download_failed"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ConnectError(message=""), "cannot_connect"),
        (RuntimeError(), "unknown"),
    ],
)
async def test_form_errors(hass: HomeAssistant, side_effect, error) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        ollama.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ollama.config_flow.ollama.AsyncClient.list",
        side_effect=side_effect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {ollama.CONF_URL: "http://localhost:11434"}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}


async def test_form_invalid_url(hass: HomeAssistant) -> None:
    """Test we handle invalid URL."""
    result = await hass.config_entries.flow.async_init(
        ollama.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {ollama.CONF_URL: "not-a-valid-url"}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_url"}


async def test_subentry_connection_error(
    hass: HomeAssistant,
    mock_init_component,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test subentry creation when connection to Ollama server fails."""
    with patch(
        "ollama.AsyncClient.list",
        side_effect=ConnectError("Connection failed"),
    ):
        new_flow = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

    assert new_flow["type"] is FlowResultType.ABORT
    assert new_flow["reason"] == "cannot_connect"


async def test_subentry_model_check_exception(
    hass: HomeAssistant,
    mock_init_component,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test subentry creation when checking model availability throws exception."""
    with patch(
        "ollama.AsyncClient.list",
        side_effect=[
            {"models": [{"model": TEST_MODEL}]},  # First call succeeds
            RuntimeError("Failed to check models"),  # Second call fails
        ],
    ):
        new_flow = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "conversation"),
            context={"source": config_entries.SOURCE_USER},
        )

        assert new_flow["type"] is FlowResultType.FORM
        assert new_flow["step_id"] == "set_options"

        # Configure with a model, should fail when checking availability
        result = await hass.config_entries.subentries.async_configure(
            new_flow["flow_id"],
            {
                ollama.CONF_MODEL: "new_model:latest",
                CONF_NAME: "Test Conversation",
                ollama.CONF_PROMPT: "test prompt",
                ollama.CONF_MAX_HISTORY: 50,
                ollama.CONF_NUM_CTX: 16384,
                ollama.CONF_THINK: False,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_subentry_reconfigure_with_download(
    hass: HomeAssistant,
    mock_init_component,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring subentry when model needs to be downloaded."""
    subentry = next(iter(mock_config_entry.subentries.values()))

    async def delayed_pull(self, model: str) -> None:
        """Simulate a delayed model download."""
        assert model == "llama3.2:latest"
        await asyncio.sleep(0)  # yield the event loop

    with (
        patch(
            "ollama.AsyncClient.list",
            return_value={"models": [{"model": TEST_MODEL}]},
        ),
        patch("ollama.AsyncClient.pull", delayed_pull),
    ):
        reconfigure_flow = await mock_config_entry.start_subentry_reconfigure_flow(
            hass, subentry.subentry_id
        )

        assert reconfigure_flow["type"] is FlowResultType.FORM
        assert reconfigure_flow["step_id"] == "set_options"

        # Reconfigure with a model that needs downloading
        result = await hass.config_entries.subentries.async_configure(
            reconfigure_flow["flow_id"],
            {
                ollama.CONF_MODEL: "llama3.2:latest",
                ollama.CONF_PROMPT: "updated prompt",
                ollama.CONF_MAX_HISTORY: 75,
                ollama.CONF_NUM_CTX: 8192,
                ollama.CONF_THINK: True,
            },
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "download"

        await hass.async_block_till_done()

        # Finish download
        result = await hass.config_entries.subentries.async_configure(
            reconfigure_flow["flow_id"], {}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert subentry.data == {
        ollama.CONF_MODEL: "llama3.2:latest",
        ollama.CONF_PROMPT: "updated prompt",
        ollama.CONF_MAX_HISTORY: 75.0,
        ollama.CONF_NUM_CTX: 8192.0,
        ollama.CONF_THINK: True,
    }


async def test_creating_ai_task_subentry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test creating an AI task subentry."""
    old_subentries = set(mock_config_entry.subentries)
    # Original conversation + original ai_task
    assert len(mock_config_entry.subentries) == 2

    with patch(
        "ollama.AsyncClient.list",
        return_value={"models": [{"model": "test_model:latest"}]},
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_config_entry.entry_id, "ai_task_data"),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "set_options"
    assert not result.get("errors")

    with patch(
        "ollama.AsyncClient.list",
        return_value={"models": [{"model": "test_model:latest"}]},
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                "name": "Custom AI Task",
                ollama.CONF_MODEL: "test_model:latest",
                ollama.CONF_MAX_HISTORY: 5,
                ollama.CONF_NUM_CTX: 4096,
                ollama.CONF_KEEP_ALIVE: 30,
                ollama.CONF_THINK: False,
            },
        )
        await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "Custom AI Task"
    assert result2.get("data") == {
        ollama.CONF_MODEL: "test_model:latest",
        ollama.CONF_MAX_HISTORY: 5,
        ollama.CONF_NUM_CTX: 4096,
        ollama.CONF_KEEP_ALIVE: 30,
        ollama.CONF_THINK: False,
    }

    assert (
        len(mock_config_entry.subentries) == 3
    )  # Original conversation + original ai_task + new ai_task

    new_subentry_id = list(set(mock_config_entry.subentries) - old_subentries)[0]
    new_subentry = mock_config_entry.subentries[new_subentry_id]
    assert new_subentry.subentry_type == "ai_task_data"
    assert new_subentry.title == "Custom AI Task"


async def test_ai_task_subentry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating an AI task subentry when entry is not loaded."""
    # Don't call mock_init_component to simulate not loaded state
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_data"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "entry_not_loaded"
