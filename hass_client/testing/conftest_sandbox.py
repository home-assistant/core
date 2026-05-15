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

import threading

_state = threading.local()


def pytest_runtest_setup(item) -> None:
    """Detect tests that use the freezer fixture before hass setup runs."""
    _state.uses_freezer = "freezer" in getattr(item, "fixturenames", ())


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
                    if host_hass in tests_common.INSTANCES:
                        tests_common.INSTANCES.remove(host_hass)

                    host_hass.import_executor.shutdown(wait=False)

                    sandbox_hass.remote_config = RemoteConfig(
                        websocket_url=ws_url,
                        token=access_token,
                        ssl=False,
                        sync_states=False,
                        sync_entity_registry=False,
                        sync_remote_services=True,
                    )
                    sandbox_hass.remote_api = HomeAssistantAPI(
                        websocket_url=ws_url,
                        token=access_token,
                    )
                    await sandbox_hass.async_setup_remote()

                    try:
                        yield sandbox_hass
                    finally:
                        await sandbox_hass.async_teardown_remote()
                        await server.close()
        finally:
            _socket_mod.socket = saved_socket

    tests_common.async_test_home_assistant = sandbox_async_test_home_assistant
    tests_conftest.async_test_home_assistant = sandbox_async_test_home_assistant
    tests_common._sandbox_ws_patched = True
