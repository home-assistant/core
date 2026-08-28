"""Tests for config entry unload/removal behavior in __init__.py."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.bluetti import (
    BluettiRuntimeData,
    _async_update_listener,
    async_remove_config_entry_device,
    async_remove_entry,
)
from homeassistant.components.bluetti.const import DOMAIN
from homeassistant.components.bluetti.models import BluettiDevice
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


def _runtime_data(stomp_client) -> BluettiRuntimeData:
    return BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[]),
        stomp_client=stomp_client,
        coordinators={},
    )


async def test_remove_entry_disconnects_websocket(hass: HomeAssistant) -> None:
    """Remove entry disconnects websocket."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    stomp_client = AsyncMock()
    entry.runtime_data = _runtime_data(stomp_client)

    await async_remove_entry(hass, entry)

    stomp_client.disconnect.assert_awaited_once()


async def test_remove_entry_without_runtime_data_does_not_raise(
    hass: HomeAssistant,
) -> None:
    """Removing a config entry that never finished setup must not crash."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    await async_remove_entry(hass, entry)


async def test_remove_entry_survives_disconnect_error(hass: HomeAssistant) -> None:
    """Remove entry survives disconnect error."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    stomp_client = AsyncMock()
    stomp_client.disconnect.side_effect = RuntimeError("boom")
    entry.runtime_data = _runtime_data(stomp_client)

    # Must not raise even though disconnect() failed.
    await async_remove_entry(hass, entry)


async def test_remove_entry_cleans_up_device_and_entity_registries(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Removing the entry cleans up its devices and entities.

    Driven through hass.config_entries.async_remove() rather than calling
    async_remove_entry() directly: this integration's own hook no longer
    does this cleanup itself (that would risk deleting a device merged with
    another integration's - see async_remove_entry's docstring) and relies
    entirely on Core's own post-removal device_registry/entity_registry
    async_clear_config_entry(), which only runs as part of the real removal
    pipeline, not from calling the hook in isolation.
    """
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    entry.runtime_data = _runtime_data(MagicMock())

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "SN1")},
        name="Test Device",
        manufacturer="Bluetti",
        model="AC200L",
    )
    # Deliberately not linked to device_entry: device removal cascades to
    # its own entities, so this checks entity cleanup independently too.
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "SN1_standalone",
        config_entry=entry,
    )

    await hass.config_entries.async_remove(entry.entry_id)

    assert (
        device_registry.async_get_device_by_identifier((DOMAIN, "SN1"), entry.entry_id)
        is None
    )
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, "SN1_standalone") is None
    )


async def test_remove_config_entry_device_stops_polling_and_updates_options(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Remove config entry device stops polling and updates options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={"devices": ["SN1", "SN2"]},
    )
    entry.add_to_hass(hass)

    device1 = BluettiDevice(
        device_id="SN1", on_line="1", name="First", sn="SN1", model="Balco260"
    )
    device2 = BluettiDevice(
        device_id="SN2", on_line="1", name="Second", sn="SN2", model="EL400"
    )
    coordinator1 = AsyncMock()
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[device1, device2]),
        stomp_client=MagicMock(),
        coordinators={"SN1": coordinator1, "SN2": MagicMock()},
    )

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
    assert [d.device_id for d in entry.runtime_data.bluetti_devices.devices] == ["SN2"]
    assert "SN1" not in entry.runtime_data.coordinators
    assert "SN2" in entry.runtime_data.coordinators
    assert entry.options["devices"] == ["SN2"]


async def test_remove_config_entry_device_rejects_non_bluetti_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Remove config entry device rejects non bluetti device."""
    entry = MockConfigEntry(domain=DOMAIN, options={"devices": ["SN1"]})
    entry.add_to_hass(hass)
    entry.runtime_data = _runtime_data(MagicMock())

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


async def test_remove_config_entry_device_without_runtime_data_does_not_raise(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A device removed before the entry ever finished setup must not crash."""
    entry = MockConfigEntry(domain=DOMAIN, options={"devices": ["SN1"]})
    entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "SN1")},
        name="First",
    )

    result = await async_remove_config_entry_device(hass, entry, device_entry)

    assert result is True
    assert entry.options["devices"] == []


async def test_remove_config_entry_device_leaves_options_untouched_when_already_absent(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Remove config entry device leaves options untouched when already absent."""
    entry = MockConfigEntry(domain=DOMAIN, options={"devices": ["SN2"]})
    entry.add_to_hass(hass)
    entry.runtime_data = _runtime_data(MagicMock())

    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "SN1")},
        name="First",
    )

    with patch.object(hass.config_entries, "async_update_entry") as mock_update:
        result = await async_remove_config_entry_device(hass, entry, device_entry)

    assert result is True
    mock_update.assert_not_called()


async def test_remove_config_entry_device_drops_stale_product_entry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Removing a device must also drop its cached product entry.

    Regression test: async_remove_config_entry_device() only updated
    entry.options["devices"], never entry.data["products"] - a later
    re-add of the same serial was treated as "already cached" by
    config_flow.py/options_flow.py's product merge (they only add
    products whose sn isn't already present), silently keeping the stale
    name/model/state from before removal instead of fresh cloud data.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "products": [
                {"sn": "SN1", "name": "Old Name", "stateList": [], "online": "1"},
                {"sn": "SN2", "name": "Kept", "stateList": [], "online": "1"},
            ]
        },
        options={"devices": ["SN1", "SN2"]},
    )
    entry.add_to_hass(hass)
    entry.runtime_data = _runtime_data(MagicMock())

    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "SN1")},
        name="Old Name",
    )

    result = await async_remove_config_entry_device(hass, entry, device_entry)

    assert result is True
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert [p["sn"] for p in updated.data["products"]] == ["SN2"]


async def test_update_listener_reloads_entry(hass: HomeAssistant) -> None:
    """Update listener reloads entry."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        await _async_update_listener(hass, entry)

    mock_reload.assert_awaited_once_with(entry.entry_id)
