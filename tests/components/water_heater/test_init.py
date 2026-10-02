"""The tests for the water heater component."""

from collections.abc import Callable
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, call

import probatio
from propcache.api import cached_property
import pytest

from homeassistant.components.water_heater import (
    DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    WaterHeaterCapabilityAttribute,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    WaterHeaterStateAttribute,
)
from homeassistant.components.water_heater.services import (
    SET_TEMPERATURE_SCHEMA,
    _async_service_temperature_set,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    async_mock_service,
    mock_integration,
    mock_platform,
    setup_test_component_platform,
)


async def test_set_temp_schema_no_req(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the set temperature schema with missing required data."""
    domain = "climate"
    service = "test_set_temperature"
    schema = cv.make_entity_service_schema(SET_TEMPERATURE_SCHEMA)
    calls = async_mock_service(hass, domain, service, schema)

    data = {"hvac_mode": "off", "entity_id": ["climate.test_id"]}
    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(domain, service, data)
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_set_temp_schema(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the set temperature schema with ok required data."""
    domain = "water_heater"
    service = "test_set_temperature"
    schema = cv.make_entity_service_schema(SET_TEMPERATURE_SCHEMA)
    calls = async_mock_service(hass, domain, service, schema)

    data = {
        "temperature": 20.0,
        "operation_mode": "gas",
        "entity_id": ["water_heater.test_id"],
    }
    await hass.services.async_call(domain, service, data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[-1].data == data


class MockWaterHeaterEntity(WaterHeaterEntity):
    """Mock water heater device to use in tests."""

    _attr_operation_list: list[str] | None = ["off", "heat_pump", "gas"]
    _attr_operation = "heat_pump"
    _attr_supported_features = WaterHeaterEntityFeature.ON_OFF
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS

    set_operation_mode: MagicMock = MagicMock()


async def test_sync_turn_on(hass: HomeAssistant) -> None:
    """Test if async turn_on calls sync turn_on."""
    water_heater = MockWaterHeaterEntity()
    water_heater.hass = hass

    # Test with turn_on method defined
    water_heater.turn_on = MagicMock()
    await water_heater.async_turn_on()

    assert water_heater.turn_on.call_count == 1

    # Test with async_turn_on method defined
    water_heater.async_turn_on = AsyncMock()
    await water_heater.async_turn_on()

    assert water_heater.async_turn_on.call_count == 1


async def test_sync_turn_off(hass: HomeAssistant) -> None:
    """Test if async turn_off calls sync turn_off."""
    water_heater = MockWaterHeaterEntity()
    water_heater.hass = hass

    # Test with turn_off method defined
    water_heater.turn_off = MagicMock()
    await water_heater.async_turn_off()

    assert water_heater.turn_off.call_count == 1

    # Test with async_turn_off method defined
    water_heater.async_turn_off = AsyncMock()
    await water_heater.async_turn_off()

    assert water_heater.async_turn_off.call_count == 1


async def test_operation_mode_validation(
    hass: HomeAssistant, config_flow_fixture: None
) -> None:
    """Test operation mode validation."""
    water_heater_entity = MockWaterHeaterEntity()
    water_heater_entity.hass = hass
    water_heater_entity._attr_name = "test"
    water_heater_entity._attr_unique_id = "test"
    water_heater_entity._attr_supported_features = (
        WaterHeaterEntityFeature.OPERATION_MODE
    )
    water_heater_entity._attr_current_operation = None
    water_heater_entity._attr_operation_list = None

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.WATER_HEATER]
        )
        return True

    async def async_setup_entry_water_heater_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Set up test water_heater platform via config entry."""
        async_add_entities([water_heater_entity])

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=async_setup_entry_init,
        ),
        built_in=False,
    )
    mock_platform(
        hass,
        "test.water_heater",
        MockPlatform(async_setup_entry=async_setup_entry_water_heater_platform),
    )

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    data = {"entity_id": "water_heater.test", "operation_mode": "test"}

    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_OPERATION_MODE, data, blocking=True
        )
    assert (
        str(exc.value) == "Operation mode test is not valid for water_heater.test. "
        "The operation list is not defined"
    )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "operation_list_not_defined"
    assert exc.value.translation_placeholders == {
        "entity_id": "water_heater.test",
        "operation_mode": "test",
    }

    water_heater_entity._attr_operation_list = ["gas", "eco"]
    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_OPERATION_MODE, data, blocking=True
        )
    assert (
        str(exc.value) == "Operation mode test is not valid for water_heater.test. "
        "Valid operation modes are: gas, eco"
    )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "not_valid_operation_mode"
    assert exc.value.translation_placeholders == {
        "entity_id": "water_heater.test",
        "operation_mode": "test",
        "operation_list": "gas, eco",
    }

    data = {"entity_id": "water_heater.test", "operation_mode": "eco"}
    await hass.services.async_call(
        DOMAIN, SERVICE_SET_OPERATION_MODE, data, blocking=True
    )
    await hass.async_block_till_done()
    water_heater_entity.set_operation_mode.assert_has_calls([mock.call("eco")])


class MockShimWaterHeaterEntity(MockWaterHeaterEntity):
    """Water heater entity with a wrong native baseline.

    The deprecated members under test must win over the baseline values.
    """

    _attr_native_current_temperature = 99.0
    _attr_native_target_temperature = 99.0
    _attr_native_target_temperature_high = 99.0
    _attr_native_target_temperature_low = 99.0


def _legacy_property(member: str, value: Any) -> type[MockShimWaterHeaterEntity]:
    """Return a subclass overriding the deprecated member with a plain property."""

    return type(
        "LegacyPropertyWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {"__module__": __name__, member: property(lambda self: value)},
    )


def _legacy_cached_property(member: str, value: Any) -> type[MockShimWaterHeaterEntity]:
    """Return a subclass overriding the deprecated member with a cached property."""

    return type(
        "LegacyCachedPropertyWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {"__module__": __name__, member: cached_property(lambda self: value)},
    )


def _legacy_class_value(member: str, value: Any) -> type[MockShimWaterHeaterEntity]:
    """Return a subclass overriding the deprecated member with a class attribute."""

    return type(
        "LegacyClassValueWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {"__module__": __name__, member: value},
    )


def _legacy_class_attribute(member: str, value: Any) -> type[MockShimWaterHeaterEntity]:
    """Return a subclass setting the deprecated _attr_ member at class level."""

    return type(
        "LegacyClassAttributeWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {"__module__": __name__, f"_attr_{member}": value},
    )


def _legacy_instance_attribute(
    member: str, value: Any
) -> type[MockShimWaterHeaterEntity]:
    """Return a subclass setting the deprecated _attr_ member at runtime."""

    def __init__(self: MockShimWaterHeaterEntity) -> None:
        setattr(self, f"_attr_{member}", value)

    return type(
        "LegacyInstanceAttributeWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {"__module__": __name__, "__init__": __init__},
    )


def _legacy_instance_property(
    member: str, value: Any
) -> type[MockShimWaterHeaterEntity]:
    """Return a subclass assigning the deprecated member on the instance."""

    def __init__(self: MockShimWaterHeaterEntity) -> None:
        setattr(self, member, value)

    return type(
        "LegacyInstancePropertyWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {"__module__": __name__, "__init__": __init__},
    )


def _legacy_slots(member: str, value: Any) -> type[MockShimWaterHeaterEntity]:
    """Return a subclass declaring the deprecated member in __slots__."""

    def __init__(self: MockShimWaterHeaterEntity) -> None:
        setattr(self, member, value)

    return type(
        "LegacySlotsWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {"__module__": __name__, "__slots__": (member,), "__init__": __init__},
    )


def _count_warnings(caplog: pytest.LogCaptureFixture, warning: str) -> int:
    """Return the number of logged records mentioning the warning."""
    return sum(warning in record.getMessage() for record in caplog.records)


DEPRECATED_MEMBERS = [
    pytest.param(
        "current_temperature",
        21.4,
        WaterHeaterStateAttribute.CURRENT_TEMPERATURE,
        21.4,
        id="current_temperature",
    ),
    pytest.param(
        "target_temperature",
        21.4,
        WaterHeaterStateAttribute.TARGET_TEMPERATURE,
        21.4,
        id="target_temperature",
    ),
    pytest.param(
        "target_temperature_high",
        21.4,
        WaterHeaterStateAttribute.TARGET_TEMP_HIGH,
        21.4,
        id="target_temperature_high",
    ),
    pytest.param(
        "target_temperature_low",
        21.4,
        WaterHeaterStateAttribute.TARGET_TEMP_LOW,
        21.4,
        id="target_temperature_low",
    ),
    pytest.param(
        "temperature_unit",
        UnitOfTemperature.FAHRENHEIT,
        # The unit is not a state attribute, it converts the published temperatures
        WaterHeaterStateAttribute.CURRENT_TEMPERATURE,
        37.2,
        id="temperature_unit",
    ),
]

DEPRECATED_MEMBER_WRITES = [
    pytest.param("current_temperature", 21.4, 12.3, id="current_temperature"),
    pytest.param("target_temperature", 21.4, 12.3, id="target_temperature"),
    pytest.param("target_temperature_high", 21.4, 12.3, id="target_temperature_high"),
    pytest.param("target_temperature_low", 21.4, 12.3, id="target_temperature_low"),
    pytest.param(
        "temperature_unit",
        UnitOfTemperature.FAHRENHEIT,
        UnitOfTemperature.KELVIN,
        id="temperature_unit",
    ),
]

DEPRECATED_MEMBER_VALUES = [
    pytest.param("current_temperature", 21.4, id="current_temperature"),
    pytest.param("target_temperature", 21.4, id="target_temperature"),
    pytest.param("target_temperature_high", 21.4, id="target_temperature_high"),
    pytest.param("target_temperature_low", 21.4, id="target_temperature_low"),
    pytest.param(
        "temperature_unit", UnitOfTemperature.FAHRENHEIT, id="temperature_unit"
    ),
]

DEPRECATED_SHAPES = [
    pytest.param(
        _legacy_property,
        "is overriding the deprecated {member} property",
        0,
        id="property",
    ),
    pytest.param(
        _legacy_cached_property,
        "is overriding the deprecated {member} property",
        0,
        id="cached-property",
    ),
    pytest.param(
        _legacy_class_value,
        "is overriding the deprecated {member} property",
        0,
        id="class-value",
    ),
    pytest.param(
        _legacy_class_attribute,
        "is setting the deprecated _attr_{member} class attribute",
        1,
        id="class-attribute",
    ),
    pytest.param(
        _legacy_instance_attribute,
        "is setting the deprecated _attr_{member} attribute",
        1,
        id="instance-attribute",
    ),
    pytest.param(
        _legacy_instance_property,
        "is setting the deprecated {member} attribute",
        1,
        id="instance-property",
    ),
    pytest.param(
        _legacy_slots,
        "is declaring the deprecated {member} in __slots__",
        0,
        id="slots",
    ),
]


@pytest.mark.parametrize(
    ("unit_system", "native_unit", "expected_temperature"),
    [
        pytest.param(
            METRIC_SYSTEM,
            UnitOfTemperature.CELSIUS,
            21.4,
            id="metric-native-celsius",
        ),
        pytest.param(
            METRIC_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            -5.9,
            id="metric-native-fahrenheit",
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.CELSIUS,
            71,
            id="us-customary-native-celsius",
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            21,
            id="us-customary-native-fahrenheit",
        ),
    ],
)
async def test_native_temperature_unit_conversion(
    hass: HomeAssistant,
    register_test_integration: MockConfigEntry,
    unit_system: UnitSystem,
    native_unit: UnitOfTemperature,
    expected_temperature: float,
) -> None:
    """Test the native unit converts the published temperatures."""
    hass.config.units = unit_system
    entity = MockWaterHeaterEntity()
    entity._attr_name = "Test"
    entity._attr_unique_id = "unique_water_heater_test"
    entity._attr_native_temperature_unit = native_unit
    entity._attr_native_current_temperature = 21.4

    setup_test_component_platform(
        hass, DOMAIN, entities=[entity], from_config_entry=True
    )
    await hass.config_entries.async_setup(register_test_integration.entry_id)
    await hass.async_block_till_done()

    assert entity.native_temperature_unit == native_unit
    # The deprecated alias keeps returning the native unit, not the display unit
    assert entity.temperature_unit == native_unit

    state = hass.states.get("water_heater.test")
    assert (
        state.attributes[WaterHeaterStateAttribute.CURRENT_TEMPERATURE]
        == expected_temperature
    )


async def test_native_temperature_unit_property(hass: HomeAssistant) -> None:
    """Test an entity may provide the native unit through a property."""

    class NativePropertyWaterHeaterEntity(MockWaterHeaterEntity):
        """Water heater entity overriding native_temperature_unit."""

        @property
        def native_temperature_unit(self) -> str:
            """Return the unit of measurement the entity reports temperatures in."""
            return UnitOfTemperature.FAHRENHEIT

    entity = NativePropertyWaterHeaterEntity()
    entity.hass = hass
    entity._attr_native_current_temperature = 68.0

    assert entity.native_temperature_unit == UnitOfTemperature.FAHRENHEIT
    # The deprecated alias dispatches to the override instead of reading the
    # storage the override bypasses
    assert entity.temperature_unit == UnitOfTemperature.FAHRENHEIT
    state_attributes = entity.state_attributes
    assert state_attributes[WaterHeaterStateAttribute.CURRENT_TEMPERATURE] == 20.0


@pytest.mark.parametrize(
    ("member", "value"),
    [
        pytest.param("current_temperature", 21.4, id="current_temperature"),
        pytest.param("target_temperature", 21.4, id="target_temperature"),
        pytest.param("target_temperature_high", 21.4, id="target_temperature_high"),
        pytest.param("target_temperature_low", 21.4, id="target_temperature_low"),
        pytest.param(
            "temperature_unit", UnitOfTemperature.FAHRENHEIT, id="temperature_unit"
        ),
    ],
)
async def test_native_attribute_invalidates_cache(
    hass: HomeAssistant, member: str, value: Any
) -> None:
    """Test writing a native _attr_ invalidates its cached property."""
    entity = MockShimWaterHeaterEntity()
    entity.hass = hass

    assert getattr(entity, f"native_{member}") != value

    setattr(entity, f"_attr_native_{member}", value)

    assert getattr(entity, f"native_{member}") == value


@pytest.mark.parametrize(
    (
        "unit_system",
        "native_unit",
        "expected_min_temp",
        "expected_max_temp",
        "expected_capability_min_temp",
        "expected_capability_max_temp",
    ),
    [
        pytest.param(
            METRIC_SYSTEM,
            UnitOfTemperature.CELSIUS,
            43.33,
            60.0,
            43.3,
            60.0,
            id="metric-native-celsius",
        ),
        pytest.param(
            METRIC_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            110,
            140,
            43.3,
            60.0,
            id="metric-native-fahrenheit",
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.CELSIUS,
            43.33,
            60.0,
            110,
            140,
            id="us-customary-native-celsius",
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            110,
            140,
            110,
            140,
            id="us-customary-native-fahrenheit",
        ),
    ],
)
async def test_default_min_max_temp_use_native_unit(
    hass: HomeAssistant,
    unit_system: UnitSystem,
    native_unit: UnitOfTemperature,
    expected_min_temp: float,
    expected_max_temp: float,
    expected_capability_min_temp: float,
    expected_capability_max_temp: float,
) -> None:
    """Test the default min and max temperature are in the native unit."""
    hass.config.units = unit_system
    entity = MockWaterHeaterEntity()
    entity.hass = hass
    entity._attr_native_temperature_unit = native_unit

    assert entity.min_temp == pytest.approx(expected_min_temp, abs=0.01)
    assert entity.max_temp == pytest.approx(expected_max_temp, abs=0.01)

    capability_attributes = entity.capability_attributes
    assert (
        capability_attributes[WaterHeaterCapabilityAttribute.MIN_TEMP]
        == expected_capability_min_temp
    )
    assert (
        capability_attributes[WaterHeaterCapabilityAttribute.MAX_TEMP]
        == expected_capability_max_temp
    )


@pytest.mark.parametrize(
    ("unit_system", "native_unit", "service_temperature", "expected_temperature"),
    [
        pytest.param(
            METRIC_SYSTEM,
            UnitOfTemperature.CELSIUS,
            20.0,
            20.0,
            id="metric-native-celsius",
        ),
        pytest.param(
            METRIC_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            20.0,
            68.0,
            id="metric-native-fahrenheit",
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.CELSIUS,
            68.0,
            20.0,
            id="us-customary-native-celsius",
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            68.0,
            68.0,
            id="us-customary-native-fahrenheit",
        ),
    ],
)
async def test_set_temperature_service_converts_to_native_unit(
    hass: HomeAssistant,
    unit_system: UnitSystem,
    native_unit: UnitOfTemperature,
    service_temperature: float,
    expected_temperature: float,
) -> None:
    """Test the set temperature service converts to the entity native unit."""
    hass.config.units = unit_system
    entity = MockWaterHeaterEntity()
    entity.hass = hass
    entity._attr_native_temperature_unit = native_unit
    entity.async_set_temperature = AsyncMock()

    await _async_service_temperature_set(
        entity,
        ServiceCall(
            hass,
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: service_temperature},
        ),
    )

    assert entity.async_set_temperature.mock_calls == [
        call(temperature=expected_temperature)
    ]


@pytest.mark.parametrize(
    ("member", "native_value", "state_attribute", "expected_state_value"),
    DEPRECATED_MEMBERS,
)
@pytest.mark.parametrize(
    ("entity_factory", "expected_warning", "expected_reads"), DEPRECATED_SHAPES
)
async def test_deprecated_temperature_member(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    entity_factory: Callable[[str, Any], type[MockShimWaterHeaterEntity]],
    expected_warning: str,
    expected_reads: int,
    member: str,
    native_value: Any,
    state_attribute: str,
    expected_state_value: Any,
) -> None:
    """Test a deprecated temperature member still feeds the native property."""
    entity = entity_factory(member, native_value)()
    entity.hass = hass

    assert getattr(entity, f"native_{member}") == native_value
    # The deprecated member is a pure alias, it returns the native value unconverted
    assert getattr(entity, member) == native_value
    assert entity.state_attributes[state_attribute] == expected_state_value

    entity_class = type(entity)
    assert (
        f"{entity_class.__module__}::{entity_class.__name__} "
        f"{expected_warning.format(member=member)}, "
        "this will be unsupported from Home Assistant 2027.11, "
        f"use WaterHeaterEntity.native_{member} instead"
    ) in caplog.text
    assert _count_warnings(caplog, "is reading the deprecated") == expected_reads


async def test_deprecated_temperature_unit_drives_conversion(
    hass: HomeAssistant,
) -> None:
    """Test the deprecated temperature_unit is used to convert for display."""
    entity = _legacy_property("temperature_unit", UnitOfTemperature.FAHRENHEIT)()
    entity.hass = hass
    entity._attr_native_current_temperature = 68.0

    assert entity.native_temperature_unit == UnitOfTemperature.FAHRENHEIT
    assert entity.min_temp == pytest.approx(110, abs=0.01)
    assert entity.max_temp == pytest.approx(140, abs=0.01)

    state_attributes = entity.state_attributes
    assert state_attributes[WaterHeaterStateAttribute.CURRENT_TEMPERATURE] == 20.0


@pytest.mark.parametrize(
    ("member", "first_value", "second_value"), DEPRECATED_MEMBER_WRITES
)
@pytest.mark.parametrize("prefix", ["", "_attr_"], ids=["property", "attribute"])
async def test_deprecated_temperature_member_setter(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    prefix: str,
    member: str,
    first_value: Any,
    second_value: Any,
) -> None:
    """Test writing a deprecated temperature member at runtime."""
    warning = f"is setting the deprecated {prefix}{member} attribute"
    entity = MockShimWaterHeaterEntity()
    entity.hass = hass

    setattr(entity, f"{prefix}{member}", first_value)

    assert getattr(entity, f"{prefix}{member}") == first_value
    assert getattr(entity, f"_attr_native_{member}") == first_value
    assert getattr(entity, f"native_{member}") == first_value
    assert caplog.text.count(warning) == 1

    setattr(entity, f"{prefix}{member}", second_value)

    assert getattr(entity, f"native_{member}") == second_value
    assert caplog.text.count(warning) == 1


@pytest.mark.parametrize(("member", "native_value"), DEPRECATED_MEMBER_VALUES)
@pytest.mark.parametrize("prefix", ["", "_attr_"], ids=["property", "attribute"])
async def test_deprecated_temperature_member_setter_reported_once_per_class(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    prefix: str,
    member: str,
    native_value: Any,
) -> None:
    """Test a deprecated write is reported once per class, not once per entity.

    A multi-zone integration builds one entity per zone from a single class, so a
    once-per-instance report is one log line per zone per setup.
    """
    warning = f"is setting the deprecated {prefix}{member} attribute"
    first = type(
        "FirstWriterWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {"__module__": __name__},
    )
    second = type(
        "SecondWriterWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {"__module__": __name__},
    )
    # A class attribute would be inherited, silencing a subclass of a reported class
    subclass = type(
        "SubclassWriterWaterHeaterEntity", (first,), {"__module__": __name__}
    )

    def write(entity_class: type[MockShimWaterHeaterEntity]) -> None:
        """Write the deprecated member on three fresh entities of the class."""
        for _ in range(3):
            entity = entity_class()
            entity.hass = hass
            setattr(entity, f"{prefix}{member}", native_value)

    write(first)

    assert f"{__name__}::FirstWriterWaterHeaterEntity {warning}" in caplog.text
    assert _count_warnings(caplog, warning) == 1

    write(second)

    assert f"{__name__}::SecondWriterWaterHeaterEntity {warning}" in caplog.text
    assert _count_warnings(caplog, warning) == 2

    write(subclass)

    assert f"{__name__}::SubclassWriterWaterHeaterEntity {warning}" in caplog.text
    assert _count_warnings(caplog, warning) == 3


@pytest.mark.parametrize(("member", "native_value"), DEPRECATED_MEMBER_VALUES)
@pytest.mark.parametrize(
    ("prefix", "kind"),
    [("", "property"), ("_attr_", "attribute")],
    ids=["property", "attribute"],
)
async def test_deprecated_temperature_member_read(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    prefix: str,
    kind: str,
    member: str,
    native_value: Any,
) -> None:
    """Test reading a deprecated temperature member is reported once per class."""
    warning = f"is reading the deprecated {prefix}{member} {kind}"
    entity_class = type(
        "MigratedWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {"__module__": __name__, f"_attr_native_{member}": native_value},
    )
    entity = entity_class()
    entity.hass = hass

    assert getattr(entity, f"{prefix}{member}") == native_value

    assert _count_warnings(caplog, warning) == 1
    # Serving the read must not report a read of the storage it is served from
    assert _count_warnings(caplog, "is reading the deprecated") == 1

    other = entity_class()
    other.hass = hass

    assert getattr(entity, f"{prefix}{member}") == native_value
    assert getattr(other, f"{prefix}{member}") == native_value

    assert _count_warnings(caplog, "is reading the deprecated") == 1


@pytest.mark.parametrize(("member", "native_value"), DEPRECATED_MEMBER_VALUES)
@pytest.mark.parametrize("prefix", ["", "_attr_"], ids=["property", "attribute"])
async def test_deprecated_temperature_member_write_not_reported_as_read(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    prefix: str,
    member: str,
    native_value: Any,
) -> None:
    """Test writing a deprecated temperature member does not report a read of it."""
    entity = type(
        "WriteOnlyWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {"__module__": __name__},
    )()
    entity.hass = hass

    setattr(entity, f"{prefix}{member}", native_value)

    assert getattr(entity, f"native_{member}") == native_value
    assert entity.state_attributes

    assert (
        _count_warnings(caplog, f"is setting the deprecated {prefix}{member} attribute")
        == 1
    )
    assert _count_warnings(caplog, "is reading the deprecated") == 0


@pytest.mark.parametrize(("member", "native_value"), DEPRECATED_MEMBER_VALUES)
@pytest.mark.parametrize(
    ("entity_factory", "expected_warning"),
    [
        pytest.param(
            _legacy_property,
            "is overriding the deprecated {member} property",
            id="property",
        ),
        pytest.param(
            _legacy_class_attribute,
            "is setting the deprecated _attr_{member} class attribute",
            id="class-attribute",
        ),
    ],
)
async def test_deprecated_temperature_member_declaration_not_reported_as_read(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    entity_factory: Callable[[str, Any], type[MockShimWaterHeaterEntity]],
    expected_warning: str,
    member: str,
    native_value: Any,
) -> None:
    """Test serving a declared deprecated member does not report a read of it.

    The fallback reaching back into the declaration is the shim's own read; the class
    was already reported when it was created.
    """
    entity = entity_factory(member, native_value)()
    entity.hass = hass

    assert getattr(entity, f"native_{member}") == native_value
    assert entity.state_attributes

    assert _count_warnings(caplog, expected_warning.format(member=member)) == 1
    assert _count_warnings(caplog, "is reading the deprecated") == 0


@pytest.mark.parametrize("integration_frame_path", ["custom_components/my_integration"])
@pytest.mark.usefixtures("mock_integration_frame")
async def test_deprecated_temperature_member_read_reports_the_reader(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a read is reported against the code reading, not the entity's class."""
    entity = type(
        "MigratedWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {"__module__": __name__, "_attr_native_current_temperature": 21.4},
    )()
    entity.hass = hass

    assert entity.current_temperature == 21.4

    assert (
        "Detected that custom integration 'my_integration' is reading the deprecated "
        "current_temperature property, use WaterHeaterEntity.native_current_temperature "
        "instead at custom_components/my_integration/light.py, line 23"
    ) in caplog.text
    assert "MigratedWaterHeaterEntity" not in caplog.text


async def test_deprecated_temperature_member_read_without_frame_helper(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a read before the frame helper is set up is reported on the class."""
    entity = type(
        "EarlyReadWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {"__module__": __name__, "_attr_native_current_temperature": 21.4},
    )()

    assert entity.current_temperature == 21.4

    assert (
        f"{__name__}::EarlyReadWaterHeaterEntity is reading the deprecated "
        "current_temperature property, this will be unsupported from Home Assistant "
        "2027.11, use WaterHeaterEntity.native_current_temperature instead"
    ) in caplog.text


@pytest.mark.parametrize(
    ("member", "first_value", "second_value"), DEPRECATED_MEMBER_WRITES
)
async def test_deprecated_temperature_member_does_not_win_over_native(
    hass: HomeAssistant, member: str, first_value: Any, second_value: Any
) -> None:
    """Test a subclass providing both members keeps the native one."""
    entity = type(
        "BothMembersWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {
            "__module__": __name__,
            f"_attr_native_{member}": first_value,
            f"_attr_{member}": second_value,
        },
    )()
    entity.hass = hass

    assert getattr(entity, f"native_{member}") == first_value


@pytest.mark.parametrize(
    ("member", "native_value", "state_attribute", "expected_state_value"),
    DEPRECATED_MEMBERS,
)
async def test_deprecated_temperature_member_reads_native_override(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    member: str,
    native_value: Any,
    state_attribute: str,
    expected_state_value: Any,
) -> None:
    """Test the deprecated member serves an entity migrated to a native property.

    A migrated entity may compute native_<member> without ever assigning
    _attr_native_<member>, so a read of the deprecated member must dispatch to the
    override instead of returning the untouched storage.
    """
    entity = type(
        "NativeOverrideWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {
            "__module__": __name__,
            f"native_{member}": property(lambda self: native_value),
        },
    )()
    entity.hass = hass

    assert getattr(entity, member) == native_value
    assert entity.state_attributes[state_attribute] == expected_state_value
    # The read is reported, the class serving it from a native member is not
    assert _count_warnings(caplog, f"is reading the deprecated {member} property") == 1
    assert _count_warnings(caplog, "deprecated") == 1


async def test_deprecated_temperature_member_not_reported(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test no deprecation is reported for an entity using the native members."""

    class NativeWaterHeaterEntity(MockShimWaterHeaterEntity):
        """Water heater entity using the native members only."""

        _attr_native_temperature_unit = UnitOfTemperature.FAHRENHEIT
        _attr_native_current_temperature = 68.0

    entity = NativeWaterHeaterEntity()
    entity.hass = hass
    entity._attr_native_target_temperature = 70.0

    assert entity.native_temperature_unit == UnitOfTemperature.FAHRENHEIT
    assert entity.native_current_temperature == 68.0
    assert entity.native_target_temperature == 70.0
    assert entity._attr_native_current_temperature == 68.0
    assert (
        entity.state_attributes[WaterHeaterStateAttribute.CURRENT_TEMPERATURE] == 20.0
    )
    assert entity.capability_attributes
    assert _count_warnings(caplog, "deprecated") == 0


@pytest.mark.parametrize(
    ("member", "native_value", "state_attribute", "expected_state_value"),
    DEPRECATED_MEMBERS,
)
async def test_deprecated_temperature_member_on_mixin(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    member: str,
    native_value: Any,
    state_attribute: str,
    expected_state_value: Any,
) -> None:
    """Test a deprecated member declared by a mixin outside the entity ancestry."""
    mixin = type(
        "NotAnEntityMixin",
        (),
        {"__module__": __name__, member: property(lambda self: native_value)},
    )
    entity = type(
        "MixinWaterHeaterEntity",
        (mixin, MockShimWaterHeaterEntity),
        {"__module__": __name__},
    )()
    entity.hass = hass

    assert getattr(entity, f"native_{member}") == native_value
    assert entity.state_attributes[state_attribute] == expected_state_value
    assert (
        f"{__name__}::NotAnEntityMixin is overriding the deprecated {member} property"
    ) in caplog.text


@pytest.mark.parametrize(
    ("member", "native_value", "state_attribute", "expected_state_value"),
    DEPRECATED_MEMBERS,
)
@pytest.mark.parametrize(
    "parent_member_template",
    ["{member}", "native_{member}"],
    ids=["deprecated-parent", "migrated-parent"],
)
async def test_deprecated_temperature_member_super_delegation(
    hass: HomeAssistant,
    parent_member_template: str,
    member: str,
    native_value: Any,
    state_attribute: str,
    expected_state_value: Any,
) -> None:
    """Test a subclass delegating the deprecated member to its parent."""
    parent = type(
        "ParentWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {
            "__module__": __name__,
            parent_member_template.format(member=member): property(
                lambda self: native_value
            ),
        },
    )
    child: type[MockShimWaterHeaterEntity] = type(
        "DelegatingWaterHeaterEntity",
        (parent,),
        {
            "__module__": __name__,
            member: property(lambda self: getattr(super(child, self), member)),
        },
    )
    entity = child()
    entity.hass = hass

    assert getattr(entity, f"native_{member}") == native_value
    assert entity.state_attributes[state_attribute] == expected_state_value


MIGRATED_PARENT_VALUES = {
    "current_temperature": 12.3,
    "target_temperature": 12.3,
    "target_temperature_high": 12.3,
    "target_temperature_low": 12.3,
    "temperature_unit": UnitOfTemperature.KELVIN,
}


def _custom_replaces(parent: type, member: str, value: Any, parent_value: Any) -> type:
    """Return a third party subclass replacing the deprecated member."""
    return type(
        "CustomReplacesWaterHeaterEntity",
        (parent,),
        {"__module__": __name__, member: property(lambda self: value)},
    )


def _custom_delegates(parent: type, member: str, value: Any, parent_value: Any) -> type:
    """Return a third party subclass transforming what its parent reports."""
    child: type = type(
        "CustomDelegatesWaterHeaterEntity",
        (parent,),
        {
            "__module__": __name__,
            member: property(
                lambda self: (
                    value
                    if getattr(super(child, self), member) == parent_value
                    else "did not delegate"
                )
            ),
        },
    )
    return child


CUSTOM_OVER_MIGRATED_SHAPES = [
    pytest.param(_custom_replaces, id="replaces"),
    pytest.param(_custom_delegates, id="delegates"),
]


@pytest.mark.parametrize(
    ("member", "native_value", "state_attribute", "expected_state_value"),
    DEPRECATED_MEMBERS,
)
@pytest.mark.parametrize("entity_factory", CUSTOM_OVER_MIGRATED_SHAPES)
async def test_deprecated_temperature_member_wins_over_migrated_parent(
    hass: HomeAssistant,
    entity_factory: Callable[[type, str, Any, Any], type[MockShimWaterHeaterEntity]],
    member: str,
    native_value: Any,
    state_attribute: str,
    expected_state_value: Any,
) -> None:
    """Test a subclass of a migrated class keeps serving its deprecated member.

    A third party integration may subclass a class which has migrated. Its deprecated
    member is more derived than the native member of the parent, so it must win,
    whether it replaces the value or transforms what the parent reports.
    """
    parent_value = MIGRATED_PARENT_VALUES[member]
    parent = type(
        "MigratedParentWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {
            "__module__": __name__,
            f"native_{member}": property(lambda self: parent_value),
        },
    )
    entity = entity_factory(parent, member, native_value, parent_value)()
    entity.hass = hass

    assert getattr(entity, f"native_{member}") == native_value
    assert getattr(entity, member) == native_value
    assert entity.state_attributes[state_attribute] == expected_state_value


@pytest.mark.parametrize(
    "member",
    [
        "current_temperature",
        "target_temperature",
        "target_temperature_high",
        "target_temperature_low",
    ],
)
async def test_deprecated_temperature_member_override_not_cached(
    hass: HomeAssistant, member: str
) -> None:
    """Test a deprecated override is read again on every native property read."""

    def _read(self: MockShimWaterHeaterEntity) -> float:
        self.reads += 1
        return float(self.reads)

    entity = type(
        "DynamicWaterHeaterEntity",
        (MockShimWaterHeaterEntity,),
        {"__module__": __name__, member: property(_read)},
    )()
    entity.hass = hass
    entity.reads = 0

    assert [getattr(entity, f"native_{member}") for _ in range(3)] == [1.0, 2.0, 3.0]
