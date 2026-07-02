"""Tests for the Besen BS20 coordinator."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from besen_bs20.exceptions import CommandFailed
from besen_bs20.models import BesenBS20Data, ChargerInfo
import pytest

from homeassistant.components.besen_bs20.const import DOMAIN
from homeassistant.components.besen_bs20.coordinator import BesenBS20Coordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


class _FakeClient:
    """Fake client used by coordinator tests."""

    def __init__(self) -> None:
        """Initialize the fake client."""

        self.address = "AA:BB"
        self.state = BesenBS20Data(info=ChargerInfo(address=self.address))
        self.calls: list[str] = []
        self.listener: Callable[[BesenBS20Data], None] | None = None
        self.removed = False
        self.fail_next_command = False
        self.fail_start = False

    def add_listener(
        self,
        listener: Callable[[BesenBS20Data], None],
    ) -> Callable[[], None]:
        """Record a listener."""

        self.listener = listener

        def _remove() -> None:
            self.removed = True

        return _remove

    async def async_start(self) -> None:
        """Record start."""

        if self.fail_start:
            raise RuntimeError("failed start")
        self.calls.append("start")

    async def async_stop(self) -> None:
        """Record stop."""

        self.calls.append("stop")

    def _maybe_fail_command(self) -> None:
        """Raise the next requested command failure."""

        if self.fail_next_command:
            self.fail_next_command = False
            raise CommandFailed("failed")

    async def async_start_charging(self) -> None:
        """Record start charging."""

        self._maybe_fail_command()
        self.calls.append("start_charging")

    async def async_stop_charging(self) -> None:
        """Record stop charging."""

        self._maybe_fail_command()
        self.calls.append("stop_charging")


async def test_coordinator_lifecycle_and_updates(hass: HomeAssistant) -> None:
    """Coordinator starts, handles updates, refreshes, and shuts down."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    client = _FakeClient()
    coordinator = BesenBS20Coordinator(hass, entry, cast(Any, client))

    await coordinator.async_start()
    new_state = BesenBS20Data(
        info=ChargerInfo(address="AA:BB", model="BS20"),
        available=True,
    )
    assert client.listener is not None
    client.listener(new_state)
    client.state = BesenBS20Data(
        info=ChargerInfo(address="AA:BB", model="BS20-revised"),
        available=True,
    )
    await coordinator.async_request_refresh()
    await coordinator.async_shutdown()

    assert coordinator.config_entry is entry
    assert coordinator.data == client.state


async def test_coordinator_start_failure_cleans_up(hass: HomeAssistant) -> None:
    """Coordinator cleans up the listener and client when start fails."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    client = _FakeClient()
    client.fail_start = True
    coordinator = BesenBS20Coordinator(hass, entry, cast(Any, client))

    with pytest.raises(RuntimeError):
        await coordinator.async_start()

    assert client.removed is True
    assert client.calls == ["stop"]


async def test_coordinator_commands_and_failures(hass: HomeAssistant) -> None:
    """Coordinator delegates commands and refreshes state on command failures."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    client = _FakeClient()
    coordinator = BesenBS20Coordinator(hass, entry, cast(Any, client))

    await coordinator.async_start_charging()
    await coordinator.async_stop_charging()

    assert client.calls == ["start_charging", "stop_charging"]

    client.fail_next_command = True
    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_start_charging()

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "command_failed"
    assert coordinator.data == client.state
