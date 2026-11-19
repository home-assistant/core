"""Test the device type helper."""

from collections.abc import Callable, Generator
from enum import StrEnum
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import Platform, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    device_type,
    entity_registry as er,
)
from homeassistant.helpers.device_type import (
    BoundDeviceType,
    DeviceSlot,
    DeviceType,
    async_get_bound_device_type,
    get_device_type_class,
    get_device_type_classes,
)


class _NotADeviceClass(StrEnum):
    """An enum that is not a device class of an entity platform."""

    POWER = "power"


@pytest.fixture(autouse=True)
def isolated_vocabulary() -> Generator[None]:
    """Drop the device types a test defines when it ends."""
    with patch.dict(device_type._VOCABULARY):
        yield


@pytest.fixture
def device(hass: HomeAssistant, device_registry: dr.DeviceRegistry) -> dr.DeviceEntry:
    """Return a device to bind types to."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    return device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("test", "plug")}
    )


def test_generic() -> None:
    """Test the base class is the generic type."""
    assert DeviceType.type_id == "generic"
    assert DeviceType.ancestor_ids == ("generic",)
    assert DeviceType.declared_slots == {}
    assert get_device_type_class("generic") is DeviceType
    assert get_device_type_classes()["generic"] is DeviceType
    assert DeviceType().references == {}


@pytest.mark.parametrize(
    ("class_name", "type_id"),
    [
        ("WashingMachine", "washing_machine"),
        ("EVCharger", "ev_charger"),
        ("TV", "tv"),
        ("NAS", "nas"),
        ("AVReceiver", "av_receiver"),
        ("SmokeCoAlarm", "smoke_co_alarm"),
        ("Thermostat2", "thermostat2"),
    ],
)
def test_type_id_from_class_name(class_name: str, type_id: str) -> None:
    """Test the type id comes from the class name."""
    cls = type(class_name, (DeviceType,), {})
    assert cls.type_id == type_id
    assert cls.ancestor_ids == (type_id, "generic")
    assert get_device_type_class(type_id) is cls
    assert get_device_type_classes()[type_id] is cls


def test_type_id_override() -> None:
    """Test the type id can be set explicitly."""

    class Printer3D(DeviceType, type_id="printer_3d"):
        """A 3D printer."""

    assert Printer3D.type_id == "printer_3d"
    assert get_device_type_class("printer_3d") is Printer3D
    assert get_device_type_class("printer3_d") is None


@pytest.mark.parametrize("type_id", ["", "Printer", "3d_printer", "printer__3d"])
def test_invalid_type_id(type_id: str) -> None:
    """Test an invalid type id is refused."""
    with pytest.raises(ValueError, match="Invalid device type id"):

        class Printer(DeviceType, type_id=type_id):
            """A printer."""

    assert get_device_type_class(type_id) is None


@pytest.mark.parametrize("type_id", ["generic", "test_plug"])
def test_duplicate_type_id(type_id: str) -> None:
    """Test a type id can only be used once."""

    class TestPlug(DeviceType):
        """A plug."""

    registered = dict(get_device_type_classes())
    with pytest.raises(TypeError, match="is already used by"):

        class Other(DeviceType, type_id=type_id):
            """Another type with the same id."""

    assert get_device_type_classes() == registered


def test_unknown_type() -> None:
    """Test looking up an unknown type id."""
    assert get_device_type_class("not_a_type") is None


def test_slot_collection() -> None:
    """Test slots are collected along the MRO, parents first."""

    class TestPlug(DeviceType):
        """A plug."""

        outlet = DeviceSlot(Platform.SWITCH, required=True)
        power = DeviceSlot(SensorDeviceClass.POWER)

    class Mixin:
        """A plain mixin."""

    class TestPowerStrip(TestPlug, Mixin):
        """A power strip."""

        energy = DeviceSlot(SensorDeviceClass.ENERGY)
        power = DeviceSlot(SensorDeviceClass.POWER, required=True)

    assert list(TestPlug.declared_slots) == ["outlet", "power"]
    assert list(TestPowerStrip.declared_slots) == ["outlet", "power", "energy"]
    assert TestPowerStrip.declared_slots["outlet"] is TestPlug.outlet
    assert TestPowerStrip.declared_slots["power"] is TestPowerStrip.power
    assert TestPowerStrip.ancestor_ids == ("test_power_strip", "test_plug", "generic")

    assert TestPlug.outlet.slot_id == "outlet"
    assert TestPlug.outlet.defined_by is TestPlug
    assert TestPowerStrip.outlet.defined_by is TestPlug
    assert TestPowerStrip.power.defined_by is TestPowerStrip
    assert TestPowerStrip.energy.defined_by is TestPowerStrip
    assert TestPowerStrip.power.required


def test_slot_descriptor() -> None:
    """Test a slot is its declaration on the class, its references on instances."""

    class TestPlug(DeviceType):
        """A plug."""

        outlet = DeviceSlot(Platform.SWITCH, required=True)
        power = DeviceSlot(SensorDeviceClass.POWER)

    plug = TestPlug(outlet=(Platform.SWITCH, "outlet"))
    assert isinstance(TestPlug.outlet, DeviceSlot)
    assert plug.outlet == ((Platform.SWITCH, "outlet"),)
    assert plug.power == ()
    assert plug.references == {"outlet": ((Platform.SWITCH, "outlet"),)}

    with pytest.raises(AttributeError, match="outlet is a slot"):
        plug.outlet = ((Platform.SWITCH, "other"),)  # type: ignore[misc]
    with pytest.raises(TypeError):
        plug.references["outlet"] = ((Platform.SWITCH, "other"),)  # type: ignore[index]
    assert plug.outlet == ((Platform.SWITCH, "outlet"),)


@pytest.mark.parametrize(
    ("references", "expected"),
    [
        pytest.param({}, {}, id="nothing"),
        pytest.param(
            {"outlet": (Platform.SWITCH, "a")},
            {"outlet": ((Platform.SWITCH, "a"),)},
            id="reference",
        ),
        pytest.param(
            {
                "outlet": [(Platform.SWITCH, "a"), (Platform.LIGHT, "a")],
                "power": ((Platform.SENSOR, "c"),),
            },
            {
                "outlet": ((Platform.SWITCH, "a"), (Platform.LIGHT, "a")),
                "power": ((Platform.SENSOR, "c"),),
            },
            id="references",
        ),
        pytest.param(
            {
                "outlet": (
                    (Platform.SWITCH, "b"),
                    (Platform.SWITCH, "a"),
                    (Platform.SWITCH, "b"),
                )
            },
            {"outlet": ((Platform.SWITCH, "b"), (Platform.SWITCH, "a"))},
            id="duplicates",
        ),
        pytest.param(
            {"outlet": (), "power": (Platform.SENSOR, "c")},
            {"power": ((Platform.SENSOR, "c"),)},
            id="empty",
        ),
    ],
)
def test_instance_references(
    references: dict[str, Any], expected: dict[str, tuple[tuple[Platform, str], ...]]
) -> None:
    """Test an instance holds the references to the entities filling its slots."""

    class TestPlug(DeviceType):
        """A plug."""

        outlet = DeviceSlot(Platform.SWITCH, Platform.LIGHT, required=True)
        power = DeviceSlot(SensorDeviceClass.POWER)

    assert TestPlug(**references).references == expected


@pytest.mark.parametrize(
    ("references", "message"),
    [
        pytest.param(
            {"relay": (Platform.SWITCH, "a")},
            "TestPlug has no slot relay",
            id="unknown_slot",
        ),
        pytest.param({"outlet": "a"}, "Slot outlet takes a", id="unique_id"),
        pytest.param({"outlet": ("switch", "a")}, "Slot outlet takes a", id="domain"),
        pytest.param({"outlet": (Platform.SWITCH, 1)}, "Slot outlet takes a", id="int"),
        pytest.param({"outlet": None}, "Slot outlet takes a", id="none"),
        pytest.param(
            {"outlet": [(Platform.SWITCH, "a"), "b"]}, "Slot outlet takes a", id="mixed"
        ),
        pytest.param(
            {"outlet": (Platform.LIGHT, "a")},
            "Slot outlet takes entities of switch, not light",
            id="platform_not_accepted",
        ),
        pytest.param(
            {"power": (Platform.SWITCH, "a")},
            "Slot power takes entities of sensor, not switch",
            id="platform_of_other_slot",
        ),
    ],
)
def test_invalid_instance(references: dict[str, Any], message: str) -> None:
    """Test an instance only takes references its slots can be filled with."""

    class TestPlug(DeviceType):
        """A plug."""

        outlet = DeviceSlot(Platform.SWITCH, required=True)
        power = DeviceSlot(SensorDeviceClass.POWER)

    with pytest.raises(TypeError, match=message):
        TestPlug(**references)


def test_instance_equality() -> None:
    """Test instances are equal when their type and references are."""

    class TestPlug(DeviceType):
        """A plug."""

        outlet = DeviceSlot(Platform.SWITCH, required=True)

    class TestPowerStrip(TestPlug):
        """A power strip."""

    plug = TestPlug(outlet=(Platform.SWITCH, "a"))
    assert plug == TestPlug(outlet=[(Platform.SWITCH, "a")])
    assert hash(plug) == hash(TestPlug(outlet=[(Platform.SWITCH, "a")]))
    assert plug != TestPlug(outlet=(Platform.SWITCH, "b"))
    assert plug != TestPlug()
    assert plug != TestPowerStrip(outlet=(Platform.SWITCH, "a"))
    assert repr(plug) == "TestPlug(outlet=[('switch', 'a')])"


@pytest.mark.parametrize(
    ("entity_ids", "missing"),
    [
        ({}, {"outlet", "relay"}),
        ({"outlet": ("switch.plug",)}, {"relay"}),
        ({"power": ("sensor.power",)}, {"outlet", "relay"}),
        ({"outlet": ("switch.plug",), "relay": ("switch.relay",)}, set()),
    ],
)
def test_missing_required(
    device: dr.DeviceEntry, entity_ids: dict[str, tuple[str, ...]], missing: set[str]
) -> None:
    """Test the required slots without entities."""

    class TestPlug(DeviceType):
        """A plug."""

        outlet = DeviceSlot(Platform.SWITCH, required=True)
        relay = DeviceSlot(Platform.SWITCH, required=True)
        power = DeviceSlot(SensorDeviceClass.POWER)

    bound = BoundDeviceType(
        device,
        TestPlug(),
        {slot_id: entity_ids.get(slot_id, ()) for slot_id in TestPlug.declared_slots},
    )
    assert bound.missing_required == missing


@pytest.mark.parametrize(
    "name",
    ["references", "type_id", "ancestor_ids", "declared_slots"],
)
def test_reserved_slot_name(name: str) -> None:
    """Test a slot cannot use a name the instance uses itself."""
    with pytest.raises(TypeError, match="reserved by DeviceType"):
        type("TestPlug", (DeviceType,), {name: DeviceSlot(Platform.SWITCH)})
    assert get_device_type_class("test_plug") is None


@pytest.mark.parametrize(
    ("redeclared", "message"),
    [
        pytest.param(
            DeviceSlot(Platform.SWITCH, Platform.LIGHT, required=True),
            "cannot change what slot TestPlug.outlet accepts",
            id="more_accepts",
        ),
        pytest.param(
            DeviceSlot(Platform.LIGHT, required=True),
            "cannot change what slot TestPlug.outlet accepts",
            id="other_accepts",
        ),
        pytest.param(
            DeviceSlot(SwitchDeviceClass.SWITCH, required=True),
            "cannot change what slot TestPlug.outlet accepts",
            id="device_class_with_value_of_platform",
        ),
        pytest.param(
            DeviceSlot(Platform.SWITCH),
            "cannot make required slot TestPlug.outlet optional",
            id="optional",
        ),
    ],
)
def test_invalid_redeclaration(redeclared: DeviceSlot, message: str) -> None:
    """Test a redeclared slot may only make the inherited slot required."""

    class TestPlug(DeviceType):
        """A plug."""

        outlet = DeviceSlot(Platform.SWITCH, required=True)

    with pytest.raises(TypeError, match=message):
        type("TestPowerStrip", (TestPlug,), {"outlet": redeclared})
    assert get_device_type_class("test_power_strip") is None


def test_redeclaration_with_device_class_of_other_platform() -> None:
    """Test a redeclared slot cannot swap in an equal device class of another platform."""

    class TestPlug(DeviceType):
        """A plug."""

        power = DeviceSlot(SensorDeviceClass.POWER)

    with pytest.raises(TypeError, match="cannot change what slot TestPlug.power"):
        type(
            "TestPowerStrip",
            (TestPlug,),
            {"power": DeviceSlot(NumberDeviceClass.POWER)},
        )
    assert get_device_type_class("test_power_strip") is None


def test_redeclaration_ignores_accepts_order() -> None:
    """Test a redeclared slot may list what it accepts in another order."""

    class TestPlug(DeviceType):
        """A plug."""

        outlet = DeviceSlot(Platform.SWITCH, Platform.LIGHT)

    class TestPowerStrip(TestPlug):
        """A power strip."""

        outlet = DeviceSlot(Platform.LIGHT, Platform.SWITCH, required=True)

    assert TestPowerStrip.declared_slots["outlet"].required


def test_slot_overridden_by_non_slot() -> None:
    """Test a subclass cannot replace an inherited slot with something else."""

    class TestPlug(DeviceType):
        """A plug."""

        outlet = DeviceSlot(Platform.SWITCH)

    with pytest.raises(TypeError, match="overrides slot outlet of TestPlug"):
        type("TestPowerStrip", (TestPlug,), {"outlet": None})


def test_slot_reused() -> None:
    """Test one slot declaration cannot be used under two names."""
    slot = DeviceSlot(Platform.SWITCH)
    with pytest.raises(TypeError, match="cannot also be"):
        type("TestPlug", (DeviceType,), {"outlet": slot, "relay": slot})


@pytest.mark.parametrize(
    ("accepts", "message"),
    [
        pytest.param((), "must accept at least one", id="nothing"),
        pytest.param(("switch",), "not 'switch'", id="string"),
        pytest.param(
            (_NotADeviceClass.POWER,),
            "not a device class of an entity platform",
            id="foreign_enum",
        ),
        pytest.param(
            (UnitOfPower.WATT,),
            "not a device class of an entity platform",
            id="core_enum",
        ),
        pytest.param(
            (SensorStateClass.MEASUREMENT,),
            "not a device class of an entity platform",
            id="platform_enum",
        ),
    ],
)
def test_invalid_accepts(accepts: tuple[object, ...], message: str) -> None:
    """Test a slot accepts only platforms and device classes."""
    with pytest.raises(TypeError, match=message):
        DeviceSlot(*accepts)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("accepts", "domain", "device_class", "expected"),
    [
        ((Platform.SWITCH,), "switch", None, True),
        ((Platform.SWITCH,), "switch", "outlet", True),
        ((Platform.SWITCH,), "light", None, False),
        ((SwitchDeviceClass.OUTLET,), "switch", "outlet", True),
        ((SwitchDeviceClass.OUTLET,), "switch", None, False),
        ((SwitchDeviceClass.OUTLET,), "switch", "switch", False),
        ((SwitchDeviceClass.OUTLET,), "light", "outlet", False),
        ((SensorDeviceClass.POWER,), "sensor", "power", True),
        ((SensorDeviceClass.POWER,), "number", "power", False),
        ((BinarySensorDeviceClass.DOOR,), "binary_sensor", "door", True),
        ((BinarySensorDeviceClass.DOOR,), "cover", "door", False),
        ((Platform.NUMBER, SensorDeviceClass.POWER), "number", "power", True),
        ((Platform.NUMBER, SensorDeviceClass.POWER), "sensor", "power", True),
        ((Platform.NUMBER, SensorDeviceClass.POWER), "sensor", "energy", False),
    ],
)
def test_accepts_entity(
    accepts: tuple[Platform | StrEnum, ...],
    domain: str,
    device_class: str | None,
    expected: bool,
) -> None:
    """Test which entities fit a slot."""
    slot = DeviceSlot(*accepts)
    assert slot.accepts == accepts
    assert slot.accepts_entity(domain, device_class) is expected


@pytest.mark.parametrize(
    ("accepts", "entity_domains"),
    [
        ((Platform.SWITCH,), ("switch",)),
        ((SensorDeviceClass.POWER, SensorDeviceClass.ENERGY), ("sensor",)),
        ((Platform.NUMBER, SensorDeviceClass.POWER), ("number", "sensor")),
        (
            (SensorDeviceClass.POWER, Platform.NUMBER, Platform.SENSOR),
            ("sensor", "number"),
        ),
    ],
)
def test_entity_domains(
    accepts: tuple[Platform | StrEnum, ...], entity_domains: tuple[str, ...]
) -> None:
    """Test the entity domains a slot accepts entities of."""
    assert DeviceSlot(*accepts).entity_domains == entity_domains


def test_slot_outside_device_type() -> None:
    """Test a slot can only be declared on a device type."""
    with pytest.raises(
        TypeError, match="Entity.outlet must be declared on a DeviceType"
    ):

        class Entity:
            """Not a device type."""

            outlet = DeviceSlot(Platform.SWITCH)


@pytest.fixture
def plug_type() -> type[DeviceType]:
    """Return a plug type to type devices with."""

    class TestPlug(DeviceType):
        """A plug."""

        outlet = DeviceSlot(Platform.SWITCH, required=True)
        power = DeviceSlot(SensorDeviceClass.POWER)
        status = DeviceSlot(Platform.LIGHT, Platform.BINARY_SENSOR)

    return TestPlug


def _slot_entity_ids(
    hass: HomeAssistant, device_id: str
) -> dict[str, tuple[str, ...]] | None:
    """Return the entity ids in the slots of a device, None if it does not exist."""
    if (bound := async_get_bound_device_type(hass, device_id)) is None:
        return None
    return dict(bound.entity_ids)


def _add_entity(
    entity_registry: er.EntityRegistry,
    domain: str,
    unique_id: str,
    platform: str = "test",
    **kwargs: Any,
) -> er.RegistryEntry:
    """Add an entity with its unique id as object id."""
    return entity_registry.async_get_or_create(
        domain, platform, unique_id, suggested_object_id=unique_id, **kwargs
    )


@pytest.mark.parametrize(
    "original_device_type",
    [
        pytest.param(None, id="untyped"),
        pytest.param("not_a_type", id="unknown_type"),
    ],
)
@pytest.mark.usefixtures("plug_type")
def test_async_get_bound_device_type_generic(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device: dr.DeviceEntry,
    original_device_type: str | None,
) -> None:
    """Test a device without a known type is of the generic type."""
    _add_entity(entity_registry, "switch", "outlet")
    device = device_registry._async_update_device(
        device.id,
        original_device_type=original_device_type,
        original_device_slots={"outlet": (("switch", "outlet"),)},
    )

    bound = async_get_bound_device_type(hass, device.id)

    assert bound == BoundDeviceType(device, DeviceType(), {})
    assert type(bound.device_type) is DeviceType


@pytest.mark.usefixtures("plug_type")
def test_async_get_bound_device_type_child_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    device: dr.DeviceEntry,
) -> None:
    """Test a child device is of the generic type, even below a typed device."""
    device_registry._async_update_device(
        device.id,
        original_device_type="test_plug",
        original_device_slots={"outlet": (("switch", "outlet"),)},
    )
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=device.config_entry_id,
        identifiers={("test", "outlet")},
        parent_device_id=device.id,
    )

    bound = async_get_bound_device_type(hass, child_device.id)

    assert bound == BoundDeviceType(child_device, DeviceType(), {})
    assert type(bound.device_type) is DeviceType


def test_async_get_bound_device_type_missing_device(hass: HomeAssistant) -> None:
    """Test there is no type for a device which does not exist."""
    assert async_get_bound_device_type(hass, "not_a_device") is None


def test_async_get_bound_device_type_binding(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device: dr.DeviceEntry,
    plug_type: type[DeviceType],
) -> None:
    """Test the slots are bound to the entities with the stored unique ids."""
    for domain, unique_id, platform, kwargs in (
        ("switch", "b", "test", {}),
        ("switch", "a", "test", {"disabled_by": er.RegistryEntryDisabler.USER}),
        ("sensor", "power", "test", {"original_device_class": "power"}),
        ("sensor", "other_power", "other", {"original_device_class": "power"}),
        ("sensor", "user_power", "test", {"original_device_class": "energy"}),
        ("light", "status", "test", {}),
        ("binary_sensor", "status_sensor", "test", {}),
        ("switch", "status", "test", {}),
        ("binary_sensor", "b", "test", {}),
    ):
        _add_entity(entity_registry, domain, unique_id, platform, **kwargs)
    entity_registry.async_update_entity("sensor.user_power", device_class="power")
    device = device_registry._async_update_device(
        device.id,
        original_device_type="test_plug",
        original_device_slots={
            "outlet": (
                ("switch", "b"),
                ("switch", "not_registered"),
                ("switch", "a"),
                ("switch", "b"),
            ),
            "power": (
                ("sensor", "user_power"),
                ("sensor", "other_power"),
                ("sensor", "power"),
            ),
            # The switch is not referenced as a platform the slot takes
            "status": (
                ("binary_sensor", "status_sensor"),
                ("light", "status"),
                ("switch", "status"),
            ),
            "not_a_slot": (("switch", "b"),),
        },
    )

    bound = async_get_bound_device_type(hass, device.id)

    assert bound is not None
    assert bound.device is device
    assert bound.device_type == plug_type(
        outlet=[
            (Platform.SWITCH, "b"),
            (Platform.SWITCH, "not_registered"),
            (Platform.SWITCH, "a"),
        ],
        power=[
            (Platform.SENSOR, "user_power"),
            (Platform.SENSOR, "other_power"),
            (Platform.SENSOR, "power"),
        ],
        status=[(Platform.BINARY_SENSOR, "status_sensor"), (Platform.LIGHT, "status")],
    )
    assert bound.entity_ids == {
        "outlet": ("switch.b", "switch.a"),
        "power": ("sensor.user_power", "sensor.power"),
        "status": ("binary_sensor.status_sensor", "light.status"),
    }
    assert bound.missing_required == frozenset()
    assert async_get_bound_device_type(hass, device.id) is bound


@pytest.mark.parametrize(
    ("original_device_slots", "missing"),
    [
        pytest.param({}, {"outlet"}, id="no_slots"),
        pytest.param(
            {"outlet": (("switch", "not_registered"),)}, {"outlet"}, id="unresolved"
        ),
        pytest.param({"power": (("sensor", "outlet"),)}, {"outlet"}, id="other_slot"),
        pytest.param({"outlet": (("switch", "outlet"),)}, set(), id="filled"),
    ],
)
@pytest.mark.usefixtures("plug_type")
def test_async_get_bound_device_type_missing_required(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device: dr.DeviceEntry,
    original_device_slots: dict[str, tuple[tuple[str, str], ...]],
    missing: set[str],
) -> None:
    """Test the required slots without an entity of a resolved device."""
    _add_entity(entity_registry, "switch", "outlet")
    device_registry._async_update_device(
        device.id,
        original_device_type="test_plug",
        original_device_slots=original_device_slots,
    )

    bound = async_get_bound_device_type(hass, device.id)

    assert bound is not None
    assert bound.missing_required == missing


@pytest.mark.usefixtures("plug_type")
def test_async_get_bound_device_type_config_entry_gone(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device: dr.DeviceEntry,
) -> None:
    """Test nothing resolves when the config entry of the device is gone."""
    _add_entity(entity_registry, "switch", "outlet")
    device_registry._async_update_device(
        device.id,
        original_device_type="test_plug",
        original_device_slots={"outlet": (("switch", "outlet"),)},
    )

    with patch.object(hass.config_entries, "async_get_entry", return_value=None):
        assert _slot_entity_ids(hass, device.id) == {
            "outlet": (),
            "power": (),
            "status": (),
        }


@pytest.mark.usefixtures("plug_type")
def test_async_get_bound_device_type_no_fit(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device: dr.DeviceEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an entity that does not fit its slot is left out, warned about once."""
    _add_entity(entity_registry, "sensor", "energy", original_device_class="energy")
    _add_entity(entity_registry, "sensor", "power", original_device_class="power")
    entity_registry.async_update_entity("sensor.power", device_class="energy")
    device_registry._async_update_device(
        device.id,
        original_device_type="test_plug",
        original_device_slots={"power": (("sensor", "energy"), ("sensor", "power"))},
    )

    assert _slot_entity_ids(hass, device.id) == {
        "outlet": (),
        "power": (),
        "status": (),
    }
    assert (
        "Entity sensor.energy with unique ID energy does not fit slot power of device"
        f" type test_plug of device {device.id}, which accepts power"
    ) in caplog.text
    assert caplog.text.count("does not fit") == 2

    # Rebuild the cached bound device type
    device_registry.async_update_device(device.id, name="Plug")
    assert _slot_entity_ids(hass, device.id) == {
        "outlet": (),
        "power": (),
        "status": (),
    }
    assert caplog.text.count("does not fit") == 2


def _update_device_slots(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_id: str,
) -> None:
    device_registry._async_update_device(
        device_id, original_device_slots={"power": (("sensor", "power"),)}
    )


def _remove_device(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_id: str,
) -> None:
    device_registry.async_remove_device(device_id)


def _create_entity(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_id: str,
) -> None:
    _add_entity(entity_registry, "switch", "second")


def _remove_entity(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_id: str,
) -> None:
    entity_registry.async_remove("switch.outlet")


def _rename_entity(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_id: str,
) -> None:
    entity_registry.async_update_entity("switch.outlet", new_entity_id="switch.renamed")


def _migrate_unique_id(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_id: str,
) -> None:
    entity_registry.async_update_entity("switch.outlet", new_unique_id="other_outlet")


def _migrate_platform(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_id: str,
) -> None:
    entity_registry.async_update_entity_platform("switch.outlet", "other")


def _change_device_class(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_id: str,
) -> None:
    entity_registry.async_update_entity("sensor.power", device_class="energy")


def _change_original_device_class(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_id: str,
) -> None:
    entity_registry.async_update_entity("sensor.power", original_device_class="energy")


@pytest.mark.parametrize(
    ("change", "slots", "other_slots"),
    [
        pytest.param(
            _update_device_slots,
            {"outlet": (), "power": ("sensor.power",), "status": ()},
            {"outlet": (), "power": (), "status": ()},
            id="device_updated",
        ),
        pytest.param(
            _remove_device,
            None,
            {"outlet": (), "power": (), "status": ()},
            id="device_removed",
        ),
        pytest.param(
            _create_entity,
            {
                "outlet": ("switch.outlet", "switch.second"),
                "power": ("sensor.power",),
                "status": (),
            },
            {"outlet": (), "power": (), "status": ()},
            id="entity_created",
        ),
        pytest.param(
            _remove_entity,
            {"outlet": (), "power": ("sensor.power",), "status": ()},
            {"outlet": (), "power": (), "status": ()},
            id="entity_removed",
        ),
        pytest.param(
            _rename_entity,
            {"outlet": ("switch.renamed",), "power": ("sensor.power",), "status": ()},
            {"outlet": (), "power": (), "status": ()},
            id="entity_renamed",
        ),
        pytest.param(
            _migrate_unique_id,
            {"outlet": (), "power": ("sensor.power",), "status": ()},
            {"outlet": ("switch.outlet",), "power": (), "status": ()},
            id="unique_id_migrated",
        ),
        pytest.param(
            _migrate_platform,
            {"outlet": (), "power": ("sensor.power",), "status": ()},
            {"outlet": (), "power": (), "status": ()},
            id="platform_migrated",
        ),
        pytest.param(
            _change_device_class,
            {"outlet": ("switch.outlet",), "power": (), "status": ()},
            {"outlet": (), "power": (), "status": ()},
            id="device_class_changed",
        ),
        pytest.param(
            _change_original_device_class,
            {"outlet": ("switch.outlet",), "power": (), "status": ()},
            {"outlet": (), "power": (), "status": ()},
            id="original_device_class_changed",
        ),
    ],
)
def test_async_get_bound_device_type_invalidation(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device: dr.DeviceEntry,
    plug_type: type[DeviceType],
    change: Callable[[dr.DeviceRegistry, er.EntityRegistry, str], None],
    slots: dict[str, tuple[str, ...]] | None,
    other_slots: dict[str, tuple[str, ...]],
) -> None:
    """Test a registry change drops the cached bound device types it affects."""
    device_registry._async_update_device(
        device.id,
        original_device_type="test_plug",
        original_device_slots={
            "outlet": (("switch", "outlet"), ("switch", "second")),
            "power": (("sensor", "power"),),
        },
    )
    other_device = device_registry.async_get_or_create(
        config_entry_id=device.config_entry_id,
        identifiers={("test", "other")},
        device_type=plug_type(outlet=(Platform.SWITCH, "other_outlet")),
    )
    _add_entity(entity_registry, "switch", "outlet", device_id=device.id)
    _add_entity(
        entity_registry,
        "sensor",
        "power",
        device_id=device.id,
        original_device_class="power",
    )
    assert _slot_entity_ids(hass, device.id) == {
        "outlet": ("switch.outlet",),
        "power": ("sensor.power",),
        "status": (),
    }
    assert _slot_entity_ids(hass, other_device.id) == {
        "outlet": (),
        "power": (),
        "status": (),
    }

    change(device_registry, entity_registry, device.id)

    assert _slot_entity_ids(hass, device.id) == slots
    assert _slot_entity_ids(hass, other_device.id) == other_slots


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"name": "Outlet"}, id="name"),
        pytest.param({"icon": "mdi:power-socket"}, id="icon"),
        pytest.param({"device_id": None}, id="device_id"),
        pytest.param({"disabled_by": er.RegistryEntryDisabler.USER}, id="disabled_by"),
    ],
)
@pytest.mark.usefixtures("plug_type")
def test_async_get_bound_device_type_kept(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device: dr.DeviceEntry,
    changes: dict[str, Any],
) -> None:
    """Test an entity update that cannot change the resolution keeps the cache."""
    device_registry._async_update_device(
        device.id,
        original_device_type="test_plug",
        original_device_slots={"outlet": (("switch", "outlet"),)},
    )
    _add_entity(entity_registry, "switch", "outlet", device_id=device.id)
    bound = async_get_bound_device_type(hass, device.id)

    entity_registry.async_update_entity("switch.outlet", **changes)

    assert async_get_bound_device_type(hass, device.id) is bound
