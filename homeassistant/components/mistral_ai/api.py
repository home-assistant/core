"""Low-level helpers for the Mistral AI API."""

from typing import Any

from mistralai.client import Mistral
from mistralai.client.types import UNSET
import mistralai.client.utils.security  # noqa: F401


def is_unset(value: Any) -> bool:
    """Return whether a value is the SDK UNSET sentinel."""
    return isinstance(value, type(UNSET))


def fetch_models(client: Mistral) -> list[Any]:
    """Fetch the list of available models from the Mistral API."""
    return client.models.list(timeout_ms=10_000).data or []


def get_model_ids(api_key: str, capability: str) -> list[str]:
    """Return the model IDs supporting a given capability."""
    client = Mistral(api_key=api_key)
    _ = client.models

    return sorted(
        model.id
        for model in fetch_models(client)
        if getattr(getattr(model, "capabilities", None), capability, False)
    )
