"""Tests for LIFX device registry repair."""

from homeassistant.components.lifx.const import DOMAIN
from homeassistant.components.lifx.entity import async_repair_device_registry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .helpers import MAC_ADDRESS, SERIAL, create_mock_light_state

from tests.common import MockConfigEntry

INCORRECT_OFFSET_MAC = "d0:73:d5:dd:ee:cd"
OTHER_SERIAL = "d0:73:d5:dd:ee:cd"
UNRELATED_CONNECTION = (dr.CONNECTION_BLUETOOTH, "test-connection")


def _add_entry(
    hass: HomeAssistant,
    *,
    domain: str = DOMAIN,
    unique_id: str = SERIAL,
) -> MockConfigEntry:
    """Add a config entry to Home Assistant."""
    entry = MockConfigEntry(domain=domain, unique_id=unique_id)
    entry.add_to_hass(hass)
    return entry


def _add_device(
    device_registry: dr.DeviceRegistry,
    entry: MockConfigEntry,
    *,
    identifiers: set[tuple[str, str]] | None = None,
    connections: set[tuple[str, str]] | None = None,
) -> dr.DeviceEntry:
    """Add a device to the registry."""
    return device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=identifiers or {(DOMAIN, SERIAL)},
        connections=connections or set(),
        name="LIFX light",
    )


def test_firmware_four_state_uses_unmodified_library_mac(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a firmware 4 state does not have its library MAC adjusted."""
    entry = _add_entry(hass)
    original = _add_device(
        device_registry,
        entry,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)},
    )
    state = create_mock_light_state(
        serial=SERIAL,
        mac_address=SERIAL,
    )

    async_repair_device_registry(hass, entry, state)

    repaired = device_registry.async_get(original.id)
    assert repaired is not None
    assert repaired.id == original.id
    assert repaired.identifiers == {(DOMAIN, SERIAL)}
    assert (dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS) in repaired.connections
    assert (dr.CONNECTION_NETWORK_MAC, INCORRECT_OFFSET_MAC) not in repaired.connections


def test_incorrect_offset_mac_is_replaced_in_place(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the historical offset MAC is replaced on the original device."""
    entry = _add_entry(hass)
    original = _add_device(
        device_registry,
        entry,
        connections={(dr.CONNECTION_NETWORK_MAC, INCORRECT_OFFSET_MAC)},
    )

    async_repair_device_registry(hass, entry, create_mock_light_state())

    repaired = device_registry.async_get(original.id)
    assert repaired is not None
    assert repaired.id == original.id
    assert repaired.identifiers == {(DOMAIN, SERIAL)}
    assert (dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS) in repaired.connections
    assert (dr.CONNECTION_NETWORK_MAC, INCORRECT_OFFSET_MAC) not in repaired.connections


def test_repair_preserves_device_and_entity_metadata(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test repair changes identity data without replacing customized records."""
    entry = _add_entry(hass)
    original = _add_device(
        device_registry,
        entry,
        connections={(dr.CONNECTION_NETWORK_MAC, INCORRECT_OFFSET_MAC)},
    )
    device_registry.async_update_device(
        original.id,
        area_id="living_room",
        disabled_by=dr.DeviceEntryDisabler.USER,
        labels={"favorite"},
        name_by_user="Reading light",
    )
    entity = entity_registry.async_get_or_create(
        config_entry=entry,
        platform=DOMAIN,
        domain="light",
        unique_id=SERIAL,
        device_id=original.id,
    )

    async_repair_device_registry(hass, entry, create_mock_light_state())

    repaired = device_registry.async_get(original.id)
    repaired_entity = entity_registry.async_get(entity.entity_id)
    assert repaired is not None
    assert repaired_entity is not None
    assert repaired.id == original.id
    assert repaired_entity.device_id == original.id
    assert repaired.area_id == "living_room"
    assert repaired.labels == {"favorite"}
    assert repaired.disabled_by is dr.DeviceEntryDisabler.USER
    assert repaired.name_by_user == "Reading light"


def test_repair_preserves_unrelated_connections(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test repair replaces only MAC connections."""
    entry = _add_entry(hass)
    original = _add_device(
        device_registry,
        entry,
        connections={
            (dr.CONNECTION_NETWORK_MAC, INCORRECT_OFFSET_MAC),
            UNRELATED_CONNECTION,
        },
    )

    async_repair_device_registry(hass, entry, create_mock_light_state())

    repaired = device_registry.async_get(original.id)
    assert repaired is not None
    assert repaired.connections == {
        (dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS),
        UNRELATED_CONNECTION,
    }


def test_obsolete_mac_collision_does_not_mutate_other_physical_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing an obsolete MAC does not affect its physical owner."""
    entry = _add_entry(hass)
    original = _add_device(
        device_registry,
        entry,
        connections={(dr.CONNECTION_NETWORK_MAC, INCORRECT_OFFSET_MAC)},
    )
    other_entry = _add_entry(hass, unique_id=OTHER_SERIAL)
    other = _add_device(
        device_registry,
        other_entry,
        identifiers={(DOMAIN, OTHER_SERIAL)},
        connections={(dr.CONNECTION_NETWORK_MAC, INCORRECT_OFFSET_MAC)},
    )

    async_repair_device_registry(hass, entry, create_mock_light_state())

    repaired = device_registry.async_get(original.id)
    preserved_other = device_registry.async_get(other.id)
    assert repaired is not None
    assert preserved_other is not None
    assert repaired.connections == {(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)}
    assert preserved_other.connections == {
        (dr.CONNECTION_NETWORK_MAC, INCORRECT_OFFSET_MAC)
    }


def test_matching_mac_from_other_integration_is_not_mutated(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test another integration may publish the same physical MAC independently."""
    entry = _add_entry(hass)
    original = _add_device(
        device_registry,
        entry,
        connections={(dr.CONNECTION_NETWORK_MAC, INCORRECT_OFFSET_MAC)},
    )
    other_entry = _add_entry(hass, domain="other", unique_id="other-device")
    other = _add_device(
        device_registry,
        other_entry,
        identifiers={("other", "other-device")},
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)},
    )

    async_repair_device_registry(hass, entry, create_mock_light_state())

    repaired = device_registry.async_get(original.id)
    preserved_other = device_registry.async_get(other.id)
    assert repaired is not None
    assert preserved_other == other
    assert repaired.connections == {(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)}
