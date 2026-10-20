# tests/components/pushmeld/test_notify.py
"""Tests for the PushMeld notification service."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError, web
from aiohttp.test_utils import TestServer
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.notify import ATTR_DATA, ATTR_TITLE
from homeassistant.components.notify.const import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.pushmeld import notify
from homeassistant.components.pushmeld.const import ATTR_DETAILS, CONF_MAXCODE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession


@pytest.fixture
async def request_recorder(
    aiohttp_server: Callable[[web.Application], TestServer],
) -> tuple[str, list[dict[str, Any]]]:
    """Start a local HTTP endpoint that records one or more requests."""
    requests: list[dict[str, Any]] = []

    async def handle(request: web.Request) -> web.Response:
        requests.append(
            {
                "headers": {
                    "Authorization": request.headers["Authorization"],
                    "Content-Type": request.headers["Content-Type"],
                },
                "payload": await request.json(),
            }
        )
        return web.Response(status=204, text="This response body is ignored")

    app = web.Application()
    app.router.add_post("/", handle)
    server = await aiohttp_server(app)
    return str(server.make_url("/")), requests


async def test_send_message_forwards_pushmeld_payload(
    hass: HomeAssistant,
    request_recorder: tuple[str, list[dict[str, Any]]],
    monkeypatch: pytest.MonkeyPatch,
    socket_enabled: None,
) -> None:
    """Send exactly the PushMeld payload without interpreting the response."""
    api_url, requests = request_recorder
    monkeypatch.setattr(notify, "API_URL", api_url)
    service = notify.PushMeldNotificationService(
        async_get_clientsession(hass),
        "test-maxcode",
    )

    await service.async_send_message(
        "A message",
        **{
            ATTR_TITLE: "A title",
            ATTR_DATA: {ATTR_DETAILS: "Additional details"},
        },
    )

    assert requests == [
        {
            "headers": {
                "Authorization": "MaxCode test-maxcode",
                "Content-Type": "application/json",
            },
            "payload": {
                "title": "A title",
                "message": "A message",
                "details": "Additional details",
            },
        }
    ]


async def test_send_message_omits_details_when_not_supplied(
    hass: HomeAssistant,
    request_recorder: tuple[str, list[dict[str, Any]]],
    monkeypatch: pytest.MonkeyPatch,
    socket_enabled: None,
) -> None:
    """Do not invent a details field when Home Assistant did not provide one."""
    api_url, requests = request_recorder
    monkeypatch.setattr(notify, "API_URL", api_url)
    service = notify.PushMeldNotificationService(
        async_get_clientsession(hass),
        "test-maxcode",
    )

    await service.async_send_message("A message", **{ATTR_DATA: {}})

    assert requests[0]["payload"] == {
        "title": "Home Assistant",
        "message": "A message",
    }


async def test_registered_service_forwards_home_assistant_call(
    hass: HomeAssistant,
    request_recorder: tuple[str, list[dict[str, Any]]],
    monkeypatch: pytest.MonkeyPatch,
    socket_enabled: None,
) -> None:
    """Forward a real Home Assistant notify service call unchanged."""
    api_url, requests = request_recorder
    monkeypatch.setattr(notify, "API_URL", api_url)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MAXCODE: "test-maxcode", "name": "Test channel"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "test_channel",
        {
            "title": "A title",
            "message": "A message",
            "data": {ATTR_DETAILS: "Additional details"},
        },
        blocking=True,
    )

    assert requests[0]["headers"]["Authorization"] == "MaxCode test-maxcode"
    assert requests[0]["payload"] == {
        "title": "A title",
        "message": "A message",
        "details": "Additional details",
    }

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_send_message_raises_for_non_success_status(
    hass: HomeAssistant,
    aiohttp_server: Callable[[web.Application], TestServer],
    monkeypatch: pytest.MonkeyPatch,
    socket_enabled: None,
) -> None:
    """Surface an HTTP failure without reading or parsing its response body."""

    async def handle(_request: web.Request) -> web.Response:
        return web.Response(status=401, text="not JSON")

    app = web.Application()
    app.router.add_post("/", handle)
    server = await aiohttp_server(app)
    monkeypatch.setattr(notify, "API_URL", str(server.make_url("/")))
    service = notify.PushMeldNotificationService(
        async_get_clientsession(hass),
        "test-maxcode",
    )

    with pytest.raises(HomeAssistantError) as err:
        await service.async_send_message("A message")

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "request_failed"
    assert err.value.translation_placeholders == {"status_code": "401"}


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        (TimeoutError(), "timeout"),
        (ClientError("connection failed"), "cannot_connect"),
    ],
)
async def test_send_message_surfaces_transport_errors(
    hass: HomeAssistant,
    exception: Exception,
    translation_key: str,
) -> None:
    """Convert transport failures into translated Home Assistant errors."""
    request = MagicMock()
    request.__aenter__ = AsyncMock(side_effect=exception)
    request.__aexit__ = AsyncMock()
    session = MagicMock()
    session.post.return_value = request
    service = notify.PushMeldNotificationService(session, "test-maxcode")

    with pytest.raises(HomeAssistantError) as err:
        await service.async_send_message("A message")

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == translation_key


async def test_async_get_service_requires_valid_entry_discovery(
    hass: HomeAssistant,
) -> None:
    """Only create a service for a complete config-entry discovery payload."""
    assert await notify.async_get_service(hass, {}, None) is None
    assert (
        await notify.async_get_service(
            hass,
            {},
            {CONF_MAXCODE: "test-maxcode"},
        )
        is None
    )
    assert (
        await notify.async_get_service(
            hass,
            {},
            {CONF_MAXCODE: "test-maxcode", "entry_id": "missing"},
        )
        is None
    )


async def test_config_entry_registers_and_unloads_notification_service(
    hass: HomeAssistant,
) -> None:
    """Register one local notify service per config entry and unload it cleanly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MAXCODE: "test-maxcode", "name": "Test channel"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.services.has_service(NOTIFY_DOMAIN, "test_channel")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(NOTIFY_DOMAIN, "test_channel")
