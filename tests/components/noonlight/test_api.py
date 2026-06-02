"""Unit tests for the thin Noonlight API client.

These exercise the client in isolation (its own httpx.AsyncClient + respx),
covering the error-mapping and response-parsing branches the coordinator
relies on but never drives directly in the happy path.
"""

from __future__ import annotations

import json

import httpx
from httpx import Response
import pytest
import respx

from homeassistant.components.noonlight.api import (
    NoonlightApi,
    NoonlightAuthError,
    NoonlightConnectionError,
    NoonlightResponseError,
    resolve_base_url,
)
from homeassistant.components.noonlight.const import (
    API_BASE_PROD,
    API_BASE_SANDBOX,
    ENV_CUSTOM,
    ENV_PRODUCTION,
    ENV_SANDBOX,
)

SANDBOX = API_BASE_SANDBOX
_ALARMS = f"{SANDBOX}/dispatch/v1/alarms"
_STATUS = f"{SANDBOX}/dispatch/v1/alarms/abc/status"


def _api() -> NoonlightApi:
    return NoonlightApi(
        httpx.AsyncClient(),
        "tok",
        base_url=SANDBOX,
        environment=ENV_SANDBOX,
    )


# -- resolve_base_url ---------------------------------------------------------


def test_resolve_named_environments():
    assert resolve_base_url(ENV_PRODUCTION, None) == API_BASE_PROD
    assert resolve_base_url(ENV_SANDBOX, None) == API_BASE_SANDBOX


def test_resolve_custom_strips_trailing_slash():
    assert (
        resolve_base_url(ENV_CUSTOM, "https://example.test/") == "https://example.test"
    )


def test_resolve_custom_requires_url():
    with pytest.raises(ValueError):
        resolve_base_url(ENV_CUSTOM, None)


def test_resolve_unknown_environment():
    with pytest.raises(ValueError):
        resolve_base_url("nope", None)


# -- environment flags --------------------------------------------------------


def test_is_production_flags():
    assert _api().is_production is False
    prod = NoonlightApi(
        httpx.AsyncClient(),
        "t",
        base_url=API_BASE_PROD,
        environment=ENV_PRODUCTION,
    )
    assert prod.is_production is True
    # Custom is treated as production for safety.
    custom = NoonlightApi(
        httpx.AsyncClient(),
        "t",
        base_url="https://x.test",
        environment=ENV_CUSTOM,
    )
    assert custom.is_production is True


# -- request error mapping ----------------------------------------------------


@respx.mock
async def test_auth_error_on_401():
    respx.get(_STATUS).mock(return_value=Response(401))
    with pytest.raises(NoonlightAuthError):
        await _api().get_alarm_status("abc")


@respx.mock
async def test_auth_error_on_403():
    respx.get(_STATUS).mock(return_value=Response(403))
    with pytest.raises(NoonlightAuthError):
        await _api().get_alarm_status("abc")


@respx.mock
async def test_response_error_on_500():
    respx.get(_STATUS).mock(return_value=Response(500, text="boom"))
    with pytest.raises(NoonlightResponseError):
        await _api().get_alarm_status("abc")


@respx.mock
async def test_connection_error_on_transport_failure():
    respx.get(_STATUS).mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(NoonlightConnectionError):
        await _api().get_alarm_status("abc")


@respx.mock
async def test_connection_error_on_timeout():
    respx.get(_STATUS).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(NoonlightConnectionError):
        await _api().get_alarm_status("abc")


@respx.mock
async def test_non_json_body_is_response_error():
    respx.get(_STATUS).mock(return_value=Response(200, text="not json", headers={}))
    with pytest.raises(NoonlightResponseError):
        await _api().get_alarm_status("abc")


@respx.mock
async def test_non_object_body_is_response_error():
    respx.get(_STATUS).mock(return_value=Response(200, json=[1, 2, 3]))
    with pytest.raises(NoonlightResponseError):
        await _api().get_alarm_status("abc")


@respx.mock
async def test_empty_body_returns_empty_dict():
    respx.get(_STATUS).mock(return_value=Response(204))
    assert await _api().get_alarm_status("abc") == {}


# -- endpoints ----------------------------------------------------------------


@respx.mock
async def test_create_alarm_builds_expected_payload():
    route = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "a1", "status": "ACTIVE"})
    )
    result = await _api().create_alarm(
        services=["police", "fire"],
        name="Main",
        phone="+15555550123",
        address="1 Test St",
        city="Testville",
        state="ca",
        zip_code="90001",
    )
    assert result["id"] == "a1"
    payload = json.loads(route.calls.last.request.content)
    assert payload["services"] == {"police": True, "fire": True}
    assert payload["location"]["address"]["zip"] == "90001"
    # Noonlight rejects a leading "+": the payload carries digits only.
    assert payload["phone"] == "15555550123"
    # Noonlight only accepts the uppercase 2-letter state code.
    assert payload["location"]["address"]["state"] == "CA"


@respx.mock
async def test_create_alarm_includes_instructions():
    route = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "a1", "status": "ACTIVE"})
    )
    await _api().create_alarm(
        services=["police"],
        name="n",
        phone="+15555550123",
        address="a",
        city="c",
        state="ca",
        zip_code="90001",
        instructions="Triggered by Front Door motion",
    )
    payload = json.loads(route.calls.last.request.content)
    # Noonlight requires an object with only the 'entry' key.
    assert payload["instructions"] == {"entry": "Triggered by Front Door motion"}


@respx.mock
async def test_create_alarm_omits_empty_instructions():
    route = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "a1", "status": "ACTIVE"})
    )
    await _api().create_alarm(
        services=["police"],
        name="n",
        phone="+15555550123",
        address="a",
        city="c",
        state="ca",
        zip_code="90001",
    )
    assert "instructions" not in json.loads(route.calls.last.request.content)


@respx.mock
async def test_create_alarm_includes_owner_id():
    route = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "a1", "status": "ACTIVE"})
    )
    await _api().create_alarm(
        services=["police"],
        name="n",
        phone="+15555550123",
        address="a",
        city="c",
        state="ca",
        zip_code="90001",
        owner_id="Site A",
    )
    assert json.loads(route.calls.last.request.content)["owner_id"] == "Site A"


@respx.mock
async def test_create_alarm_omits_empty_owner_id():
    route = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "a1", "status": "ACTIVE"})
    )
    await _api().create_alarm(
        services=["police"],
        name="n",
        phone="+15555550123",
        address="a",
        city="c",
        state="ca",
        zip_code="90001",
    )
    assert "owner_id" not in json.loads(route.calls.last.request.content)


@respx.mock
async def test_create_alarm_without_id_raises():
    respx.post(_ALARMS).mock(return_value=Response(201, json={"status": "X"}))
    with pytest.raises(NoonlightResponseError):
        await _api().create_alarm(
            services=["police"],
            name="n",
            phone="p",
            address="a",
            city="c",
            state="s",
            zip_code="z",
        )


@respx.mock
async def test_cancel_alarm_posts_canceled_status():
    route = respx.post(_STATUS).mock(
        return_value=Response(200, json={"status": "CANCELED"})
    )
    await _api().cancel_alarm("abc")
    assert json.loads(route.calls.last.request.content) == {"status": "CANCELED"}
