"""Pytest fixtures and shared setup for the Greencell integration."""

import asyncio
from collections.abc import Callable
import json
from types import SimpleNamespace

import pytest

from homeassistant.components import mqtt
from homeassistant.components.greencell import (
    CONF_SERIAL_NUMBER,
    DOMAIN,
    GREENCELL_DISC_TOPIC,
)
from homeassistant.components.greencell.const import (
    GREENCELL_ACCESS_KEY,
    GREENCELL_CURRENT_DATA_KEY,
    GREENCELL_POWER_DATA_KEY,
    GREENCELL_STATE_DATA_KEY,
    GREENCELL_VOLTAGE_DATA_KEY,
)
from homeassistant.components.mqtt import DATA_MQTT

TEST_SERIAL_NUMBER = "EVGC021A2275XXXXXXXXXX"


# --- Stub data/access classes for sensors/tests ---
class DummyAccess:
    """Simulates GreencellAccess with minimal functionality for tests."""

    def __init__(self) -> None:
        """Initialize with default state."""
        self._disabled = False
        self._listeners: list[callable] = []

    def is_disabled(self) -> bool:
        """Return whether the access is disabled."""
        return self._disabled

    def update(self, state: str) -> None:
        """Simulate state update; notify listeners if state changes."""
        self._disabled = state == "OFFLINE"

    def on_msg(self, payload: bytes) -> None:
        """Simulate receiving a message; notify listeners."""
        self._disabled = False

    def register_listener(self, callback_fn: callable) -> None:
        """Register a listener callback."""
        self._listeners.append(callback_fn)


class Dummy3PhaseData:
    """Simulates 3-phase data with get_value method."""

    def __init__(self, values: dict[str, float]) -> None:
        """Initialize with a dictionary of phase values."""
        self._values = values

    def get_value(self, phase: str) -> float | None:
        """Return the value for the specified phase, or None if not available."""
        return self._values.get(phase)


class DummySingleData:
    """Simulates single-phase data with a data attribute."""

    def __init__(self, data: float | None = None) -> None:
        """Initialize with optional data value."""
        self.data = data


# --- Fake infrastructure for tests ---
class DummyMessage:
    """Simulates an MQTT message with a payload attribute."""

    def __init__(self, payload: str) -> None:
        """Initialize the dummy message with a JSON payload."""
        self.payload = payload


class DummyServices:
    """Simulates Home Assistant services for testing."""

    def __init__(self) -> None:
        """Initialize the dummy services."""
        self.calls = []

    def async_call(self, domain, service, service_data) -> None:
        """Simulate a service call by appending to calls list."""
        self.calls.append((domain, service, service_data))


class DummyConfigEntry:
    """Simulates a ConfigEntry holding a serial_number."""

    def __init__(
        self, serial_number: str = TEST_SERIAL_NUMBER, entry_id: str = "test_entry"
    ) -> None:
        """Initialize the dummy ConfigEntry."""
        self.data = {CONF_SERIAL_NUMBER: serial_number}
        self.entry_id = entry_id


class DummyHass:
    """Minimal HomeAssistant stub: config_entries, services, task creation."""

    def __init__(self, entries=None) -> None:
        """Initialize the dummy HomeAssistant instance."""

        # stubbing config_entries.async_entries(...)
        self.config_entries = SimpleNamespace(
            async_entries=lambda domain: entries or [],
            flow=SimpleNamespace(
                async_progress_by_handler=lambda handler,
                *,
                include_uninitialized,
                match_context: []
            ),
        )
        self.data: dict = {}
        self.services = DummyServices()
        self.published: list = []
        self.subscriptions: dict[str, Callable] = {}

    def async_create_task(self, task):
        """Stub for async_create_task to capture tasks."""
        if asyncio.iscoroutine(task):
            asyncio.get_event_loop().create_task(task)

    def subscribed_topics(self):
        """Return a list of all subscribed topics."""
        return list(self.subscriptions.keys())


class ExpectedCallGenerator:
    """Generates expected service call tuples for verification."""

    @staticmethod
    def generate(domain, service, topic, payload, retain=False):
        """Generate a service call tuple, with correct payload string."""
        # If payload is already a JSON string, use as-is; otherwise dump it
        if isinstance(payload, str):
            payload_str = payload
        else:
            payload_str = json.dumps(payload)
        return (
            domain,
            service,
            {
                "topic": topic,
                "payload": payload_str,
                "retain": retain,
            },
        )

    @staticmethod
    def generate_mqtt_publish_cmd(
        payload: dict, device_id: str = TEST_SERIAL_NUMBER
    ) -> tuple[str, str, dict]:
        """Generate expected MQTT publish call tuple."""
        return ExpectedCallGenerator.generate(
            "mqtt", "publish", f"/greencell/evse/{device_id}/cmd", payload, retain=False
        )


@pytest.fixture(autouse=True)
def stub_async_create_task(monkeypatch: pytest.MonkeyPatch):
    """Stub DummyHass.async_create_task to capture tasks for verification."""

    # Capture list of scheduled tasks
    scheduled_tasks: list = []

    # Fake create_task method
    def fake_create_task(self, task):
        scheduled_tasks.append(task)
        # Optionally, run immediately or schedule normally
        if asyncio.iscoroutine(task):
            asyncio.get_event_loop().create_task(task)

    # Patch the DummyHass method
    monkeypatch.setattr(DummyHass, "async_create_task", fake_create_task)
    return scheduled_tasks


# --- MQTT subscribe stub fixture ---
@pytest.fixture(autouse=True)
def stub_subscribe(monkeypatch: pytest.MonkeyPatch):
    """Automatically stub async_subscribe to capture subscriptions."""
    subs = []

    async def fake_subscribe(hass, topic, callback):
        subs.append((topic, callback))
        return lambda: None

    # Patch the exact symbol imported by the integration
    monkeypatch.setattr(
        "homeassistant.components.greencell.async_subscribe",
        fake_subscribe,
    )
    return subs


# --- stomp publish stub for config_flow tests ---
@pytest.fixture(autouse=True)
def stub_mqtt_and_publish(monkeypatch: pytest.MonkeyPatch):
    """Stub both async_subscribe and async_publish for config_flow tests."""
    callbacks = {}

    # subscribe stub
    async def fake_subscribe(hass, topic, callback):
        """Simulate async_subscribe by storing the callback."""
        callbacks[topic] = callback

        if topic == GREENCELL_DISC_TOPIC:
            # fire on next loop iteration
            asyncio.get_event_loop().call_soon(
                callback, DummyMessage(payload=json.dumps({"id": TEST_SERIAL_NUMBER}))
            )
        return lambda: None

    async def fake_publish(hass, topic, payload, qos, retain):
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
def runtime(entry) -> dict:
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
async def hass(entry, runtime):
    """Provides a FakeHass instance for tests."""
    return DummyHass(entries=[])


@pytest.fixture
async def hass_with_runtime(monkeypatch: pytest.MonkeyPatch, entry, runtime):
    """Provides a FakeHass instance for tests."""

    class DummyMqttData:
        """Simulates MQTT data with a client and async_subscribe method."""

        def __init__(self, hass) -> None:
            """Initialize the dummy MQTT data."""

            def async_subscribe(
                topic, callback, qos=None, encoding=None, job_type=None
            ):
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
