"""Test Google Docs actions through Home Assistant's service registry."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.google_docs.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .common import DOCUMENT_ID, TOKEN_URI, http_error


async def test_append_text(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_api: dict[str, MagicMock],
) -> None:
    """The document is selected through its config entry and text is preserved."""
    await hass.services.async_call(
        DOMAIN,
        "append_text",
        {"config_entry": setup_integration.entry_id, "text": "שלום 🌍\n"},
        blocking=True,
    )
    mock_api["append_text"].assert_called_once_with(
        "mock-access-token", DOCUMENT_ID, "שלום 🌍\n"
    )


@pytest.mark.parametrize("text", ["Hello", "שלום 🌍\nLine two\n", ""])
async def test_get_text(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_api: dict[str, MagicMock],
    text: str,
) -> None:
    """A read returns data directly to the calling script or automation."""
    mock_api["get_document"].return_value["text"] = text
    result = await hass.services.async_call(
        DOMAIN,
        "get_text",
        {"config_entry": setup_integration.entry_id},
        blocking=True,
        return_response=True,
    )
    assert result == {
        "document_id": DOCUMENT_ID,
        "title": "Home Assistant",
        "text": text,
    }


@pytest.mark.parametrize(
    ("action", "fields", "return_response"),
    [("append_text", {"text": "Entry"}, False), ("get_text", {}, True)],
)
@pytest.mark.parametrize(
    ("status", "reauth_count"), [(401, 1), (403, 0), (404, 0), (429, 0), (503, 0)]
)
async def test_action_http_error(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_api: dict[str, MagicMock],
    action: str,
    fields: dict[str, str],
    return_response: bool,
    status: int,
    reauth_count: int,
) -> None:
    """Auth failures reauthenticate and access/server failures surface clearly."""
    mock_api["append_text"].side_effect = http_error(status)
    mock_api["get_document"].side_effect = http_error(status)
    data = {"config_entry": setup_integration.entry_id, **fields}
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            action,
            data,
            blocking=True,
            return_response=return_response,
        )
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == reauth_count


async def test_append_rejects_empty_text(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """An empty write is rejected before it reaches Google."""
    with pytest.raises(probatio.Invalid, match="length of value"):
        await hass.services.async_call(
            DOMAIN,
            "append_text",
            {"config_entry": setup_integration.entry_id, "text": ""},
            blocking=True,
        )


@pytest.mark.parametrize("entry_id", ["unknown", "wrong-domain"])
async def test_invalid_config_entry(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    entry_id: str,
) -> None:
    """An action cannot access a different integration's configuration entry."""
    other = MockConfigEntry(domain="google_sheets", entry_id="wrong-domain", data={})
    other.add_to_hass(hass)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "append_text",
            {"config_entry": entry_id, "text": "Entry"},
            blocking=True,
        )


async def test_unloaded_entry(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """An unloaded document entry is unavailable to actions."""
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "get_text",
            {"config_entry": setup_integration.entry_id},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("action", "fields", "return_response", "api_method", "api_arguments"),
    [
        pytest.param(
            "append_text",
            {"text": "Entry"},
            False,
            "append_text",
            (DOCUMENT_ID, "Entry"),
            id="append",
        ),
        pytest.param("get_text", {}, True, "get_document", (DOCUMENT_ID,), id="read"),
    ],
)
async def test_action_refresh_survives_unload(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_api: dict[str, MagicMock],
    action: str,
    fields: dict[str, str],
    return_response: bool,
    api_method: str,
    api_arguments: tuple[str, ...],
) -> None:
    """An in-flight action retains its session when the entry is unloaded."""
    token = {**setup_integration.data["token"], "expires_at": 0}
    hass.config_entries.async_update_entry(
        setup_integration, data={**setup_integration.data, "token": token}
    )
    refresh_started = asyncio.Event()
    finish_refresh = asyncio.Event()

    async def async_refresh_token(
        token: dict[str, str | float],
    ) -> dict[str, str | float]:
        refresh_started.set()
        await finish_refresh.wait()
        return {
            **token,
            "access_token": "refreshed-access-token",
            "expires_at": time.time() + 3600,
        }

    mock_api["get_document"].reset_mock()
    with patch.object(
        setup_integration.runtime_data.implementation,
        "async_refresh_token",
        side_effect=async_refresh_token,
    ):
        action_task = hass.async_create_task(
            hass.services.async_call(
                DOMAIN,
                action,
                {"config_entry": setup_integration.entry_id, **fields},
                blocking=True,
                return_response=return_response,
            )
        )
        try:
            await refresh_started.wait()
            assert await hass.config_entries.async_unload(setup_integration.entry_id)
            assert not hasattr(setup_integration, "runtime_data")
        finally:
            finish_refresh.set()
        await action_task

    mock_api[api_method].assert_called_once_with(
        "refreshed-access-token", *api_arguments
    )


@pytest.mark.parametrize(
    ("action", "fields", "return_response"),
    [
        pytest.param("append_text", {"text": "Entry"}, False, id="append"),
        pytest.param("get_text", {}, True, id="read"),
    ],
)
@pytest.mark.parametrize(
    ("status", "error", "reauth_count", "translation_key"),
    [
        pytest.param(400, None, 1, "auth_failed", id="invalid-grant"),
        pytest.param(503, None, 0, "cannot_connect", id="server-error"),
        pytest.param(200, TimeoutError(), 0, "cannot_connect", id="timeout"),
    ],
)
async def test_action_refresh_failure(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    mock_api: dict[str, MagicMock],
    action: str,
    fields: dict[str, str],
    return_response: bool,
    status: int,
    error: Exception | None,
    reauth_count: int,
    translation_key: str,
) -> None:
    """A failed token refresh prevents Docs calls and only invalid grants reauth."""
    token = {**setup_integration.data["token"], "expires_at": 0}
    hass.config_entries.async_update_entry(
        setup_integration, data={**setup_integration.data, "token": token}
    )
    aioclient_mock.post(
        TOKEN_URI, status=status, json={"error": "invalid_grant"}, exc=error
    )
    mock_api["get_document"].reset_mock()
    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            DOMAIN,
            action,
            {"config_entry": setup_integration.entry_id, **fields},
            blocking=True,
            return_response=return_response,
        )
    await hass.async_block_till_done()
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == translation_key
    mock_api["append_text"].assert_not_called()
    mock_api["get_document"].assert_not_called()
    assert len(hass.config_entries.flow.async_progress()) == reauth_count
