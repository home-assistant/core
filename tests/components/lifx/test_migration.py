"""Tests the lifx migration."""

import pytest

from homeassistant.components.lifx import DOMAIN
from homeassistant.components.lifx.config_flow import LIFXConfigFlow
from homeassistant.components.lifx.const import CONF_SERIAL
from homeassistant.components.lifx.util import async_entry_serial, normalize_serial
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import IP_ADDRESS, LABEL, SERIAL
from .helpers import LEGACY_SERIAL, MAC_ADDRESS

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("d073d5ddeecc", "d073d5ddeecc"),
        ("D073D5DDEECC", "d073d5ddeecc"),
        ("d0:73:d5:dd:ee:cc", "d073d5ddeecc"),
        ("D0:73:D5:DD:EE:CC", "d073d5ddeecc"),
    ],
)
def test_normalize_serial(value: str, expected: str) -> None:
    """Test normalization of valid raw and colon-formatted serials."""
    assert normalize_serial(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "d073d5ddee",
        "d073d5ddeeff00",
        "ggbbccddeecc",
        "gg:bb:cc:dd:ee:cc",
        "aa-bb-cc-dd-ee-cc",
        "aabb.ccdd.eecc",
    ],
)
def test_normalize_serial_rejects_invalid_value(value: str) -> None:
    """Test rejection of malformed serials."""
    with pytest.raises(ValueError):
        normalize_serial(value)


@pytest.mark.parametrize(
    ("version", "unique_id", "data"),
    [
        (
            2,
            "d0:73:d5:dd:ee:cc",
            {CONF_HOST: IP_ADDRESS, CONF_SERIAL: "ggbbccddeecc"},
        ),
        (1, "gg:bb:cc:dd:ee:cc", {CONF_HOST: IP_ADDRESS}),
    ],
)
def test_entry_serial_returns_none_for_malformed_identity(
    version: int, unique_id: str, data: dict[str, str]
) -> None:
    """Test malformed stored identity is ignored."""
    entry = MockConfigEntry(
        domain=DOMAIN, version=version, unique_id=unique_id, data=data
    )

    assert async_entry_serial(entry) is None


async def test_migrate_current_entry_to_version_2(
    hass: HomeAssistant,
) -> None:
    """Test migration of a current per-device entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=LEGACY_SERIAL,
        data={CONF_HOST: IP_ADDRESS},
    )
    entry.add_to_hass(hass)

    assert await entry.async_migrate(hass)
    assert entry.version == 2
    assert entry.unique_id == SERIAL
    assert entry.data == {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL}


async def test_migrate_registries_off_the_colon_separated_serial(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the registries move to the raw serial."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=LEGACY_SERIAL,
        data={CONF_HOST: IP_ADDRESS},
    )
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, LEGACY_SERIAL), ("other", LEGACY_SERIAL)},
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)},
        name=LABEL,
    )
    light = entity_registry.async_get_or_create(
        LIGHT_DOMAIN, DOMAIN, LEGACY_SERIAL, config_entry=entry, device_id=device.id
    )
    rssi = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{LEGACY_SERIAL}_rssi",
        config_entry=entry,
        device_id=device.id,
    )

    assert await entry.async_migrate(hass)

    migrated = device_registry.async_get(device.id)
    assert migrated is not None
    assert migrated.identifiers == {(DOMAIN, SERIAL), ("other", LEGACY_SERIAL)}
    assert migrated.connections == {(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)}
    assert entity_registry.async_get(light.entity_id).unique_id == SERIAL
    assert entity_registry.async_get(rssi.entity_id).unique_id == f"{SERIAL}_rssi"


async def test_migrate_leaves_registry_entries_it_cannot_improve_alone(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an unrecognised identifier and an already raw unique ID are untouched."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=LEGACY_SERIAL,
        data={CONF_HOST: IP_ADDRESS},
    )
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "not-a-serial")}
    )
    light = entity_registry.async_get_or_create(
        LIGHT_DOMAIN, DOMAIN, SERIAL, config_entry=entry, device_id=device.id
    )

    assert await entry.async_migrate(hass)

    migrated = device_registry.async_get(device.id)
    assert migrated is not None
    assert migrated.identifiers == {(DOMAIN, "not-a-serial")}
    assert entity_registry.async_get(light.entity_id).unique_id == SERIAL


@pytest.mark.parametrize("unique_id", ["gg:bb:cc:dd:ee:cc", "d0:73:d5:dd:ee"])
async def test_migrate_malformed_current_entry_fails_cleanly(
    hass: HomeAssistant, unique_id: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Test malformed current entries remain unchanged when migration fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=unique_id,
        data={CONF_HOST: IP_ADDRESS},
    )
    entry.add_to_hass(hass)

    # Nothing the user can retry makes the entry migratable
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert "that is not a LIFX serial number" in caplog.text
    assert entry.version == 1
    assert entry.unique_id == unique_id
    assert entry.data == {CONF_HOST: IP_ADDRESS}


@pytest.mark.parametrize("unique_id", [None, DOMAIN])
async def test_migrate_removes_the_legacy_shared_entry(
    hass: HomeAssistant, unique_id: str | None
) -> None:
    """Test the shared entry every device once lived on is dropped, not migrated.

    It holds no host for any of its devices, so they are left to discovery,
    which is how they were found while the entry was in use.
    """
    entry = MockConfigEntry(domain=DOMAIN, version=1, unique_id=unique_id, data={})
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_migrate_version_2_entry_is_noop(hass: HomeAssistant) -> None:
    """Test migration leaves a version 2 entry unchanged."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=LIFXConfigFlow.VERSION,
        unique_id=SERIAL,
        data={CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL},
    )
    entry.add_to_hass(hass)

    assert await entry.async_migrate(hass)
    assert entry.version == 2
    assert entry.unique_id == SERIAL
    assert entry.data == {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL}
