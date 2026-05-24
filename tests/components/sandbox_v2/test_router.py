"""Tests for :class:`SandboxFlowRouter` — classification + setup interception."""

from typing import cast

import pytest

from homeassistant.components.sandbox_v2.manager import SandboxManager
from homeassistant.components.sandbox_v2.proxy_flow import SandboxFlowProxy
from homeassistant.components.sandbox_v2.router import SandboxFlowRouter
from homeassistant.config_entries import SOURCE_USER, ConfigEntry, ConfigFlowContext
from homeassistant.core import HomeAssistant

from ._helpers import FakeSandboxManager, make_channel_pair

from tests.common import MockConfigEntry, MockModule, mock_integration


@pytest.fixture(name="manager")
def _manager_fixture(hass: HomeAssistant) -> FakeSandboxManager:
    """A fake sandbox manager that never spawns a subprocess."""
    return FakeSandboxManager()


async def test_async_create_flow_returns_none_for_system_domain(
    hass: HomeAssistant, manager: FakeSandboxManager
) -> None:
    """System integrations stay on main — router returns None."""
    mock_integration(
        hass,
        MockModule("test_system", partial_manifest={"integration_type": "system"}),
    )
    router = SandboxFlowRouter(hass, cast(SandboxManager, manager))

    flow = await router.async_create_flow(
        "test_system",
        context=ConfigFlowContext(source=SOURCE_USER),
        data=None,
    )

    assert flow is None


async def test_async_create_flow_returns_proxy_for_builtin(
    hass: HomeAssistant, manager: FakeSandboxManager
) -> None:
    """A built-in integration not in ALWAYS_MAIN gets a SandboxFlowProxy."""
    mock_integration(hass, MockModule("test_builtin"))
    router = SandboxFlowRouter(hass, cast(SandboxManager, manager))

    flow = await router.async_create_flow(
        "test_builtin",
        context=ConfigFlowContext(source=SOURCE_USER),
        data=None,
    )

    assert isinstance(flow, SandboxFlowProxy)


async def test_async_create_flow_reuses_group_of_existing_entry(
    hass: HomeAssistant, manager: FakeSandboxManager
) -> None:
    """A second flow for a domain already routed to a sandbox reuses it."""
    mock_integration(hass, MockModule("test_reuse"))
    existing = MockConfigEntry(
        domain="test_reuse",
        sandbox="built-in",
    )
    existing.add_to_hass(hass)

    router = SandboxFlowRouter(hass, cast(SandboxManager, manager))
    flow = await router.async_create_flow(
        "test_reuse",
        context=ConfigFlowContext(source=SOURCE_USER),
        data=None,
    )

    assert isinstance(flow, SandboxFlowProxy)
    # The proxy carries the same group as the existing entry.
    assert flow._sandbox_group == "built-in"


async def test_async_create_flow_returns_none_when_classified_main(
    hass: HomeAssistant, manager: FakeSandboxManager
) -> None:
    """ALWAYS_MAIN domains go to main — router returns None."""
    mock_integration(hass, MockModule("automation"))
    router = SandboxFlowRouter(hass, cast(SandboxManager, manager))

    flow = await router.async_create_flow(
        "automation",
        context=ConfigFlowContext(source=SOURCE_USER),
        data=None,
    )

    assert flow is None


async def test_async_setup_entry_routes_to_sandbox(
    hass: HomeAssistant, manager: FakeSandboxManager
) -> None:
    """Entries carrying ``sandbox`` are routed to the manager.

    The sandbox-side runtime replies to ``sandbox_v2/entry_setup`` via a
    stub on channel_b; the router rolls that response into the
    main-side entry state.
    """
    channel_a, channel_b = make_channel_pair()
    received: list[dict[str, object]] = []

    async def _entry_setup(payload: dict[str, object]) -> dict[str, object]:
        received.append(payload)
        return {"ok": True}

    channel_b.register("sandbox_v2/entry_setup", _entry_setup)
    channel_a.start()
    channel_b.start()
    manager.install("built-in", channel_a)

    entry = MockConfigEntry(
        domain="test_entry",
        title="Test",
        sandbox="built-in",
    )
    router = SandboxFlowRouter(hass, cast(SandboxManager, manager))

    try:
        result = await router.async_setup_entry(cast(ConfigEntry, entry))
    finally:
        await channel_a.close()
        await channel_b.close()

    assert result is True
    assert manager.start_calls == ["built-in"]
    assert len(received) == 1
    assert received[0]["domain"] == "test_entry"
    assert received[0]["title"] == "Test"
    # Sandbox group is carried as a first-class ConfigEntry field now;
    # entry.data on the wire is exactly what the integration sees.
    assert received[0]["data"] == {}


async def test_async_setup_entry_marks_setup_error_on_failure(
    hass: HomeAssistant, manager: FakeSandboxManager
) -> None:
    """A sandbox refusing entry_setup propagates as SETUP_ERROR."""
    channel_a, channel_b = make_channel_pair()

    async def _entry_setup(_payload: dict[str, object]) -> dict[str, object]:
        return {"ok": False, "reason": "boom"}

    channel_b.register("sandbox_v2/entry_setup", _entry_setup)
    channel_a.start()
    channel_b.start()
    manager.install("built-in", channel_a)

    entry = MockConfigEntry(
        domain="test_fail",
        title="Test",
        sandbox="built-in",
    )
    entry.add_to_hass(hass)
    router = SandboxFlowRouter(hass, cast(SandboxManager, manager))

    try:
        result = await router.async_setup_entry(cast(ConfigEntry, entry))
    finally:
        await channel_a.close()
        await channel_b.close()

    assert result is False
    assert entry.reason == "boom"


async def test_async_setup_entry_returns_none_when_not_sandboxed(
    hass: HomeAssistant, manager: FakeSandboxManager
) -> None:
    """Entries without ``sandbox`` set are left to the default setup path."""
    entry = MockConfigEntry(domain="test_plain", data={"some": "value"})
    router = SandboxFlowRouter(hass, cast(SandboxManager, manager))

    result = await router.async_setup_entry(cast(ConfigEntry, entry))

    assert result is None
    assert manager.start_calls == []
