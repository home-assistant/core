"""Test cases for the Greencell integration in Home Assistant initialization."""

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from homeassistant.components.greencell import (
    DOMAIN,
    async_setup_entry,
    async_unload_entry,
    wait_for_device_ready,
)
from homeassistant.components.greencell.const import (
    CONF_SERIAL_NUMBER,
    DISCOVERY_TIMEOUT,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .conftest import TEST_SERIAL_NUMBER


class DummyConfigEntry:
    """Minimal stub for ConfigEntry."""

    def __init__(
        self, serial: str | None = TEST_SERIAL_NUMBER, entry_id: str = "entry1"
    ) -> None:
        """Initialize the dummy ConfigEntry."""
        self.entry_id = entry_id
        self.data = {CONF_SERIAL_NUMBER: serial} if serial else {}
        self.runtime_data = None


@pytest.mark.asyncio
async def test_wait_for_device_ready_sets_event(
    hass_with_runtime: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that wait_for_device_ready sets the event on first message."""
    subs: list[tuple[str, Callable[[Any], None]]] = []

    async def fake_subscribe(
        hass: HomeAssistant, topic: str, callback: Callable[[Any], None]
    ) -> Callable[[], None]:
        subs.append((topic, callback))
        return lambda: subs.remove((topic, callback))

    monkeypatch.setattr(
        "homeassistant.components.greencell.async_subscribe",
        fake_subscribe,
        raising=True,
    )

    unsub, event = wait_for_device_ready(
        hass_with_runtime, TEST_SERIAL_NUMBER, DISCOVERY_TIMEOUT
    )

    await asyncio.sleep(0)

    assert subs, "No subscriptions were registered by wait_for_device_ready()"

    for _, cb in subs:
        cb("dummy-message")
        break

    await asyncio.sleep(0)
    assert event.is_set(), "Event was not set after invoking the subscribed callback"

    unsub()


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test successful setup of Greencell entry with runtime data."""
    entry = DummyConfigEntry()

    monkeypatch.setattr(
        "homeassistant.components.greencell.mqtt.async_wait_for_mqtt_client",
        lambda h: asyncio.sleep(0),
    )

    ev = asyncio.Event()
    ev.set()
    monkeypatch.setattr(
        "homeassistant.components.greencell.wait_for_device_ready",
        lambda hass, serial, timeout: (lambda: None, ev),
    )

    called = {}

    async def fake_forward(entry: ConfigEntry, platforms: list[str]) -> None:
        called["yes"] = True

    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", fake_forward)

    result = await async_setup_entry(hass, entry)  # type: ignore[arg-type]

    assert result is True
    assert entry.runtime_data is not None
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]
    assert called["yes"]


@pytest.mark.asyncio
async def test_async_setup_entry_missing_serial(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test async_setup_entry with no serial number in entry."""
    entry = DummyConfigEntry(serial=None)

    monkeypatch.setattr(
        "homeassistant.components.greencell.mqtt.async_wait_for_mqtt_client",
        lambda h: asyncio.sleep(0),
    )

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, entry)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_async_setup_entry_timeout(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test async_setup_entry with timeout waiting for device readiness."""
    entry = DummyConfigEntry()

    monkeypatch.setattr(
        "homeassistant.components.greencell.mqtt.async_wait_for_mqtt_client",
        lambda h: asyncio.sleep(0),
    )

    ev = asyncio.Event()
    monkeypatch.setattr(
        "homeassistant.components.greencell.wait_for_device_ready",
        lambda hass, serial, timeout: (lambda: None, ev),
    )

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, entry)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_async_unload_entry(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test unloading a Greencell config entry."""
    entry = DummyConfigEntry()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"dummy": "runtime"}

    async def fake_unload(entry_: ConfigEntry, platforms: list[str]) -> bool:
        return True

    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", fake_unload)

    ok = await async_unload_entry(hass, entry)  # type: ignore[arg-type]
    assert ok
    assert entry.entry_id not in hass.data[DOMAIN]
