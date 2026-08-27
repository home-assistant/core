"""Tests for config entry unload/removal behavior in __init__.py."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.bluetti import (
    BluettiRuntimeData,
    _async_update_listener,
    async_remove_config_entry_device,
    async_remove_entry,
    async_unload_entry,
)
from homeassistant.components.bluetti.const import DOMAIN
from homeassistant.components.bluetti.models import BluettiDevice
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


def _runtime_data(stomp_client) -> BluettiRuntimeData:
    return BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[]),
        stomp_client=stomp_client,
        coordinators={},
    )


async def test_unload_entry_disconnects_websocket(hass):
    """Unload entry disconnects websocket."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    stomp_client = AsyncMock()
    entry.runtime_data = _runtime_data(stomp_client)

    result = await async_unload_entry(hass, entry)

    assert result is True
    stomp_client.disconnect.assert_awaited_once()


async def test_unload_entry_survives_disconnect_error(hass):
    """Unload entry survives disconnect error."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    stomp_client = AsyncMock()
    stomp_client.disconnect.side_effect = RuntimeError("socket already closed")
    entry.runtime_data = _runtime_data(stomp_client)

    # Must not raise even though disconnect() failed.
    result = await async_unload_entry(hass, entry)
    assert result is True


async def test_unload_entry_does_not_explicitly_shut_down_modbus_coordinators(hass):
    """Unload entry does not explicitly shut down modbus coordinators."""
    # DataUpdateCoordinator (constructed with config_entry=entry) already
    # registers its own async_shutdown via config_entry.async_on_unload -
    # an explicit call here would run BluettiModbusCoordinator's
    # connection-closing side effect a second time. This is a regression
    # test for that: a raw AsyncMock modbus_coordinator (not wired to any
    # real config_entry.async_on_unload registration) must NOT be shut
    # down by async_unload_entry itself.
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    modbus_coordinator = AsyncMock()
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[]),
        stomp_client=AsyncMock(),
        coordinators={},
        modbus_coordinators={"SN1": modbus_coordinator},
    )

    result = await async_unload_entry(hass, entry)

    assert result is True
    modbus_coordinator.async_shutdown.assert_not_awaited()


async def test_unload_entry_without_runtime_data_does_not_raise(hass):
    """A config entry that never finished setup has no runtime_data yet."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    result = await async_unload_entry(hass, entry)
    assert result is True


async def test_remove_entry_disconnects_websocket(hass):
    """Remove entry disconnects websocket."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    stomp_client = AsyncMock()
    entry.runtime_data = _runtime_data(stomp_client)

    await async_remove_entry(hass, entry)

    stomp_client.disconnect.assert_awaited_once()


async def test_remove_entry_without_runtime_data_does_not_raise(hass):
    """Removing a config entry that never finished setup must not crash."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    await async_remove_entry(hass, entry)


async def test_remove_entry_survives_disconnect_error(hass):
    """Remove entry survives disconnect error."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    stomp_client = AsyncMock()
    stomp_client.disconnect.side_effect = RuntimeError("boom")
    entry.runtime_data = _runtime_data(stomp_client)

    # Must not raise even though disconnect() failed.
    await async_remove_entry(hass, entry)


async def test_remove_entry_cleans_up_device_and_entity_registries(hass):
    """Remove entry cleans up device and entity registries."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    entry.runtime_data = _runtime_data(MagicMock())

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "SN1")},
        name="Test Device",
        manufacturer="Bluetti",
        model="AC200L",
    )
    entity_registry = er.async_get(hass)
    # Deliberately not linked to device_entry: device removal cascades to
    # its own entities, so this checks the explicit entity cleanup loop.
    entity_registry.async_get_or_create(
        "sensor", DOMAIN, "SN1_standalone", config_entry=entry,
    )

    await async_remove_entry(hass, entry)

    assert device_registry.async_get_device_by_identifier((DOMAIN, "SN1"), entry.entry_id) is None
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "SN1_standalone") is None


async def test_remove_config_entry_device_stops_polling_and_updates_options(hass):
    """Remove config entry device stops polling and updates options."""
    entry = MockConfigEntry(
        domain=DOMAIN, options={"devices": ["SN1", "SN2"], "modbus": {"SN1": {"host": "10.2.1.60", "port": 502}}}
    )
    entry.add_to_hass(hass)

    device1 = BluettiDevice(device_id="SN1", on_line="1", name="First", sn="SN1", model="Balco260")
    device2 = BluettiDevice(device_id="SN2", on_line="1", name="Second", sn="SN2", model="EL400")
    coordinator1 = AsyncMock()
    modbus_coordinator1 = AsyncMock()
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[device1, device2]),
        stomp_client=MagicMock(),
        coordinators={"SN1": coordinator1, "SN2": MagicMock()},
        modbus_coordinators={"SN1": modbus_coordinator1},
    )

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "SN1")},
        name="First",
        manufacturer="Bluetti",
        model="Balco260",
    )

    result = await async_remove_config_entry_device(hass, entry, device_entry)

    assert result is True
    coordinator1.async_shutdown.assert_awaited_once()
    modbus_coordinator1.async_shutdown.assert_awaited_once()
    assert [d.device_id for d in entry.runtime_data.bluetti_devices.devices] == ["SN2"]
    assert "SN1" not in entry.runtime_data.coordinators
    assert "SN2" in entry.runtime_data.coordinators
    assert "SN1" not in entry.runtime_data.modbus_coordinators
    assert entry.options["devices"] == ["SN2"]
    assert entry.options["modbus"] == {}


async def test_remove_config_entry_device_rejects_non_bluetti_device(hass):
    """Remove config entry device rejects non bluetti device."""
    entry = MockConfigEntry(domain=DOMAIN, options={"devices": ["SN1"]})
    entry.add_to_hass(hass)
    entry.runtime_data = _runtime_data(MagicMock())

    device_registry = dr.async_get(hass)
    other_entry = MockConfigEntry(domain="other_domain")
    other_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other_domain", "not-bluetti")},
        name="Unrelated device",
    )

    result = await async_remove_config_entry_device(hass, entry, device_entry)

    assert result is False
    assert entry.options["devices"] == ["SN1"]


async def test_remove_config_entry_device_without_runtime_data_does_not_raise(hass):
    """A device removed before the entry ever finished setup must not crash."""
    entry = MockConfigEntry(domain=DOMAIN, options={"devices": ["SN1"]})
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "SN1")},
        name="First",
    )

    result = await async_remove_config_entry_device(hass, entry, device_entry)

    assert result is True
    assert entry.options["devices"] == []


async def test_remove_config_entry_device_leaves_options_untouched_when_already_absent(hass):
    """Remove config entry device leaves options untouched when already absent."""
    entry = MockConfigEntry(domain=DOMAIN, options={"devices": ["SN2"]})
    entry.add_to_hass(hass)
    entry.runtime_data = _runtime_data(MagicMock())

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "SN1")},
        name="First",
    )

    with patch.object(hass.config_entries, "async_update_entry") as mock_update:
        result = await async_remove_config_entry_device(hass, entry, device_entry)

    assert result is True
    mock_update.assert_not_called()


async def test_update_listener_reloads_entry(hass):
    """Update listener reloads entry."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        await _async_update_listener(hass, entry)

    mock_reload.assert_awaited_once_with(entry.entry_id)
