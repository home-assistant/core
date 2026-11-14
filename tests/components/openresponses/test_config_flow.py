"""Tests for the Open Responses config flow."""

from unittest.mock import MagicMock

from openresponses_client import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
)
import pytest

from homeassistant.components.openresponses.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LLM_HASS_API,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_URL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import llm

from .conftest import TEST_URL

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("user_input", "expected_data"),
    [
        pytest.param(
            {CONF_URL: f" {TEST_URL}/ ", CONF_API_KEY: "sk-test"},
            {CONF_URL: TEST_URL, CONF_API_KEY: "sk-test"},
            id="with_api_key",
        ),
        pytest.param(
            {CONF_URL: TEST_URL},
            {CONF_URL: TEST_URL},
            id="without_api_key",
        ),
    ],
)
async def test_user_flow(
    hass: HomeAssistant,
    mock_client: MagicMock,
    user_input: dict[str, str],
    expected_data: dict[str, str],
) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "localhost"
    assert result["data"] == expected_data
    assert result["subentries"] == ()


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            AuthenticationError("Invalid key", status=401),
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(
            PermissionDeniedError("Forbidden", status=403),
            "invalid_auth",
            id="permission_denied",
        ),
        pytest.param(
            APIConnectionError("Connection refused"),
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(
            NotFoundError("Not found", status=404),
            "cannot_connect",
            id="wrong_url",
        ),
        pytest.param(RuntimeError("Boom"), "unknown", id="unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_client: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test errors in the user flow and recovering from them."""
    mock_client.create.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: TEST_URL, CONF_API_KEY: "sk-test"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.create.side_effect = BadRequestError("Missing model", status=400)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: TEST_URL, CONF_API_KEY: "sk-test"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_client")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a server can only be added once."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: f"{TEST_URL}/"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("llm_hass_api", "expected_data"),
    [
        pytest.param(
            [llm.LLM_API_ASSIST],
            {
                CONF_MODEL: "qwen3:8b",
                CONF_PROMPT: "Be brief.",
                CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
            },
            id="with_llm_api",
        ),
        pytest.param(
            [],
            {CONF_MODEL: "qwen3:8b", CONF_PROMPT: "Be brief."},
            id="without_llm_api",
        ),
    ],
)
async def test_create_conversation_subentry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    llm_hass_api: list[str],
    expected_data: dict[str, str | list[str]],
) -> None:
    """Test creating a conversation agent."""
    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, "conversation"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "qwen3:8b",
            CONF_PROMPT: "Be brief.",
            CONF_LLM_HASS_API: llm_hass_api,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "qwen3:8b"
    assert result["data"] == expected_data


async def test_reconfigure_conversation_subentry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test reconfiguring a conversation agent."""
    result = await init_integration.start_subentry_reconfigure_flow(
        hass, "ulid-conversation"
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_MODEL: "qwen3:8b", CONF_PROMPT: "Be brief."},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    subentry = init_integration.subentries["ulid-conversation"]
    assert subentry.title == "qwen3:8b"
    assert subentry.data == {CONF_MODEL: "qwen3:8b", CONF_PROMPT: "Be brief."}
