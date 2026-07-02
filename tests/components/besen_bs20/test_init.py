"""Tests for integration setup and unload."""

from types import SimpleNamespace
from typing import Any, cast

from besen_bs20 import client as client_module
from besen_bs20.exceptions import CannotConnect, InvalidAuth
from bleak.backends.device import BLEDevice
import pytest

from homeassistant.components import bluetooth
from homeassistant.components.besen_bs20 import (
    BesenBS20ConfigEntry,
    async_setup_entry,
    async_unload_entry,
    coordinator as coordinator_module,
    repairs,
)
from homeassistant.components.besen_bs20.const import CONF_SYNC_CLOCK, PLATFORMS
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PIN
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady


class _FakeConfigEntries:
    """Fake Home Assistant config entries manager."""

    def __init__(self, *, unload_ok: bool = True) -> None:
        """Initialize the manager."""

        self.unload_ok = unload_ok
        self.forwarded: list[tuple[object, list[str]]] = []
        self.unloaded: list[tuple[object, list[str]]] = []

    async def async_forward_entry_setups(
        self,
        entry: object,
        platforms: list[str],
    ) -> None:
        """Record forwarded platforms."""

        self.forwarded.append((entry, platforms))

    async def async_unload_platforms(
        self,
        entry: object,
        platforms: list[str],
    ) -> bool:
        """Record unloaded platforms."""

        self.unloaded.append((entry, platforms))
        return self.unload_ok


class _FakeClient:
    """Fake Besen client."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the fake client."""

        self.args = args
        self.kwargs = kwargs


class _FakeCoordinator:
    """Fake coordinator."""

    next_error: Exception | None = None

    def __init__(self, hass: object, client: _FakeClient) -> None:
        """Initialize the fake coordinator."""

        del hass
        self.client = client
        self.started = False
        self.shutdown = False

    async def async_start(self) -> None:
        """Start or raise configured error."""

        if self.next_error is not None:
            raise self.next_error
        self.started = True

    async def async_shutdown(self) -> None:
        """Record shutdown."""

        self.shutdown = True


def _entry() -> BesenBS20ConfigEntry:
    """Return a fake config entry."""

    return cast(
        BesenBS20ConfigEntry,
        SimpleNamespace(
            entry_id="entry",
            data={
                CONF_ADDRESS: "AA:BB",
                CONF_NAME: "ACP#Garage",
                CONF_PIN: "123456",
            },
            options={CONF_SYNC_CLOCK: False},
            runtime_data=None,
        ),
    )


def _hass(*, unload_ok: bool = True) -> SimpleNamespace:
    """Return a fake hass object."""

    return SimpleNamespace(config_entries=_FakeConfigEntries(unload_ok=unload_ok))


def _bluetooth_module() -> Any:
    """Return the runtime Bluetooth module used by setup."""

    return bluetooth


def _patch_setup_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    ble_device: object | None = None,
) -> list[tuple[str, str]]:
    """Patch setup dependencies and return repair calls."""

    repair_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(client_module, "BesenBS20Client", _FakeClient)
    monkeypatch.setattr(coordinator_module, "BesenBS20Coordinator", _FakeCoordinator)
    monkeypatch.setattr(
        _bluetooth_module(),
        "async_ble_device_from_address",
        lambda *args, **kwargs: cast(BLEDevice, ble_device)
        if ble_device is not None
        else None,
    )
    monkeypatch.setattr(
        _bluetooth_module(),
        "async_address_reachability_diagnostics",
        lambda *args, **kwargs: "diagnostic reason",
        raising=False,
    )
    monkeypatch.setattr(
        _bluetooth_module(),
        "BluetoothReachabilityIntent",
        SimpleNamespace(CONNECTION="connection"),
        raising=False,
    )
    monkeypatch.setattr(
        repairs,
        "async_create_no_connectable_path_issue",
        lambda hass, entry_id: repair_calls.append(("create_path", entry_id)),
    )
    monkeypatch.setattr(
        repairs,
        "async_delete_no_connectable_path_issue",
        lambda hass, entry_id: repair_calls.append(("delete_path", entry_id)),
    )
    monkeypatch.setattr(
        repairs,
        "async_create_reauth_issue",
        lambda hass, entry_id: repair_calls.append(("create_reauth", entry_id)),
    )
    monkeypatch.setattr(
        repairs,
        "async_delete_reauth_issue",
        lambda hass, entry_id: repair_calls.append(("delete_reauth", entry_id)),
    )
    return repair_calls


@pytest.mark.asyncio
async def test_setup_entry_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setup creates runtime data and forwards platforms."""

    _FakeCoordinator.next_error = None
    repairs_called = _patch_setup_dependencies(monkeypatch, ble_device=object())
    hass = _hass()
    entry = _entry()

    result = await async_setup_entry(cast(Any, hass), entry)
    runtime_data = cast(Any, entry).runtime_data
    client = cast(_FakeClient, runtime_data.client)
    coordinator = cast(_FakeCoordinator, runtime_data.coordinator)

    assert result is True
    assert client.kwargs["address"] == "AA:BB"
    assert client.kwargs["sync_clock"] is False
    assert coordinator.started is True
    assert hass.config_entries.forwarded == [(entry, PLATFORMS)]
    assert repairs_called == [("delete_path", "entry"), ("delete_reauth", "entry")]


@pytest.mark.asyncio
async def test_setup_entry_no_connectable_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setup raises not ready when no active Bluetooth path exists."""

    repairs_called = _patch_setup_dependencies(monkeypatch)

    with pytest.raises(ConfigEntryNotReady, match="diagnostic reason"):
        await async_setup_entry(cast(Any, _hass()), _entry())

    assert repairs_called == [("create_path", "entry")]


@pytest.mark.asyncio
async def test_setup_entry_auth_and_connect_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setup maps coordinator auth/connect errors to config-entry errors."""

    _patch_setup_dependencies(monkeypatch, ble_device=object())
    _FakeCoordinator.next_error = InvalidAuth("bad pin")
    with pytest.raises(ConfigEntryAuthFailed):
        await async_setup_entry(cast(Any, _hass()), _entry())

    _FakeCoordinator.next_error = CannotConnect("offline")
    with pytest.raises(ConfigEntryNotReady, match="offline"):
        await async_setup_entry(cast(Any, _hass()), _entry())

    _FakeCoordinator.next_error = None


@pytest.mark.asyncio
async def test_unload_entry_shutdowns_only_when_platforms_unload() -> None:
    """Unload shuts down runtime data only when platforms unload successfully."""

    entry = _entry()
    coordinator = _FakeCoordinator(object(), _FakeClient())
    cast(Any, entry).runtime_data = SimpleNamespace(coordinator=coordinator)

    assert await async_unload_entry(cast(Any, _hass()), entry) is True
    assert coordinator.shutdown is True

    coordinator.shutdown = False
    assert await async_unload_entry(cast(Any, _hass(unload_ok=False)), entry) is False
    assert coordinator.shutdown is False
