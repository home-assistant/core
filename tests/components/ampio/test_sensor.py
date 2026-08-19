"""Tests for the Ampio sensor platform."""

from dataclasses import replace
from unittest.mock import MagicMock

from ampio_mqtt import (
    OPEN_SENSOR_KEY_PREFIXES,
    SENSOR_KIND_KEYS,
    AmpioObject,
    AvailabilityChanged,
    ObjectRemoved,
    ObjectUpdated,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ampio.const import DOMAIN
from homeassistant.components.ampio.sensor import SENSOR_DESCRIPTIONS
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import (
    MSENS_FALLBACK_NAME,
    MSENS_IDENTIFIER,
    MSERV_MAC,
    emit,
    make_object,
)

from tests.common import MockConfigEntry, snapshot_platform

TEMPERATURE_ENTITY_ID = "sensor.m_sens_salon_temperatura"
HUMIDITY_ENTITY_ID = "sensor.m_sens_salon_wilgotnosc"
CO2_ENTITY_ID = "sensor.m_sens_salon_co2"


async def _push_value(
    hass: HomeAssistant, client: MagicMock, oid: int, value: str
) -> None:
    """Replace the object's value in the store and push the update event."""
    obj = replace(client.objects[oid], value=value)
    client.objects[oid] = obj
    emit(client, ObjectUpdated(object=obj))
    await hass.async_block_till_done()


def test_sensor_kind_vocabulary_is_mapped_or_excluded() -> None:
    """A library upgrade that adds a kind fails here instead of dropping entities.

    The metadata-less generic "value" kind and the open key families are
    deliberately not exposed; a new key or prefix forces a mapping decision.
    """
    assert SENSOR_KIND_KEYS - {"value"} == SENSOR_DESCRIPTIONS.keys()
    assert set(OPEN_SENSOR_KEY_PREFIXES) == {"analog_", "value_"}


@pytest.mark.usefixtures("mock_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot every entity's registry entry and state."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_client")
async def test_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot every device registry entry the integration creates."""
    await setup_integration(hass, mock_config_entry)

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert devices
    for device in devices:
        assert device == snapshot(name=f"device-{device.name}")


async def test_push_update_changes_state(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A pushed object update is reflected in the entity state."""
    await setup_integration(hass, mock_config_entry)

    await _push_value(hass, mock_client, 36, "25.5")

    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "25.5"


async def test_unusable_value_surfaces_as_unknown(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A push a numeric sensor cannot represent maps to unknown, not an error.

    Which value shapes parse to None (nan, inf, overflow, non-numeric) is the
    library's ``numeric_value`` contract, covered by its own tests; here one
    representative proves the None-to-unknown mapping.
    """
    await setup_integration(hass, mock_config_entry)

    await _push_value(hass, mock_client, 36, "INVALID")

    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == STATE_UNKNOWN


async def test_push_only_updates_target_entity(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A push for one object must not write state on its siblings.

    ``last_reported`` advances on any write (even an unchanged value), so it
    is the signal that catches a spurious fan-out.
    """
    await setup_integration(hass, mock_config_entry)
    temperature_before = hass.states.get(TEMPERATURE_ENTITY_ID).last_reported

    await _push_value(hass, mock_client, 37, "45.5")

    assert hass.states.get(HUMIDITY_ENTITY_ID).state == "45.5"
    assert hass.states.get(TEMPERATURE_ENTITY_ID).last_reported == temperature_before


async def test_removed_object_becomes_unavailable(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """An object evicted from the catalogue flips its entity unavailable."""
    await setup_integration(hass, mock_config_entry)

    obj = mock_client.objects.pop(43)
    emit(mock_client, ObjectRemoved(object=obj))
    await hass.async_block_till_done()

    assert hass.states.get(CO2_ENTITY_ID).state == STATE_UNAVAILABLE


async def test_broker_availability_flips_entities(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A broker disconnect flips every entity unavailable; reconnect restores."""
    await setup_integration(hass, mock_config_entry)

    mock_client.available = False
    emit(mock_client, AvailabilityChanged(available=False))
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(HUMIDITY_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(CO2_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_client.available = True
    emit(mock_client, AvailabilityChanged(available=True))
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "24.4"


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param(
            make_object(
                200, "lin_wej", 1, leaf_id="", funkcja=5, name="Ghost", value="55.0"
            ),
            id="ghost-without-leaf",
        ),
        pytest.param(
            make_object(
                201, "lin_wej", 7, leaf_id="0_cb8f_lin_0_9", funkcja=6, params=16
            ),
            id="hidden",
        ),
        pytest.param(
            make_object(
                202,
                "lin_wej",
                9,
                leaf_id="0_cb8f_lin_0_10",
                funkcja=7,
                name="Status",
                value="42.0",
            ),
            id="kind-without-description",
        ),
        pytest.param(
            make_object(
                203,
                "przekaznik",
                0,
                leaf_id="0_cb8f_prz_0_1",
                funkcja=8,
                name="Relay",
                value="1",
            ),
            id="not-a-sensor",
        ),
    ],
)
async def test_unexposable_objects_are_skipped(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    extra: AmpioObject,
) -> None:
    """Invisible objects and kinds outside the sensor table produce no entity."""
    mock_client.objects[extra.id] = extra

    await setup_integration(hass, mock_config_entry)

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == 8


@pytest.mark.parametrize(
    "leaf_id",
    [
        pytest.param("0_nomac_temp_0_1", id="unparseable-module-mac"),
        pytest.param("0_1_temp_0_1", id="server-owned"),
    ],
)
async def test_hub_anchored_objects(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    leaf_id: str,
) -> None:
    """The M-SERV's own objects and unresolvable leafs anchor to the hub."""
    mock_client.objects[500] = make_object(
        500, "temp", 1, leaf_id=leaf_id, funkcja=5, name="Hub sensor"
    )

    await setup_integration(hass, mock_config_entry)

    hub = device_registry.async_get_device_by_identifier(
        (DOMAIN, MSERV_MAC), mock_config_entry.entry_id
    )
    assert hub is not None
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{MSERV_MAC}_leaf_{leaf_id}"
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).device_id == hub.id


async def test_module_without_catalogue_row_gets_bare_device(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A leaf-derived mac with no module row still keys its own device."""
    mock_client.objects[500] = make_object(
        500, "temp", 1, leaf_id="0_dead_temp_0_1", device_id=99, name="Dangling"
    )

    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{MSERV_MAC}:{0xDEAD}"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Ampio module 0xDEAD"
    assert device.model is None
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{MSERV_MAC}_leaf_0_dead_temp_0_1"
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).device_id == device.id


@pytest.mark.parametrize(
    ("changes", "expected_model"),
    [
        pytest.param({"name": None}, "M-SENS", id="nameless-module"),
        # The device_id join key is volatile across resyncs; the leaf-derived
        # mac is authoritative, so a disagreeing row must not misattribute
        # another module's metadata to this device.
        pytest.param({"mac": 99999}, None, id="disagreeing-mac"),
    ],
)
async def test_module_row_cannot_name_device(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    changes: dict[str, int | None],
    expected_model: str | None,
) -> None:
    """A catalogue row that cannot label the device leaves the mac-derived name."""
    mock_client.modules[17] = replace(mock_client.modules[17], **changes)

    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        MSENS_IDENTIFIER, mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == MSENS_FALLBACK_NAME
    assert device.model == expected_model
