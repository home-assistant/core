"""Low-level helpers for the Mistral AI API."""

from contextlib import suppress
import importlib
from typing import Any, cast

from mistralai.client import Mistral, errors, utils
import mistralai.client.models as models_mod
from mistralai.client.types import UNSET
import mistralai.client.utils.security  # noqa: F401

from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client


def is_unset(value: Any) -> bool:
    """Return whether a value is the SDK UNSET sentinel."""
    return isinstance(value, type(UNSET))


def preload_mistral_sdk() -> None:
    """Materialize every lazily-imported Mistral SDK symbol up front.

    The Speakeasy-generated SDK resolves many names via module-level
    ``__getattr__`` hooks, which call ``import_module`` on *every* access (not
    just the first). That trips Home Assistant's "blocking call" detector when
    it happens inside the event loop. Run this in the executor and
    materialize each lazy attribute onto its module so ``__getattr__`` is never
    invoked again at call time.
    """
    for package in (utils, errors, models_mod):
        imports = getattr(package, "_dynamic_imports", {})

        modules: dict[str, Any] = {}
        for module_path in set(imports.values()):
            with suppress(ImportError):
                modules[module_path] = importlib.import_module(
                    module_path, package=package.__package__
                )

        for attr_name, module_path in imports.items():
            module = modules.get(module_path)
            if module is None:
                continue
            with suppress(AttributeError):
                setattr(package, attr_name, getattr(module, attr_name))


def create_client(api_key: str, async_client: Any) -> Mistral:
    """Create a Mistral client bound to Home Assistant's shared HTTP client.

    Runs synchronously in the executor so the SDK's lazy ``import_module``
    calls never block the event loop. ``async_client`` must be obtained on the
    event loop via :func:`homeassistant.helpers.httpx_client.get_async_client`.
    """
    client = Mistral(api_key=api_key, async_client=cast(Any, async_client))
    preload_mistral_sdk()

    # Force the lazy sub-SDKs (chat/models) to load now, in the executor.
    _ = client.chat
    _ = client.models

    return client


async def async_create_client(hass: HomeAssistant, api_key: str) -> Mistral:
    """Create a Mistral client, building it in the executor."""
    return await hass.async_add_executor_job(
        create_client, api_key, get_async_client(hass)
    )


async def fetch_models(client: Mistral) -> list[Any]:
    """Fetch the list of available models from the Mistral API."""
    return (await client.models.list_async(timeout_ms=10_000)).data or []


async def get_model_ids(client: Mistral, capability: str) -> list[str]:
    """Return the model IDs supporting a given capability."""
    return sorted(
        model.id
        for model in await fetch_models(client)
        if getattr(getattr(model, "capabilities", None), capability, False)
    )
