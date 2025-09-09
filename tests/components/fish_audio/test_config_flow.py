"""Config flow tests for Fish Audio."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from homeassistant.components.fish_audio.const import (
    CONF_API_KEY,
    CONF_BACKEND,
    CONF_LANGUAGE,
    CONF_SELF_ONLY,
    CONF_SORT_BY,
    CONF_VOICE_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def _prime_models(mock_async_client) -> None:
    """Give the session a predictable models payload for the happy path."""
    sess = (
        mock_async_client.return_value
    )  # the constructor's return_value (our session)
    sess.list_models.return_value = SimpleNamespace(
        items=[
            SimpleNamespace(id="z-id", title="Zulu"),
            SimpleNamespace(id="a-id", title="Alpha"),
            SimpleNamespace(id="m-id", title="Mike"),
        ]
    )


@pytest.mark.asyncio
async def test_user_flow_happy_path(hass: HomeAssistant, mock_async_client) -> None:
    """User -> filter -> model -> creates entry (no platform setup assertions)."""
    _prime_models(mock_async_client)

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    # Provide API key
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "key123"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "filter"

    # Provide filters -> should go to model step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_SELF_ONLY: True,
            CONF_LANGUAGE: "en",
            CONF_SORT_BY: "score",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"

    # Select model/backend -> create entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_VOICE_ID: "a-id", CONF_BACKEND: "s1"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fish Audio"
    assert result["data"] == {CONF_API_KEY: "key123"}
    assert result["options"] == {
        CONF_SELF_ONLY: True,
        CONF_LANGUAGE: "en",
        CONF_SORT_BY: "score",
        CONF_VOICE_ID: "a-id",
        CONF_BACKEND: "s1",
    }


@pytest.mark.asyncio
async def test_user_flow_invalid_api_key(
    hass: HomeAssistant, mock_async_client_connect_error
) -> None:
    """Invalid API key keeps us on user step with cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "bad-key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_models_error_bounces_back_to_filter(
    hass: HomeAssistant, mock_async_client
) -> None:
    """If listing models fails, we bounce back to filter with 'no_models_found'."""
    # Start and pass the user step
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "ok"}
    )
    assert result["step_id"] == "filter"

    # Make models listing raise
    sess = mock_async_client.return_value
    sess.list_models.side_effect = RuntimeError("boom")

    # Submit filters -> should return to filter with error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_SELF_ONLY: False,
            CONF_LANGUAGE: "en",
            CONF_SORT_BY: "score",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "filter"
    assert result["errors"] == {"base": "no_models_found"}


@pytest.mark.asyncio
async def test_model_step_requires_voice_id(
    hass: HomeAssistant, mock_async_client
) -> None:
    """Submitting model step without CONF_VOICE_ID stays on model with error."""
    _prime_models(mock_async_client)

    # Reach model step
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "ok"}
    )
    assert result["step_id"] == "filter"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_SELF_ONLY: False,
            CONF_LANGUAGE: "en",
            CONF_SORT_BY: "score",
        },
    )
    assert result["step_id"] == "model"

    # Missing voice id -> stay on model with error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_BACKEND: "s1"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"
    assert result["errors"] == {"base": "no_model_selected"}


# -------------------------
# Options flow
# -------------------------


@pytest.mark.asyncio
async def test_options_flow_happy_path(
    hass: HomeAssistant, mock_async_client, mock_entry
) -> None:
    """Options flow: init -> filter -> model -> create entry with updated options."""
    _prime_models(mock_async_client)

    mock_entry.add_to_hass(hass)

    # Begin options flow (validates API key)
    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Change filters -> model step
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SELF_ONLY: True, CONF_LANGUAGE: "de", CONF_SORT_BY: "score"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "model"

    # Pick voice/backend -> create entry
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_VOICE_ID: "m-id", CONF_BACKEND: "s1"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_entry.options == {
        CONF_SELF_ONLY: True,
        CONF_LANGUAGE: "de",
        CONF_SORT_BY: "score",
        CONF_VOICE_ID: "m-id",
        CONF_BACKEND: "s1",
    }


@pytest.mark.asyncio
async def test_options_flow_cannot_connect_aborts(
    hass: HomeAssistant, mock_async_client_connect_error, mock_entry
) -> None:
    """Options flow aborts if API key validation fails."""
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
