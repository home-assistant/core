"""Tests for integration setup and unload."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar, cast

from besen_bs20.exceptions import CannotConnect, InvalidAuth
from besen_bs20.models import BesenBS20Data, ChargerConfig, ChargerInfo, ChargeStatus
import pytest

from homeassistant.components import besen_bs20 as integration_module, bluetooth
from homeassistant.components.besen_bs20.const import CONF_SYNC_CLOCK, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry

_DEFAULT_BLE_DEVICE = object()


def _state() -> BesenBS20Data:
    """Return a populated available charger state."""

    return BesenBS20Data(
        info=ChargerInfo(
            address="AA:BB",
            serial="SERIAL",
            phases=1,
            manufacturer="Besen",
            model="BS20",
            hardware_version="HW1",
            software_version="SW1",
        ),
        config=ChargerConfig(device_name="Garage", rssi=-55),
        charge=ChargeStatus(
            charger_status=True,
            current_energy=3500,
            total_energy=1.2,
            current_amount=12.3,
            inner_temp_c=24.5,
        ),
        available=True,
        authenticated=True,
    )


class _FakeClient:
    """Fake Besen client."""

    instances: ClassVar[list[_FakeClient]] = []
    next_error: ClassVar[Exception | None] = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the fake client."""

        self.args = args
        self.kwargs = kwargs
        self.address = kwargs["address"]
        self.state = _state()
        self.started = False
        self.stopped = False
        self.removed = False
        self.listener: Callable[[BesenBS20Data], None] | None = None
        self.instances.append(self)

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
        """Start or raise configured error."""

        if self.next_error is not None:
            raise self.next_error
        self.started = True

    async def async_stop(self) -> None:
        """Record shutdown."""

        self.stopped = True


def _entry() -> MockConfigEntry:
    """Return a config entry."""

    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB",
            CONF_NAME: "ACP#Garage",
            CONF_PIN: "123456",
        },
        options={CONF_SYNC_CLOCK: False},
        title="Garage",
        unique_id="AA:BB",
    )


def _assert_entry_state(entry: MockConfigEntry, state: ConfigEntryState) -> None:
    """Assert a config entry state without narrowing later assertions."""

    assert entry.state is state


def _patch_setup_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    ble_device: object | None = _DEFAULT_BLE_DEVICE,
    start_error: Exception | None = None,
) -> None:
    """Patch setup dependencies."""

    _FakeClient.instances = []
    _FakeClient.next_error = start_error
    monkeypatch.setattr(integration_module, "BesenBS20Client", _FakeClient)
    monkeypatch.setattr(
        bluetooth,
        "async_ble_device_from_address",
        lambda *args, **kwargs: ble_device,
    )
    monkeypatch.setattr(
        bluetooth,
        "async_address_reachability_diagnostics",
        lambda *args, **kwargs: "diagnostic reason",
    )


async def test_setup_entry_success(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setup creates runtime data and forwards the switch platform."""

    entry = _entry()
    entry.add_to_hass(hass)
    _patch_setup_dependencies(monkeypatch)

    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()

    client = _FakeClient.instances[0]
    _assert_entry_state(entry, ConfigEntryState.LOADED)
    assert cast(Any, entry.runtime_data).client is client
    assert client.kwargs["address"] == "AA:BB"
    assert client.kwargs["sync_clock"] is False
    assert client.started is True
    assert hass.states.get("switch.garage_charge") is not None

    assert await hass.config_entries.async_unload(entry.entry_id) is True
    await hass.async_block_till_done()

    _assert_entry_state(entry, ConfigEntryState.NOT_LOADED)
    assert client.removed is True
    assert client.stopped is True


async def test_setup_entry_no_connectable_path(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setup retries and creates a repair issue when no active path exists."""

    entry = _entry()
    entry.add_to_hass(hass)
    _patch_setup_dependencies(monkeypatch, ble_device=None)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    _assert_entry_state(entry, ConfigEntryState.SETUP_RETRY)
    assert issue_registry.async_get_issue(
        DOMAIN,
        f"{entry.entry_id}_no_connectable_path",
    )


async def test_setup_entry_auth_error_starts_reauth(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setup maps invalid auth to a config-entry auth failure."""

    entry = _entry()
    entry.add_to_hass(hass)
    _patch_setup_dependencies(monkeypatch, start_error=InvalidAuth("bad pin"))

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    _assert_entry_state(entry, ConfigEntryState.SETUP_ERROR)


async def test_setup_entry_connect_error_retries(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setup maps connection errors to a retry."""

    entry = _entry()
    entry.add_to_hass(hass)
    _patch_setup_dependencies(monkeypatch, start_error=CannotConnect("offline"))

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    _assert_entry_state(entry, ConfigEntryState.SETUP_RETRY)


async def test_unload_skips_shutdown_when_platform_unload_fails(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unload does not stop the client when platform unload fails."""

    entry = _entry()
    entry.add_to_hass(hass)
    _patch_setup_dependencies(monkeypatch)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    client = _FakeClient.instances[0]

    async def _async_unload_platforms(*args: Any, **kwargs: Any) -> bool:
        """Return a failed platform unload."""

        return False

    monkeypatch.setattr(
        hass.config_entries,
        "async_unload_platforms",
        _async_unload_platforms,
    )

    assert await hass.config_entries.async_unload(entry.entry_id) is False

    assert client.stopped is False
