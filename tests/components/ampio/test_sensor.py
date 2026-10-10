"""Tests for the Ampio sensor platform."""

from dataclasses import replace
from unittest.mock import MagicMock

from ampio_mqtt import (
    SENSOR_KIND_KEY_PREFIXES,
    SENSOR_KIND_KEYS,
    AmpioObject,
    AvailabilityChanged,
    ObjectRemoved,
    ObjectUpdated,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ampio.const import DOMAIN, HUB_IDENTIFIER
from homeassistant.components.ampio.sensor import SENSOR_DESCRIPTIONS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import (
    MREL_MAC,
    MSENS_FALLBACK_NAME,
    MSENS_IDENTIFIER,
    emit,
    make_object,
    module_identifier,
    object_identifier,
    object_unique_id,
)

from tests.common import MockConfigEntry, snapshot_platform

TEMPERATURE_ENTITY_ID = "sensor.m_sens_salon_temperatura"
HUMIDITY_ENTITY_ID = "sensor.m_sens_salon_wilgotnosc"
# An unnamed object's device reads "Object <id>", after its module's name.
CO2_ENTITY_ID = "sensor.m_sens_salon_object_43_co2"


async def _push_value(
    hass: HomeAssistant, client: MagicMock, oid: int, value: str
) -> None:
    """Replace the object's state in the store and push the update event."""
    obj = replace(client.objects[oid], state=value)
    client.objects[oid] = obj
    emit(client, ObjectUpdated(object=obj))
    await hass.async_block_till_done()


def test_sensor_kind_vocabulary_is_mapped_or_excluded() -> None:
    """A library upgrade that adds a kind fails here instead of dropping entities.

    The metadata-less generic "value" kind and the open key families are
    deliberately not exposed; a new key or prefix forces a mapping decision.
    """
    assert SENSOR_KIND_KEYS - {"value"} == SENSOR_DESCRIPTIONS.keys()
    assert set(SENSOR_KIND_KEY_PREFIXES) == {"analog_", "value_"}


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
    """Snapshot every device and child device the integration creates."""
    await setup_integration(hass, mock_config_entry)

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    children = dr.async_child_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert devices
    assert len(children) == 8
    for device in devices:
        assert device == snapshot(name=f"device-{device.name}")
    for child in children:
        assert child == snapshot(name=f"child-{child.name}")


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
    """A push that a numeric sensor cannot represent maps to unknown, not an error.

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
                202,
                "lin_wej",
                9,
                leaf_id="0_cb8f_74_0_10",
                funkcja=7,
                name="Status",
                state="42.0",
            ),
            id="kind-without-description",
        ),
        pytest.param(
            make_object(
                203,
                "przekaznik",
                0,
                leaf_id="0_cb8f_1_0_1",
                funkcja=8,
                name="Relay",
                state="1",
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
    """Kinds outside the sensor table produce no entity."""
    mock_client.objects[extra.id] = extra

    await setup_integration(hass, mock_config_entry)

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == 8


async def test_objects_sharing_a_leaf_get_separate_entities(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Two Designer objects that drive one output keep one entity each."""
    mock_client.objects[132] = make_object(
        132, "lin_wej", 7, leaf_id="0_cb8f_74_0_3", funkcja=3, state="900.5"
    )

    await setup_integration(hass, mock_config_entry)

    unique_ids = {
        entity.unique_id
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    assert len(unique_ids) == 9
    assert {object_unique_id(43), object_unique_id(132)} <= unique_ids


async def test_server_owned_object_anchors_to_hub(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The M-SERV's own objects get child devices under the hub."""
    mock_client.objects[500] = make_object(
        500, "temp", 1, leaf_id="0_1_76_0_1", funkcja=5, name="Hub sensor"
    )

    await setup_integration(hass, mock_config_entry)

    hub = device_registry.async_get_device_by_identifier(
        HUB_IDENTIFIER, mock_config_entry.entry_id
    )
    assert hub is not None
    child = device_registry.async_get_child_device_by_identifier(
        object_identifier(500), mock_config_entry.entry_id
    )
    assert child is not None
    assert child.parent_device_id == hub.id
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, object_unique_id(500)
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).device_id == child.id


async def test_module_without_catalogue_row_gets_bare_device(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A module mac with no catalogue row still keys its own device."""
    mock_client.objects[500] = make_object(
        500, "temp", 1, leaf_id="0_dead_76_0_1", name="Dangling"
    )

    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        module_identifier(0xDEAD), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Ampio module 0xDEAD"
    assert device.model is None
    child = device_registry.async_get_child_device_by_identifier(
        object_identifier(500), mock_config_entry.entry_id
    )
    assert child is not None
    assert child.parent_device_id == device.id


async def test_nameless_module_row_keeps_fallback_name(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A catalogue row without a name leaves the mac-derived device name."""
    mock_client.modules[17] = replace(mock_client.modules[17], nazwa_urzadzenia=None)

    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        MSENS_IDENTIFIER, mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == MSENS_FALLBACK_NAME
    assert device.model == "M-SENS"


@pytest.mark.parametrize(
    "leaf_id",
    [
        pytest.param("0_be82_76_0_1", id="to-another-module"),
        pytest.param("0_1_76_0_1", id="onto-the-m-serv"),
    ],
)
async def test_moved_object_keeps_its_first_parent(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    leaf_id: str,
) -> None:
    """An object moved to another module in Designer stays under its first module.

    The registry refuses to re-parent a child device.
    """
    await setup_integration(hass, mock_config_entry)
    first_parent = device_registry.async_get_device_by_identifier(
        MSENS_IDENTIFIER, mock_config_entry.entry_id
    )
    assert first_parent is not None

    mock_client.objects[36] = make_object(
        36, "temp", 1, leaf_id=leaf_id, name="Temperatura", state="24.4"
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    child = device_registry.async_get_child_device_by_identifier(
        object_identifier(36), mock_config_entry.entry_id
    )
    assert child is not None
    assert child.parent_device_id == first_parent.id
    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "24.4"
    assert (
        device_registry.async_get_device_by_identifier(
            module_identifier(MREL_MAC), mock_config_entry.entry_id
        )
        is None
    )


async def test_module_without_sensors_gets_no_device(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A module whose objects expose no sensor registers no device."""
    mock_client.objects[203] = make_object(
        203, "przekaznik", 0, leaf_id="0_be82_1_0_1", name="Relay", state="1"
    )

    await setup_integration(hass, mock_config_entry)

    assert (
        device_registry.async_get_device_by_identifier(
            module_identifier(MREL_MAC), mock_config_entry.entry_id
        )
        is None
    )
