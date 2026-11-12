"""Tests for the Mistral API helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from mistralai.client.types import UNSET

from homeassistant.components.mistral_ai.api import (
    async_create_client,
    fetch_models,
    get_model_ids,
    is_unset,
)
from homeassistant.core import HomeAssistant


def test_is_unset() -> None:
    """UNSET sentinel detection."""
    assert is_unset(UNSET)
    assert not is_unset(None)
    assert not is_unset("x")


async def test_fetch_models(hass: HomeAssistant) -> None:
    """fetch_models returns the model list."""
    client = SimpleNamespace(
        models=SimpleNamespace(
            list_async=AsyncMock(return_value=SimpleNamespace(data=["m1", "m2"]))
        )
    )
    assert await fetch_models(client) == ["m1", "m2"]


async def test_fetch_models_empty(hass: HomeAssistant) -> None:
    """fetch_models returns an empty list when the SDK has no data."""
    client = SimpleNamespace(
        models=SimpleNamespace(
            list_async=AsyncMock(return_value=SimpleNamespace(data=None))
        )
    )
    assert await fetch_models(client) == []


async def test_get_model_ids_filters_by_capability(hass: HomeAssistant) -> None:
    """get_model_ids keeps only models supporting the capability."""
    models = [
        SimpleNamespace(id="a", capabilities=SimpleNamespace(completion_chat=True)),
        SimpleNamespace(id="b", capabilities=SimpleNamespace(completion_chat=False)),
        SimpleNamespace(id="c", capabilities=None),
    ]
    client = SimpleNamespace(
        models=SimpleNamespace(
            list_async=AsyncMock(return_value=SimpleNamespace(data=models))
        )
    )
    assert await get_model_ids(client, "completion_chat") == ["a"]


async def test_async_create_client(hass: HomeAssistant) -> None:
    """async_create_client builds a client with the shared HTTP client."""
    with patch("homeassistant.components.mistral_ai.api.Mistral") as mistral_cls:
        await async_create_client(hass, "test-key")

    assert mistral_cls.called
    assert mistral_cls.call_args.kwargs["api_key"] == "test-key"
    assert "async_client" in mistral_cls.call_args.kwargs
