"""Test the Ollama config flow."""

import asyncio
from unittest.mock import ANY, AsyncMock, patch

from httpx import ConnectError
from ollama import ResponseError
import pytest

from homeassistant import config_entries
from homeassistant.components import ollama
from homeassistant.components.ollama.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_MODEL = "test_model:latest"


async def test_form(hass: HomeAssistant) -> None:
    """Test flow when configuring URL only."""
    # Pretend we already set up a config entry.
    hass.config.components.add(DOMAIN)
    MockConfigEntry(
        domain=DOMAIN,
        state=config_entries.ConfigEntryState.LOADED,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
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
    assert result2["data"] == {ollama.CONF_URL: "http://localhost:11434"}

    # No subentries created by default
    assert len(result2.get("subentries", [])) == 0
    assert len(mock_setup_entry.mock_calls) == 1
    assert CONF_API_KEY not in result2["data"]


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test we abort on duplicate config entry."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            ollama.CONF_URL: "http://localhost:11434",
            ollama.CONF_MODEL: "test_model",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
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
            context={"source": SOURCE_USER},
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
        context={"source": SOURCE_USER},
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
            context={"source": SOURCE_USER},
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
            context={"source": SOURCE_USER},
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
    ("init_data", "input_data", "expected_data"),
    [
        (
            {
                CONF_URL: "http://localhost:11434",
                CONF_API_KEY: "old-api-key",
            },
            {
                CONF_API_KEY: "new-api-key",
            },
            {
                CONF_URL: "http://localhost:11434",
                CONF_API_KEY: "new-api-key",
            },
        ),
        (
            {
                CONF_URL: "http://localhost:11434",
                CONF_API_KEY: "old-api-key",
            },
            {
                # Reconfigure without api_key to test that it gets removed from data
            },
            {
                CONF_URL: "http://localhost:11434",
            },
        ),
    ],
)
async def test_reauth_flow_success(
    hass: HomeAssistant, init_data, input_data, expected_data
) -> None:
    """Test successful reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=init_data,
        options={CONF_API_KEY: "stale-options-api-key"},
        version=3,
        minor_version=3,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.ollama.config_flow.ollama.AsyncClient.list",
        return_value={"models": [{"model": TEST_MODEL}]},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            input_data,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert entry.data == expected_data
    assert entry.options == {}


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ResponseError(error="Unauthorized", status_code=401), "invalid_auth"),
        (ConnectError(message="Connection failed"), "cannot_connect"),
    ],
)
async def test_reauth_flow_errors(hass: HomeAssistant, side_effect, error) -> None:
    """Test reauthentication flow when authentication fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "http://localhost:11434",
            CONF_API_KEY: "old-api-key",
        },
        version=3,
        minor_version=3,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.ollama.config_flow.ollama.AsyncClient.list",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "other-api-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    with patch(
        "homeassistant.components.ollama.config_flow.ollama.AsyncClient.list",
        return_value={"models": [{"model": TEST_MODEL}]},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "new-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert entry.data == {
        CONF_URL: "http://localhost:11434",
        CONF_API_KEY: "new-api-key",
    }


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
        DOMAIN, context={"source": SOURCE_USER}
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


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ConnectError(message=""), "cannot_connect"),
        (RuntimeError(), "unknown"),
    ],
)
async def test_form_errors_recovery(hass: HomeAssistant, side_effect, error) -> None:
    """Test that the user flow recovers after an error and completes successfully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # First attempt fails
    with patch(
        "homeassistant.components.ollama.config_flow.ollama.AsyncClient.list",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {ollama.CONF_URL: "http://localhost:11434"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Second attempt succeeds
    with patch(
        "homeassistant.components.ollama.config_flow.ollama.AsyncClient.list",
        return_value={"models": [{"model": TEST_MODEL}]},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {ollama.CONF_URL: "http://localhost:11434"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {ollama.CONF_URL: "http://localhost:11434"}


async def test_form_invalid_url(hass: HomeAssistant) -> None:
    """Test we handle invalid URL."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
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
            context={"source": SOURCE_USER},
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
            context={"source": SOURCE_USER},
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


async def test_filter_invalid_llms(
    hass: HomeAssistant,
    mock_init_component,
    mock_config_entry_with_assist_invalid_api: MockConfigEntry,
) -> None:
    """Test reconfiguring subentry when one of the configured LLM APIs has been removed."""
    subentry = next(iter(mock_config_entry_with_assist_invalid_api.subentries.values()))

    assert len(subentry.data.get(CONF_LLM_HASS_API)) == 2
    assert "invalid_api" in subentry.data.get(CONF_LLM_HASS_API)
    assert "assist" in subentry.data.get(CONF_LLM_HASS_API)

    valid_apis = ollama.config_flow.filter_invalid_llm_apis(
        hass, subentry.data[CONF_LLM_HASS_API]
    )

    assert len(valid_apis) == 1
    assert "invalid_api" not in valid_apis
    assert "assist" in valid_apis


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
            context={"source": SOURCE_USER},
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
        context={"source": SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "entry_not_loaded"


@pytest.mark.parametrize(
    ("user_input", "expected_headers", "expected_data"),
    [
        (
            {CONF_URL: "http://localhost:11434", CONF_API_KEY: "my-secret-token"},
            {"Authorization": "Bearer my-secret-token"},
            {CONF_URL: "http://localhost:11434", CONF_API_KEY: "my-secret-token"},
        ),
        (
            {CONF_URL: "http://localhost:11434", CONF_API_KEY: ""},
            None,
            {CONF_URL: "http://localhost:11434"},
        ),
        (
            {CONF_URL: "http://localhost:11434", CONF_API_KEY: "          "},
            None,
            {CONF_URL: "http://localhost:11434"},
        ),
        (
            {CONF_URL: "http://localhost:11434"},
            None,
            {CONF_URL: "http://localhost:11434"},
        ),
    ],
)
async def test_user_step_async_client_headers(
    hass: HomeAssistant,
    user_input: dict[str, str],
    expected_headers: dict[str, str] | None,
    expected_data: dict[str, str],
) -> None:
    """Test Authorization header passed to AsyncClient with/without api_key."""
    with patch(
        "homeassistant.components.ollama.config_flow.ollama.AsyncClient",
    ) as mock_async_client:
        mock_async_client.return_value.list = AsyncMock(return_value={"models": []})

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == expected_data
    mock_async_client.assert_called_with(
        host="http://localhost:11434",
        headers=expected_headers,
        verify=ANY,
    )


@pytest.mark.parametrize(
    ("status_code", "error", "error_message", "user_input"),
    [
        (
            400,
            "unknown",
            "Bad Request",
            {
                CONF_URL: "http://localhost:11434",
                CONF_API_KEY: "my-secret-token",
            },
        ),
        (
            401,
            "invalid_auth",
            "Unauthorized",
            {
                CONF_URL: "http://localhost:11434",
                CONF_API_KEY: "my-secret-token",
            },
        ),
        (
            403,
            "invalid_auth",
            "Unauthorized",
            {
                CONF_URL: "http://localhost:11434",
                CONF_API_KEY: "my-secret-token",
            },
        ),
        (
            403,
            "invalid_auth",
            "Forbidden",
            {
                CONF_URL: "http://localhost:11434",
            },
        ),
    ],
)
async def test_user_step_errors(
    hass: HomeAssistant,
    status_code: int,
    error: str,
    error_message: str,
    user_input: dict[str, str],
) -> None:
    """Test error handling when ollama returns HTTP 4xx."""
    with patch(
        "homeassistant.components.ollama.config_flow.ollama.AsyncClient"
    ) as mock_async_client:
        mock_client_instance = AsyncMock()
        mock_async_client.return_value = mock_client_instance

        mock_client_instance.list.side_effect = ResponseError(
            error=error_message, status_code=status_code
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result.get("errors") == {"base": error}


async def test_user_step_trim_url(hass: HomeAssistant) -> None:
    """Test URL is trimmed before validation and persistence."""
    with patch(
        "homeassistant.components.ollama.config_flow.ollama.AsyncClient",
    ) as mock_async_client:
        mock_async_client.return_value.list = AsyncMock(return_value={"models": []})

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_URL: "  http://localhost:11434  ",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_URL: "http://localhost:11434"}
    mock_async_client.assert_called_with(
        host="http://localhost:11434",
        headers=None,
        verify=ANY,
    )
