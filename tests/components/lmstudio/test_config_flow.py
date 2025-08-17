"""Test the LM Studio config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import openai
import pytest

from homeassistant import config_entries
from homeassistant.components.lmstudio.config_flow import (
    _create_max_tokens_selector,
    _create_model_options,
    _create_model_selector,
    _create_temperature_selector,
    _create_top_p_selector,
    _safe_fetch_models,
    _safe_fetch_models_with_errors,
    validate_input,
)
from homeassistant.components.lmstudio.const import (
    DOMAIN,
    MAX_MAX_TOKENS,
    MAX_TEMPERATURE,
    MAX_TOP_P,
    MIN_MAX_TOKENS,
    MIN_TEMPERATURE,
    MIN_TOP_P,
    TEMPERATURE_STEP,
    TOP_P_STEP,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import selector

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant, mock_openai_client_config_flow: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    # Configure connection step
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "base_url": "http://localhost:1234/v1",
            "api_key": "test-key",
        },
    )

    # Should show model selection step
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "model"

    # Configure model step
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            "model": "test-model",
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "http://localhost:1234/v1"
    assert result3["data"] == {
        "base_url": "http://localhost:1234/v1",
        "api_key": "test-key",
        "model": "test-model",
    }
    assert len(result3["subentries"]) == 1
    assert result3["subentries"][0]["subentry_type"] == "conversation"


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lmstudio.config_flow._fetch_available_models",
        side_effect=openai.AuthenticationError(
            response=httpx.Response(
                status_code=401, request=httpx.Request(method="GET", url="test")
            ),
            body=None,
            message="Invalid API key",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "base_url": "http://localhost:1234/v1",
                "api_key": "test-key",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lmstudio.config_flow._fetch_available_models",
        side_effect=openai.APIConnectionError(
            request=httpx.Request(method="GET", url="test")
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "base_url": "http://localhost:1234/v1",
                "api_key": "test-key",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unexpected_exception(hass: HomeAssistant) -> None:
    """Test we handle unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lmstudio.config_flow._fetch_available_models",
        side_effect=Exception("Unexpected error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "base_url": "http://localhost:1234/v1",
                "api_key": "test-key",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(
    hass: HomeAssistant, mock_openai_client_config_flow: AsyncMock
) -> None:
    """Test we handle already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"base_url": "http://localhost:1234/v1", "api_key": "test-key"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "base_url": "http://localhost:1234/v1",
            "api_key": "test-key",
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_validate_input_success(
    hass: HomeAssistant, mock_openai_client_config_flow: AsyncMock
) -> None:
    """Test validate_input function success."""
    models = await validate_input(
        hass,
        {
            "base_url": "http://localhost:1234/v1",
            "api_key": "test-key",
        },
    )

    # Check that models list is returned
    assert isinstance(models, list)
    assert len(models) > 0
    assert all(isinstance(model, str) for model in models)

    mock_openai_client_config_flow.with_options.assert_called_once_with(timeout=10.0)
    mock_openai_client_config_flow.with_options.return_value.models.list.assert_called_once()


async def test_validate_input_connection_error(hass: HomeAssistant) -> None:
    """Test validate_input function with connection error."""
    with (
        patch(
            "homeassistant.components.lmstudio.config_flow.openai.AsyncOpenAI",
            side_effect=openai.APIConnectionError(
                request=httpx.Request(method="GET", url="test")
            ),
        ),
        pytest.raises(openai.APIConnectionError),
    ):
        await validate_input(
            hass,
            {
                "base_url": "http://localhost:1234/v1",
                "api_key": "test-key",
            },
        )


async def test_options_flow(
    hass: HomeAssistant, mock_openai_client_config_flow: AsyncMock
) -> None:
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "base_url": "http://localhost:1234/v1",
            "api_key": "test-key",
            "model": "old-model",
            "available_models": ["old-model", "new-model", "another-model"],
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "model": "new-model",
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {}

    # Check that the config entry data was updated
    assert entry.data["model"] == "new-model"
    assert entry.data["base_url"] == "http://localhost:1234/v1"  # Unchanged
    assert entry.data["api_key"] == "test-key"  # Unchanged


def test_helper_functions() -> None:
    """Test NumberSelector helper functions."""
    # Test max tokens selector
    max_tokens_selector = _create_max_tokens_selector()
    assert max_tokens_selector.config["mode"] == "box"
    assert max_tokens_selector.config["min"] == MIN_MAX_TOKENS
    assert max_tokens_selector.config["max"] == MAX_MAX_TOKENS

    # Test temperature selector
    temperature_selector = _create_temperature_selector()
    assert temperature_selector.config["mode"] == "slider"
    assert temperature_selector.config["min"] == MIN_TEMPERATURE
    assert temperature_selector.config["max"] == MAX_TEMPERATURE
    assert temperature_selector.config["step"] == TEMPERATURE_STEP

    # Test top_p selector
    top_p_selector = _create_top_p_selector()
    assert top_p_selector.config["mode"] == "slider"
    assert top_p_selector.config["min"] == MIN_TOP_P
    assert top_p_selector.config["max"] == MAX_TOP_P
    assert top_p_selector.config["step"] == TOP_P_STEP


async def test_safe_fetch_models_fetch_error(hass: HomeAssistant) -> None:
    """Test _safe_fetch_models when model fetching fails."""
    # Test with no cached models and fetch error - should return empty list
    with patch(
        "homeassistant.components.lmstudio.config_flow._fetch_available_models",
        side_effect=Exception("API Error"),
    ):
        models = await _safe_fetch_models(hass, "http://localhost:1234", "test-key", [])
        assert models == []


def test_create_model_options() -> None:
    """Test _create_model_options function."""
    # Test with empty list
    result = _create_model_options([])
    assert result == []

    # Test with single model
    result = _create_model_options(["gpt-4"])
    expected = [{"value": "gpt-4", "label": "gpt-4"}]
    assert result == expected

    # Test with multiple models
    result = _create_model_options(["gpt-4", "gpt-3.5-turbo", "claude-3"])
    expected = [
        {"value": "gpt-4", "label": "gpt-4"},
        {"value": "gpt-3.5-turbo", "label": "gpt-3.5-turbo"},
        {"value": "claude-3", "label": "claude-3"},
    ]
    assert result == expected


def test_create_model_selector() -> None:
    """Test _create_model_selector function."""
    # Test with default model
    models = [{"value": "gpt-4", "label": "gpt-4"}]
    result = _create_model_selector(models)
    assert isinstance(result, selector.SelectSelector)
    assert result.config["options"] == models
    assert result.config["mode"] == "dropdown"
    assert result.config["custom_value"] is True

    # Test with custom default model
    result = _create_model_selector(models, "custom-model")
    assert isinstance(result, selector.SelectSelector)
    assert result.config["options"] == models


async def test_safe_fetch_models_with_errors_scenarios(hass: HomeAssistant) -> None:
    """Test _safe_fetch_models_with_errors with different scenarios."""
    # Test with connection error
    with patch(
        "homeassistant.components.lmstudio.config_flow._fetch_available_models"
    ) as mock_fetch:
        mock_fetch.side_effect = Exception("Connection failed")

        result, errors = await _safe_fetch_models_with_errors(
            hass, "http://localhost:1234/v1", "test-key"
        )

        assert result == []
        assert "base" in errors
        assert errors["base"] == "unknown"

    # Test with API connection error
    with patch(
        "homeassistant.components.lmstudio.config_flow._fetch_available_models"
    ) as mock_fetch:
        mock_fetch.side_effect = openai.APIConnectionError(
            request=httpx.Request(method="GET", url="http://localhost:1234")
        )

        result, errors = await _safe_fetch_models_with_errors(
            hass, "http://localhost:1234/v1", "test-key"
        )

        assert result == []
        assert "base" in errors
        assert errors["base"] == "cannot_connect"

    # Test with auth error
    with patch(
        "homeassistant.components.lmstudio.config_flow._fetch_available_models"
    ) as mock_fetch:
        mock_fetch.side_effect = openai.AuthenticationError(
            response=httpx.Response(
                status_code=401,
                request=httpx.Request(method="GET", url="http://localhost:1234"),
            ),
            body=None,
            message="Invalid API key",
        )

        result, errors = await _safe_fetch_models_with_errors(
            hass, "http://localhost:1234/v1", "test-key"
        )

        assert result == []
        assert "base" in errors
        assert errors["base"] == "invalid_auth"

    # Test with successful fetch
    with patch(
        "homeassistant.components.lmstudio.config_flow._fetch_available_models"
    ) as mock_fetch:
        mock_fetch.return_value = [{"label": "test-model", "value": "test-model"}]

        result, errors = await _safe_fetch_models_with_errors(
            hass, "http://localhost:1234/v1", "test-key"
        )

        assert len(result) == 1
        assert result[0]["label"] == "test-model"
        assert errors == {}


async def test_safe_fetch_models_scenarios(hass: HomeAssistant) -> None:
    """Test _safe_fetch_models with different scenarios."""
    # Test with cached models (string format)
    cached_models = ["model1", "model2"]
    result = await _safe_fetch_models(
        hass, "http://localhost:1234/v1", "test-key", cached_models
    )

    assert len(result) == 2
    assert result[0]["label"] == "model1"
    assert result[1]["label"] == "model2"

    # Test with cached models (dict format) - this covers line 239
    cached_models_dict = [
        {"label": "Model 1", "value": "model1"},
        {"label": "Model 2", "value": "model2"},
    ]
    result = await _safe_fetch_models(
        hass, "http://localhost:1234/v1", "test-key", cached_models_dict
    )

    assert len(result) == 2
    assert result[0]["label"] == "Model 1"
    assert result[1]["label"] == "Model 2"

    # Test with no cached models and fetch succeeds
    with patch(
        "homeassistant.components.lmstudio.config_flow._fetch_available_models"
    ) as mock_fetch:
        mock_fetch.return_value = [{"label": "test-model", "value": "test-model"}]

        result = await _safe_fetch_models(
            hass, "http://localhost:1234/v1", "test-key", None
        )

        assert len(result) == 1
        assert result[0]["label"] == "test-model"

    # Test with exception during fetch - should return empty list
    with patch(
        "homeassistant.components.lmstudio.config_flow._fetch_available_models"
    ) as mock_fetch:
        mock_fetch.side_effect = Exception("Connection failed")

        result = await _safe_fetch_models(
            hass, "http://localhost:1234/v1", "test-key", None
        )

        assert result == []


async def test_validate_input_unknown_error(hass: HomeAssistant) -> None:
    """Test validate_input with unknown error type."""
    data = {
        "base_url": "http://localhost:1234/v1",
        "api_key": "test-key",
    }

    # Simulate unknown error by patching _safe_fetch_models_with_errors
    with patch(
        "homeassistant.components.lmstudio.config_flow._safe_fetch_models_with_errors"
    ) as mock_safe_fetch:
        mock_safe_fetch.return_value = ([], {"base": "unknown"})

        with pytest.raises(openai.APIError):
            await validate_input(hass, data)


async def test_validate_input_with_errors(hass: HomeAssistant) -> None:
    """Test validate_input with different error scenarios."""
    data = {
        "base_url": "http://localhost:1234/v1",
        "api_key": "test-key",
    }

    # Test with invalid auth error
    with patch(
        "homeassistant.components.lmstudio.config_flow.openai.AsyncOpenAI"
    ) as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value = mock_instance
        mock_with_options = AsyncMock()
        mock_models = AsyncMock()
        mock_models.list = AsyncMock(
            side_effect=openai.AuthenticationError(
                response=httpx.Response(
                    status_code=401,
                    request=httpx.Request(method="GET", url="http://localhost:1234"),
                ),
                body=None,
                message="Invalid API key",
            )
        )
        mock_with_options.models = mock_models
        mock_instance.with_options = lambda timeout: mock_with_options

        with pytest.raises(openai.AuthenticationError):
            await validate_input(hass, data)
