# tests/components/pushmeld/test_notify.py
"""Tests for the PushMeld notification service."""

import asyncio
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError, web
from aiohttp.test_utils import TestServer
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import pushmeld
from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    legacy as notify_legacy,
)
from homeassistant.components.pushmeld import notify
from homeassistant.components.pushmeld.const import ATTR_DETAILS, CONF_MAXCODE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.setup import async_setup_component


@pytest.fixture
async def request_recorder(
    aiohttp_server: Callable[[], TestServer],
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


@pytest.mark.usefixtures("socket_enabled")
async def test_send_message_forwards_pushmeld_payload(
    hass: HomeAssistant,
    request_recorder: tuple[str, list[dict[str, Any]]],
    monkeypatch: pytest.MonkeyPatch,
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


@pytest.mark.usefixtures("socket_enabled")
async def test_send_message_omits_details_when_not_supplied(
    hass: HomeAssistant,
    request_recorder: tuple[str, list[dict[str, Any]]],
    monkeypatch: pytest.MonkeyPatch,
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


@pytest.mark.usefixtures("socket_enabled")
async def test_registered_service_forwards_home_assistant_call(
    hass: HomeAssistant,
    request_recorder: tuple[str, list[dict[str, Any]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forward a real Home Assistant notify service call unchanged."""
    api_url, requests = request_recorder
    monkeypatch.setattr(notify, "API_URL", api_url)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test channel",
        data={CONF_MAXCODE: "test-maxcode"},
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


@pytest.mark.usefixtures("socket_enabled")
async def test_send_message_raises_for_non_success_status(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
    monkeypatch: pytest.MonkeyPatch,
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
        title="Test channel",
        data={CONF_MAXCODE: "test-maxcode"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.services.has_service(NOTIFY_DOMAIN, "test_channel")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(NOTIFY_DOMAIN, "test_channel")


async def test_setup_retries_when_notification_platform_fails_to_load(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry setup when discovery cannot load the notification platform."""
    monkeypatch.setattr(pushmeld, "NOTIFY_SERVICE_SETUP_TIMEOUT", 0.01)
    discovery_load = AsyncMock(return_value=None)
    monkeypatch.setattr(pushmeld.discovery, "async_load_platform", discovery_load)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test channel",
        data={CONF_MAXCODE: "test-maxcode"},
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    entry.async_cancel_retry_setup()
    discovery_load.assert_awaited_once()


async def test_entry_setup_does_not_wait_for_parent_setup_task(
    hass: HomeAssistant,
) -> None:
    """Set up an entry without waiting for its tracked component task."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test channel",
        data={CONF_MAXCODE: "test-maxcode"},
    )
    entry.add_to_hass(hass)

    setup_task = hass.async_create_task(async_setup_component(hass, DOMAIN, {}))

    assert await asyncio.wait_for(setup_task, timeout=1)
    assert hass.services.has_service(NOTIFY_DOMAIN, "test_channel")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_entry_setup_waits_for_notification_registration(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not register a notification action after its config entry unloads."""
    setup_started = asyncio.Event()
    release_setup = asyncio.Event()
    original_setup = notify.PushMeldNotificationService.async_setup

    async def delayed_setup(
        service: notify.PushMeldNotificationService,
        setup_hass: HomeAssistant,
        service_name: str,
        target_service_name_prefix: str,
    ) -> None:
        setup_started.set()
        await release_setup.wait()
        await original_setup(
            service, setup_hass, service_name, target_service_name_prefix
        )

    monkeypatch.setattr(
        notify.PushMeldNotificationService,
        "async_setup",
        delayed_setup,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test channel",
        data={CONF_MAXCODE: "test-maxcode"},
    )
    entry.add_to_hass(hass)

    setup_task = asyncio.create_task(hass.config_entries.async_setup(entry.entry_id))
    await setup_started.wait()

    assert not setup_task.done()
    release_setup.set()
    assert await setup_task
    await hass.async_block_till_done()

    assert hass.services.has_service(NOTIFY_DOMAIN, "test_channel")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(NOTIFY_DOMAIN, "test_channel")


async def test_stale_setup_error_does_not_fail_retry(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not let a timed-out loader fail a later setup attempt."""
    monkeypatch.setattr(pushmeld, "NOTIFY_SERVICE_SETUP_TIMEOUT", 0.01)
    old_setup_started = asyncio.Event()
    old_setup_finished = asyncio.Event()
    new_setup_started = asyncio.Event()
    release_old_setup = asyncio.Event()
    release_new_setup = asyncio.Event()
    setup_count = 0
    original_setup = notify.PushMeldNotificationService.async_setup

    async def delayed_setup(
        service: notify.PushMeldNotificationService,
        setup_hass: HomeAssistant,
        service_name: str,
        target_service_name_prefix: str,
    ) -> None:
        nonlocal setup_count
        setup_count += 1
        if setup_count == 1:
            old_setup_started.set()
            await release_old_setup.wait()
            await original_setup(
                service, setup_hass, service_name, target_service_name_prefix
            )
            old_setup_finished.set()
            return

        new_setup_started.set()
        await release_new_setup.wait()
        await original_setup(
            service, setup_hass, service_name, target_service_name_prefix
        )

    monkeypatch.setattr(
        notify.PushMeldNotificationService,
        "async_setup",
        delayed_setup,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test channel",
        data={CONF_MAXCODE: "test-maxcode"},
    )
    entry.add_to_hass(hass)

    first_setup = asyncio.create_task(hass.config_entries.async_setup(entry.entry_id))
    await old_setup_started.wait()
    assert not await first_setup
    assert entry.state is ConfigEntryState.SETUP_RETRY

    entry.async_cancel_retry_setup()
    entry._async_setup_again(hass)
    await new_setup_started.wait()

    release_old_setup.set()
    await old_setup_finished.wait()
    release_new_setup.set()

    await asyncio.wait_for(entry.runtime_data.notify_service_ready, timeout=1)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.services.has_service(NOTIFY_DOMAIN, "test_channel")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_stale_discovery_callback_does_not_register_after_retry(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ignore a discovery callback that belongs to an earlier setup attempt."""
    monkeypatch.setattr(pushmeld, "NOTIFY_SERVICE_SETUP_TIMEOUT", 0.01)
    old_callback_started = asyncio.Event()
    new_callback_started = asyncio.Event()
    release_old_callback = asyncio.Event()
    release_new_callback = asyncio.Event()
    callback_count = 0
    original_get_service = notify.async_get_service

    async def delayed_get_service(
        *args: Any,
        **kwargs: Any,
    ) -> notify.PushMeldNotificationService | None:
        nonlocal callback_count
        callback_count += 1
        if callback_count == 1:
            old_callback_started.set()
            await release_old_callback.wait()
        else:
            new_callback_started.set()
            await release_new_callback.wait()
        return await original_get_service(*args, **kwargs)

    monkeypatch.setattr(notify, "async_get_service", delayed_get_service)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Old channel",
        data={CONF_MAXCODE: "test-maxcode"},
    )
    entry.add_to_hass(hass)

    first_setup = asyncio.create_task(hass.config_entries.async_setup(entry.entry_id))
    await old_callback_started.wait()
    assert not await first_setup
    assert entry.state is ConfigEntryState.SETUP_RETRY

    object.__setattr__(entry, "title", "New channel")
    entry.async_cancel_retry_setup()
    entry._async_setup_again(hass)
    await new_callback_started.wait()

    release_old_callback.set()
    release_new_callback.set()
    await asyncio.wait_for(entry.runtime_data.notify_service_ready, timeout=1)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert not hass.services.has_service(NOTIFY_DOMAIN, "old_channel")
    assert hass.services.has_service(NOTIFY_DOMAIN, "new_channel")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_notify_reset_deletes_registry_after_services_unregister(
    hass: HomeAssistant,
) -> None:
    """Let the notify loader delete its registry after unregistering services."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test channel",
        data={CONF_MAXCODE: "test-maxcode"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN in hass.data[f"{NOTIFY_DOMAIN}_services"]

    await notify_legacy.async_reset_platform(hass, DOMAIN)

    assert DOMAIN not in hass.data[f"{NOTIFY_DOMAIN}_services"]
    assert not hass.services.has_service(NOTIFY_DOMAIN, "test_channel")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_reload_during_notification_setup_does_not_register_stale_service(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not retain a stale service when an entry reloads during setup."""
    old_setup_started = asyncio.Event()
    new_setup_started = asyncio.Event()
    release_old_setup = asyncio.Event()
    release_new_setup = asyncio.Event()
    setup_count = 0
    original_setup = notify.PushMeldNotificationService.async_setup

    async def delayed_setup(
        service: notify.PushMeldNotificationService,
        setup_hass: HomeAssistant,
        service_name: str,
        target_service_name_prefix: str,
    ) -> None:
        nonlocal setup_count
        setup_count += 1
        if setup_count == 1:
            old_setup_started.set()
            await release_old_setup.wait()
        else:
            new_setup_started.set()
            await release_new_setup.wait()
        await original_setup(
            service, setup_hass, service_name, target_service_name_prefix
        )

    monkeypatch.setattr(
        notify.PushMeldNotificationService,
        "async_setup",
        delayed_setup,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test channel",
        data={CONF_MAXCODE: "test-maxcode"},
    )
    entry.add_to_hass(hass)

    setup_task = asyncio.create_task(hass.config_entries.async_setup(entry.entry_id))
    await old_setup_started.wait()
    assert not setup_task.done()
    release_old_setup.set()
    assert await setup_task
    await hass.async_block_till_done()
    assert hass.services.has_service(NOTIFY_DOMAIN, "test_channel")

    reload_task = asyncio.create_task(hass.config_entries.async_reload(entry.entry_id))
    await new_setup_started.wait()
    assert not hass.services.has_service(NOTIFY_DOMAIN, "test_channel")
    release_new_setup.set()
    assert await reload_task
    await hass.async_block_till_done()

    assert hass.services.has_service(NOTIFY_DOMAIN, "test_channel")
    assert hass.data[f"{NOTIFY_DOMAIN}_services"][DOMAIN] == [
        entry.runtime_data.notify_service
    ]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_unload_does_not_remove_replacement_notification_service(
    hass: HomeAssistant,
) -> None:
    """Keep a replacement action that is no longer owned by PushMeld."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test channel",
        data={CONF_MAXCODE: "test-maxcode"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    replacement = AsyncMock()
    hass.services.async_register(NOTIFY_DOMAIN, "test_channel", replacement)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(NOTIFY_DOMAIN, "test_channel")


async def test_setup_does_not_remove_existing_notification_service(
    hass: HomeAssistant,
) -> None:
    """Do not remove another integration's notify action during setup failure."""
    hass.services.async_register(NOTIFY_DOMAIN, "test_channel", AsyncMock())
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test channel",
        data={CONF_MAXCODE: "test-maxcode"},
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "config_entry_error_name_exists"
    assert entry.error_reason_translation_placeholders == {
        "service_name": "test_channel"
    }
    assert hass.services.has_service(NOTIFY_DOMAIN, "test_channel")


async def test_setup_fails_when_name_is_taken_during_discovery(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail setup if another integration claims the name during discovery."""
    original_get_service = notify.async_get_service

    async def register_conflicting_service(
        setup_hass: HomeAssistant,
        config: Any,
        discovery_info: Any = None,
    ) -> notify.PushMeldNotificationService | None:
        setup_hass.services.async_register(NOTIFY_DOMAIN, "test_channel", AsyncMock())
        return await original_get_service(setup_hass, config, discovery_info)

    monkeypatch.setattr(notify, "async_get_service", register_conflicting_service)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test channel",
        data={CONF_MAXCODE: "test-maxcode"},
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "config_entry_error_name_exists"
    assert hass.services.has_service(NOTIFY_DOMAIN, "test_channel")
