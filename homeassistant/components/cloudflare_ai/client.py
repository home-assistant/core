"""Client wrapper around the official Cloudflare Python SDK."""

from __future__ import annotations

from collections.abc import AsyncGenerator
import json
import logging
from typing import Any

from cloudflare import APIConnectionError, AsyncCloudflare, AuthenticationError
import httpx

from .const import CF_AI_GATEWAY_BASE

_LOGGER = logging.getLogger(__name__)

# Parameters accepted by the cloudflare SDK's ai.run() method directly.
# Anything not in this set is passed via extra_body so the API can
# accept arbitrary model-specific parameters.
_SDK_RUN_PARAMS = frozenset(
    {
        "audio",
        "frequency_penalty",
        "functions",
        "guidance",
        "height",
        "ignore_eos",
        "image",
        "image_b64",
        "input_text",
        "lang",
        "lora",
        "max_length",
        "max_tokens",
        "messages",
        "negative_prompt",
        "num_steps",
        "presence_penalty",
        "prompt",
        "raw",
        "repetition_penalty",
        "response_format",
        "seed",
        "source_lang",
        "strength",
        "stream",
        "target_lang",
        "temperature",
        "text",
        "tools",
        "top_k",
        "top_p",
        "width",
    }
)

# Parameters accepted by the streaming variant of ai.run().
_SDK_STREAM_PARAMS = frozenset(
    {
        "frequency_penalty",
        "max_tokens",
        "messages",
        "presence_penalty",
        "temperature",
        "tools",
        "top_k",
        "top_p",
    }
)


class CloudflareAIError(Exception):
    """Base error for Cloudflare AI."""


class CloudflareAIAuthError(CloudflareAIError):
    """Authentication error."""


class CloudflareAIConnectionError(CloudflareAIError):
    """Connection error."""


class CloudflareAIClient:
    """Client for Cloudflare Workers AI.

    Wraps the official cloudflare SDK for direct API calls, and uses
    a separate httpx client for AI Gateway calls (which have a different
    URL pattern not supported by the SDK).
    """

    def __init__(
        self,
        cf: AsyncCloudflare,
        httpx_client: httpx.AsyncClient,
        account_id: str,
        api_token: str,
        gateway_id: str | None = None,
        gateway_api_token: str | None = None,
    ) -> None:
        """Initialize the client."""
        self._cf = cf
        self._httpx_client = httpx_client
        self._account_id = account_id
        self._api_token = api_token
        self._gateway_id = gateway_id
        self._gateway_api_token = gateway_api_token

    @property
    def use_gateway(self) -> bool:
        """Return True if AI Gateway is configured."""
        return bool(self._gateway_id)

    def _gateway_url(self, model: str) -> str:
        """Build the AI Gateway URL for a model."""
        return (
            f"{CF_AI_GATEWAY_BASE}/{self._account_id}"
            f"/{self._gateway_id}/workers-ai/{model}"
        )

    def _gateway_headers(self) -> dict[str, str]:
        """Build headers for AI Gateway requests."""
        gateway_token = self._gateway_api_token or self._api_token
        return {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
            "cf-aig-authorization": f"Bearer {gateway_token}",
        }

    async def run_model(
        self,
        model: str,
        input_data: dict[str, Any],
        *,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        """Run a model and return the parsed response dict."""
        try:
            if self.use_gateway:
                return await self._gateway_json(model, input_data, timeout)
            return await self._sdk_run(model, input_data, timeout)
        except AuthenticationError as err:
            raise CloudflareAIAuthError(str(err)) from err
        except APIConnectionError as err:
            raise CloudflareAIConnectionError(str(err)) from err
        except CloudflareAIError:
            raise
        except Exception as err:
            raise CloudflareAIError(str(err)) from err

    async def stream_model(
        self,
        model: str,
        input_data: dict[str, Any],
        timeout: float = 120.0,
    ) -> AsyncGenerator[dict[str, Any]]:
        """Stream model output as parsed SSE events."""
        try:
            if self.use_gateway:
                async for event in self._gateway_stream(model, input_data, timeout):
                    yield event
            else:
                async for event in self._sdk_stream(model, input_data, timeout):
                    yield event
        except AuthenticationError as err:
            raise CloudflareAIAuthError(str(err)) from err
        except APIConnectionError as err:
            raise CloudflareAIConnectionError(str(err)) from err
        except CloudflareAIError:
            raise
        except Exception as err:
            raise CloudflareAIError(str(err)) from err

    async def validate_credentials(self) -> bool:
        """Validate credentials by listing AI models."""
        try:
            await self._cf.ai.models.list(account_id=self._account_id)
        except AuthenticationError as err:
            raise CloudflareAIAuthError(str(err)) from err
        except APIConnectionError as err:
            raise CloudflareAIConnectionError(str(err)) from err
        except Exception as err:
            raise CloudflareAIConnectionError(str(err)) from err
        else:
            return True

    # ----------------------------------------------------------------
    # Direct Workers AI (via official SDK)
    # ----------------------------------------------------------------

    async def _sdk_run(
        self, model: str, input_data: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Run a model via the SDK."""
        sdk_kwargs: dict[str, Any] = {
            "account_id": self._account_id,
            "timeout": timeout,
        }
        extra: dict[str, Any] = {}

        for key, value in input_data.items():
            if key in _SDK_RUN_PARAMS:
                sdk_kwargs[key] = value
            else:
                extra[key] = value

        if extra:
            sdk_kwargs["extra_body"] = extra

        result = await self._cf.ai.run(model, **sdk_kwargs)

        if isinstance(result, dict):
            return result
        return {"response": str(result) if result else ""}

    async def _sdk_stream(
        self, model: str, input_data: dict[str, Any], timeout: float
    ) -> AsyncGenerator[dict[str, Any]]:
        """Stream via SDK."""
        sdk_kwargs: dict[str, Any] = {
            "account_id": self._account_id,
            "timeout": timeout,
            "stream": True,
        }
        extra: dict[str, Any] = {}

        for key, value in input_data.items():
            if key == "stream":
                continue
            if key in _SDK_STREAM_PARAMS:
                sdk_kwargs[key] = value
            else:
                extra[key] = value

        if extra:
            sdk_kwargs["extra_body"] = extra

        async with self._cf.ai.with_streaming_response.run(
            model, **sdk_kwargs
        ) as response:
            async for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    return
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    _LOGGER.debug("Failed to parse SSE: %s", payload)

    # ----------------------------------------------------------------
    # AI Gateway (via httpx client directly)
    # ----------------------------------------------------------------

    async def _gateway_json(
        self, model: str, input_data: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Run a model via AI Gateway."""
        resp = await self._httpx_client.post(
            self._gateway_url(model),
            json=input_data,
            headers=self._gateway_headers(),
            timeout=timeout,
        )
        self._check_http(resp)
        return self._unwrap(resp.json())

    async def _gateway_stream(
        self, model: str, input_data: dict[str, Any], timeout: float
    ) -> AsyncGenerator[dict[str, Any]]:
        """Stream via AI Gateway."""
        input_data = {**input_data, "stream": True}
        request = self._httpx_client.build_request(
            "POST",
            self._gateway_url(model),
            json=input_data,
            headers=self._gateway_headers(),
            timeout=timeout,
        )
        resp = await self._httpx_client.send(request, stream=True)
        try:
            self._check_http(resp)
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    return
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    _LOGGER.debug("Failed to parse SSE: %s", payload)
        finally:
            await resp.aclose()

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _unwrap(data: dict[str, Any]) -> dict[str, Any]:
        """Unwrap the CF API {result: ..., success: true} envelope."""
        if isinstance(data, dict) and "result" in data and "success" in data:
            return data["result"]
        return data

    @staticmethod
    def _check_http(resp: httpx.Response) -> None:
        """Check an httpx response for errors."""
        if resp.status_code == 401:
            raise CloudflareAIAuthError("Authentication failed")
        if resp.status_code == 403:
            raise CloudflareAIAuthError("Insufficient permissions")
        if resp.status_code >= 400:
            raise CloudflareAIError(f"API error {resp.status_code}: {resp.text[:200]}")
