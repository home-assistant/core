"""Pytest fixtures and shared setup for the Greencell integration."""

import asyncio
from collections.abc import Callable, Coroutine
import json
from types import SimpleNamespace
from typing import Any

import pytest

from homeassistant.components import mqtt
from homeassistant.components.greencell.const import (
    CONF_SERIAL_NUMBER,
    DOMAIN,
    GREENCELL_ACCESS_KEY,
    GREENCELL_CURRENT_DATA_KEY,
    GREENCELL_DISC_TOPIC,
    GREENCELL_POWER_DATA_KEY,
    GREENCELL_STATE_DATA_KEY,
    GREENCELL_VOLTAGE_DATA_KEY,
)
from homeassistant.components.mqtt import DATA_MQTT
from homeassistant.core import HomeAssistant

TEST_SERIAL_NUMBER = "EVGC021A2275XXXXXXXXXX"


# --- Stub data/access classes for sensors/tests ---
class DummyAccess:
    """Simulates GreencellAccess with minimal functionality for tests."""

    def __init__(self) -> None:
        """Initialize with default state."""
        self._disabled: bool = False
        self._listeners: list[Callable[[], None]] = []

    def is_disabled(self) -> bool:
        """Return whether the access is disabled."""
        return self._disabled

    def update(self, state: str) -> None:
        """Simulate state update; notify listeners if state changes."""
        self._disabled = state == "OFFLINE"

    def on_msg(self, payload: bytes) -> None:
        """Simulate receiving a message; notify listeners."""
        self._disabled = False

    def register_listener(self, callback_fn: Callable[[], None]) -> None:
        """Register a listener callback."""
        self._listeners.append(callback_fn)


class Dummy3PhaseData:
    """Simulates 3-phase data with get_value method."""

    def __init__(self, values: dict[str, float]) -> None:
        """Initialize with a dictionary of phase values."""
        self._values: dict[str, float] = values

    def get_value(self, phase: str) -> float | None:
        """Return the value for the specified phase, or None if not available."""
        return self._values.get(phase)


class DummySingleData:
    """Simulates single-phase data with a data attribute."""

    def __init__(self, data: float | str | None = None) -> None:
        """Initialize with optional data value."""
        self.data: float | str | None = data


# --- Fake infrastructure for tests ---
class DummyMessage:
    """Simulates an MQTT message with a payload attribute."""

    def __init__(self, payload: str) -> None:
        """Initialize the dummy message with a JSON payload."""
        self.payload: str = payload


class DummyServices:
    """Simulates Home Assistant services for testing."""

    def __init__(self) -> None:
        """Initialize the dummy services."""
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def async_call(
        self, domain: str, service: str, service_data: dict[str, Any]
    ) -> None:
        """Simulate a service call by appending to calls list."""
        self.calls.append((domain, service, service_data))


class DummyConfigEntry:
    """Simulates a ConfigEntry holding a serial_number."""

    def __init__(
        self, serial_number: str = TEST_SERIAL_NUMBER, entry_id: str = "test_entry"
    ) -> None:
        """Initialize the dummy ConfigEntry."""
        self.data: dict[str, str] = {CONF_SERIAL_NUMBER: serial_number}
        self.entry_id: str = entry_id


class DummyHass:
    """Minimal HomeAssistant stub: config_entries, services, task creation."""

    def __init__(self, entries: list[Any] | None = None) -> None:
        """Initialize the dummy HomeAssistant instance."""

        # stubbing config_entries.async_entries(...)
        self.config_entries = SimpleNamespace(
            async_entries=lambda domain: entries or [],
            async_forward_entry_setups=lambda entry, platforms: None,
            async_unload_platforms=lambda entry, platforms: True,
            flow=SimpleNamespace(
                async_progress_by_handler=lambda handler,
                *,
                include_uninitialized,
                match_context: []
            ),
        )
        self.data: dict[str, Any] = {}
        self.services: DummyServices = DummyServices()
        self.published: list[Any] = []
        self.subscriptions: dict[str, Callable[[Any], None]] = {}

    def async_create_task(self, task: Coroutine[Any, Any, Any] | Any) -> None:
        """Stub for async_create_task to capture tasks."""
        if asyncio.iscoroutine(task):
            asyncio.get_event_loop().create_task(task)

    def subscribed_topics(self) -> list[str]:
        """Return a list of all subscribed topics."""
        return list(self.subscriptions.keys())


@pytest.fixture(autouse=True)
def stub_async_create_task(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Stub DummyHass.async_create_task to capture tasks for verification."""

    scheduled_tasks: list[Any] = []

    def fake_create_task(self: DummyHass, task: Coroutine[Any, Any, Any] | Any) -> None:
        scheduled_tasks.append(task)
        if asyncio.iscoroutine(task):
            asyncio.get_event_loop().create_task(task)

    monkeypatch.setattr(DummyHass, "async_create_task", fake_create_task)
    return scheduled_tasks


# --- MQTT subscribe stub fixture ---
@pytest.fixture(autouse=True)
def stub_subscribe(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Callable]]:
    """Automatically stub async_subscribe to capture subscriptions."""
    subs: list[tuple[str, Callable]] = []

    async def fake_subscribe(
        hass: HomeAssistant, topic: str, callback: Callable
    ) -> Callable[[], None]:
        subs.append((topic, callback))
        return lambda: subs.remove((topic, callback))

    async def fake_wait_for_client(hass_: HomeAssistant) -> bool:
        """Simulate async_wait_for_mqtt_client by returning True. Tests don't need real MQTT client."""
        return True

    async def fake_publish(
        hass: HomeAssistant, topic: str, payload: Any, qos: int, retain: bool
    ) -> None:
        """Simulate async_publish by storing the call."""
        if not hasattr(hass, "published"):
            hass.published = []
        hass.published.append((topic, payload, qos, retain))

    monkeypatch.setattr(
        "homeassistant.components.greencell.async_subscribe",
        fake_subscribe,
    )
    monkeypatch.setattr(
        "homeassistant.components.mqtt.async_wait_for_mqtt_client", fake_wait_for_client
    )
    monkeypatch.setattr("homeassistant.components.mqtt.async_publish", fake_publish)
    return subs


# --- stomp publish stub for config_flow tests ---
@pytest.fixture(autouse=True)
def stub_mqtt_and_publish(monkeypatch: pytest.MonkeyPatch) -> dict[str, Callable]:
    """Stub both async_subscribe and async_publish for config_flow tests."""
    callbacks: dict[str, Callable] = {}

    async def fake_subscribe(
        hass: HomeAssistant, topic: str, callback: Callable[[Any], None]
    ) -> Callable[[], None]:
        """Simulate async_subscribe by storing the callback."""
        callbacks[topic] = callback

        if topic == GREENCELL_DISC_TOPIC:
            asyncio.get_event_loop().call_soon(
                callback, DummyMessage(payload=json.dumps({"id": TEST_SERIAL_NUMBER}))
            )
        return lambda: callbacks.pop(topic, None)

    async def fake_publish(
        hass: HomeAssistant, topic: str, payload: Any, qos: int, retain: bool
    ) -> None:
        """Simulate async_publish by storing the call."""
        if not hasattr(hass, "published"):
            hass.published = []
        hass.published.append((topic, payload, qos, retain))

    monkeypatch.setattr(mqtt, "async_subscribe", fake_subscribe)
    monkeypatch.setattr(mqtt, "async_publish", fake_publish)

    return callbacks


# --- Hass fixture ---
@pytest.fixture
def entry() -> SimpleNamespace:
    """Provides a dummy config entry with a serial number."""
    return SimpleNamespace(
        entry_id="test_entry", data={"serial_number": TEST_SERIAL_NUMBER}
    )


@pytest.fixture
def runtime(entry: SimpleNamespace) -> dict[str, Any]:
    """Provides a runtime dictionary with dummy data for Greencell sensors."""
    access = DummyAccess()
    current = Dummy3PhaseData({"l1": 1000, "l2": None, "l3": 3000})
    voltage = Dummy3PhaseData({"l1": 230.0, "l2": None, "l3": 232.5})
    power = DummySingleData(data=1500.5)
    state = DummySingleData(data="charging")

    return {
        GREENCELL_ACCESS_KEY: access,
        GREENCELL_CURRENT_DATA_KEY: current,
        GREENCELL_VOLTAGE_DATA_KEY: voltage,
        GREENCELL_POWER_DATA_KEY: power,
        GREENCELL_STATE_DATA_KEY: state,
    }


@pytest.fixture
async def hass(entry: SimpleNamespace, runtime: dict[str, Any]) -> DummyHass:
    """Provides a FakeHass instance for tests."""
    return DummyHass(entries=[])


@pytest.fixture
async def hass_with_runtime(
    monkeypatch: pytest.MonkeyPatch, entry: SimpleNamespace, runtime: dict[str, Any]
) -> DummyHass:
    """Provides a FakeHass instance for tests."""

    class DummyMqttData:
        """Simulates MQTT data with a client and async_subscribe method."""

        def __init__(self, hass: HomeAssistant) -> None:
            """Initialize the dummy MQTT data."""

            def async_subscribe(
                topic: str,
                callback: Callable[[Any], None],
                qos: int | None = None,
                encoding: str | None = None,
                job_type: str | None = None,
            ) -> Callable[[], None]:
                """Simulate async_subscribe by storing the callback."""
                hass.subscriptions[topic] = callback
                return lambda: hass.subscriptions.pop(topic, None)

            self.client = SimpleNamespace(
                connected=True, async_subscribe=async_subscribe
            )

    hass = DummyHass(entries=[DummyConfigEntry(entry_id=entry.entry_id)])
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    hass.data[DATA_MQTT] = DummyMqttData(hass)

    return hass
