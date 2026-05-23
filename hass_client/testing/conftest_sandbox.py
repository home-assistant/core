"""Pytest plugin for running HA Core integration tests through a real sandbox websocket.

Layers on top of hass_client.testing.pytest_plugin: instead of creating a bare
RemoteHomeAssistant, this boots a host HA Core with websocket_api + sandbox
integration, starts a real aiohttp test server, creates a sandbox auth token,
and connects the sandbox RemoteHomeAssistant to it via a live websocket.

Tests that use the ``freezer`` fixture (pytest-freezer's FrozenDateTimeFactory)
fall back to the base plugin without a real websocket, because mid-test time
jumps hang live async connections.

Usage:
    pytest -p hass_client.testing.conftest_sandbox \
           ../core/tests/components/input_boolean/test_init.py
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator as _Generator
from contextlib import suppress
import threading

import pytest_asyncio

_pytest_fixture = pytest_asyncio.fixture

_state = threading.local()


def pytest_runtest_setup(item) -> None:
    """Detect tests that use the freezer fixture before hass setup runs."""
    _state.uses_freezer = "freezer" in getattr(item, "fixturenames", ())


@_pytest_fixture(autouse=True)
def verify_cleanup(
    expected_lingering_tasks: bool,
    expected_lingering_timers: bool,
) -> _Generator[None]:
    """Override verify_cleanup to tolerate ImportExecutor threads.

    The sandbox creates a host HA instance whose import executor thread
    may still be running when cleanup checks happen.
    """
    import asyncio as _asyncio

    event_loop = _asyncio.get_event_loop()
    threads_before = frozenset(threading.enumerate())
    tasks_before = _asyncio.all_tasks(event_loop)
    yield

    event_loop.run_until_complete(event_loop.shutdown_default_executor())

    from tests.common import INSTANCES

    if len(INSTANCES) >= 2:
        count = len(INSTANCES)
        for inst in INSTANCES:
            inst.stop()
        import pytest as _pytest
        _pytest.exit(
            f"Detected non stopped instances ({count}), aborting test run"
        )

    tasks = _asyncio.all_tasks(event_loop) - tasks_before
    for task in tasks:
        if expected_lingering_tasks:
            pass
        else:
            task.cancel()
    if tasks:
        event_loop.run_until_complete(_asyncio.wait(tasks))

    threads = frozenset(threading.enumerate()) - threads_before
    for thread in threads:
        if thread.name.startswith("ImportExecutor"):
            thread.join(timeout=5)
            continue
        assert (
            isinstance(thread, threading._DummyThread)
            or thread.name.startswith("waitpid-")
            or "_run_safe_shutdown_loop" in thread.name
        )


def pytest_runtest_teardown(item, nextitem) -> None:
    """Clear per-test flag."""
    _state.uses_freezer = False


def pytest_configure() -> None:
    """Patch async_test_home_assistant to boot a real sandbox websocket server."""
    from contextlib import asynccontextmanager
    from unittest.mock import patch

    from aiohttp.test_utils import TestServer

    import hass_client.testing.pytest_plugin as base_plugin

    base_plugin.pytest_configure()

    from homeassistant.components.sandbox import async_setup as sandbox_async_setup
    from homeassistant.components.sandbox.const import (
        DATA_SANDBOX,
        DOMAIN as SANDBOX_DOMAIN,
    )
    from homeassistant.setup import async_setup_component

    from hass_client.api import HomeAssistantAPI
    from hass_client.config import RemoteConfig
    from hass_client.runtime import RemoteHomeAssistant

    import tests.conftest as tests_conftest
    import tests.common as tests_common
    from tests.common import MockConfigEntry

    if getattr(tests_common, "_sandbox_ws_patched", False):
        return

    patched_async_test_home_assistant = tests_common.async_test_home_assistant

    import socket as _socket_mod

    _real_socket = _socket_mod.socket

    @asynccontextmanager
    async def sandbox_async_test_home_assistant(*args, **kwargs):
        """Create a sandbox-connected test HA instance with a real websocket.

        Falls back to the base plugin (no websocket) when the test uses the
        freezer fixture, since freezer.move_to() hangs live connections.
        """
        if getattr(_state, "uses_freezer", False):
            async with patched_async_test_home_assistant(*args, **kwargs) as hass:
                yield hass
            return

        saved_socket = _socket_mod.socket
        _socket_mod.socket = _real_socket

        try:
            async with patched_async_test_home_assistant(*args, **kwargs) as host_hass:
                await async_setup_component(host_hass, "websocket_api", {})
                await sandbox_async_setup(host_hass, {})

                server = TestServer(host_hass.http.app)
                await server.start_server()

                ws_url = f"ws://127.0.0.1:{server.port}/api/websocket"

                sandbox_entry = MockConfigEntry(
                    domain=SANDBOX_DOMAIN,
                    data={
                        "entries": [
                            {
                                "entry_id": "sandbox_test",
                                "domain": "input_boolean",
                                "title": "Sandbox Test",
                                "data": {},
                            }
                        ]
                    },
                )
                sandbox_entry.add_to_hass(host_hass)

                with patch(
                    "homeassistant.components.sandbox._spawn_sandbox",
                    return_value=None,
                ):
                    await host_hass.config_entries.async_setup(
                        sandbox_entry.entry_id
                    )

                sandbox_data = host_hass.data[DATA_SANDBOX]
                instance = sandbox_data.sandboxes[sandbox_entry.entry_id]
                access_token = instance.access_token

                async with patched_async_test_home_assistant(
                    *args, **kwargs
                ) as sandbox_hass:
                    sandbox_hass.remote_config = RemoteConfig(
                        websocket_url=ws_url,
                        token=access_token,
                        ssl=False,
                        sync_states=False,
                        sync_entity_registry=False,
                    )
                    sandbox_api = HomeAssistantAPI(
                        websocket_url=ws_url,
                        token=access_token,
                    )
                    sandbox_hass.remote_api = sandbox_api

                    from hass_client.sandbox_service_registry import (
                        SandboxServiceRegistry,
                    )

                    sandbox_svc_registry = SandboxServiceRegistry(
                        sandbox_hass, sandbox_api
                    )
                    sandbox_hass.services = sandbox_svc_registry
                    await sandbox_hass.async_setup_remote()

                    async def _on_command(message):
                        """Handle commands forwarded from host."""
                        event_data = message.get("event", {})
                        cmd_type = event_data.get("type")
                        if cmd_type == "call_service":
                            call_id = event_data.get("call_id")
                            domain = event_data.get("domain", "")
                            service = event_data.get("service", "")
                            service_data = event_data.get("service_data", {})
                            target = event_data.get("target")
                            return_response = event_data.get(
                                "return_response", False
                            )
                            context_data = event_data.get("context")
                            try:
                                result = (
                                    await sandbox_svc_registry.async_execute_forwarded_call(
                                        domain, service, service_data,
                                        target=target,
                                        return_response=return_response,
                                        context_data=context_data,
                                    )
                                )
                                await sandbox_api.async_sandbox_service_call_result(
                                    call_id=call_id,
                                    success=True,
                                    result=result,
                                )
                            except Exception as err:
                                kwargs = {
                                    "call_id": call_id,
                                    "success": False,
                                    "error": str(err),
                                    "error_type": type(err).__name__,
                                }
                                if hasattr(err, "translation_domain") and err.translation_domain:
                                    kwargs["translation_domain"] = err.translation_domain
                                if hasattr(err, "translation_key") and err.translation_key:
                                    kwargs["translation_key"] = err.translation_key
                                if hasattr(err, "translation_placeholders") and err.translation_placeholders:
                                    kwargs["translation_placeholders"] = err.translation_placeholders
                                await sandbox_api.async_sandbox_service_call_result(
                                    **kwargs
                                )

                    await sandbox_api.subscribe(
                        _on_command,
                        "sandbox/subscribe_entity_commands",
                    )

                    try:
                        yield sandbox_hass
                    finally:
                        await sandbox_hass.async_teardown_remote()
                        await server.close()
                        await host_hass.async_stop(force=True)
                        # Clear the shutdown flag so pytest-asyncio can
                        # still finalize fixtures on the shared loop.
                        with suppress(AttributeError):
                            delattr(
                                host_hass.loop,
                                "_shutdown_run_callback_threadsafe",
                            )
        finally:
            _socket_mod.socket = saved_socket

    tests_common.async_test_home_assistant = sandbox_async_test_home_assistant
    tests_conftest.async_test_home_assistant = sandbox_async_test_home_assistant
    tests_common._sandbox_ws_patched = True
