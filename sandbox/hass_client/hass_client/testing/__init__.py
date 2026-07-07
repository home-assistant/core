"""Sandbox testing infrastructure.

Two pytest plugins for exercising the sandbox bridge against HA Core
integration tests:

* :mod:`hass_client.testing.pytest_plugin` — fast in-process lane. Runs
  the sandbox-side :class:`hass_client.sandbox.SandboxRuntime` as an
  asyncio task in the test event loop, joined to the manager-side
  :class:`Channel` by an in-memory loopback transport. No subprocess
  spawn, no live socket.
* :mod:`hass_client.testing.conftest_sandbox` — real-subprocess lane.
  Lets the manager spawn ``python -m hass_client.sandbox`` exactly as
  production does. Tests that use the ``freezer`` fixture must be marked
  with ``@pytest.mark.no_sandbox_freezer`` so they auto-skip — freezer
  cannot move time inside the subprocess and the channel will hang.

Both plugins share the helper module :mod:`hass_client.testing._inproc`
for the in-memory transport pieces.
"""
