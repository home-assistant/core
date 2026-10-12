"""The tests for the climate component."""

from collections.abc import Callable
from enum import Enum
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, call

import probatio
from propcache.api import cached_property
import pytest

from homeassistant.components.climate import DOMAIN, ClimateEntity, HVACMode
from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_HUMIDITY_STEP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_HORIZONTAL_OFF,
    SWING_HORIZONTAL_ON,
    ClimateEntityCapabilityAttribute,
    ClimateEntityFeature,
    ClimateEntityStateAttribute,
)
from homeassistant.components.climate.services import (
    SET_TEMPERATURE_SCHEMA,
    _async_service_temperature_set,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from tests.common import (
    MockConfigEntry,
    MockEntity,
    async_mock_service,
    setup_test_component_platform,
)


async def test_set_temp_schema_no_req(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the set temperature schema with missing required data."""
    domain = "climate"
    service = "test_set_temperature"
    schema = SET_TEMPERATURE_SCHEMA
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
    domain = "climate"
    service = "test_set_temperature"
    schema = SET_TEMPERATURE_SCHEMA
    calls = async_mock_service(hass, domain, service, schema)

    data = {"temperature": 20.0, "hvac_mode": "heat", "entity_id": ["climate.test_id"]}
    await hass.services.async_call(domain, service, data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[-1].data == data


class MockClimateEntity(MockEntity, ClimateEntity):
    """Mock Climate device to use in tests."""

    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.SWING_HORIZONTAL_MODE
    )
    _attr_preset_mode = "home"
    _attr_preset_modes = ["home", "away"]
    _attr_fan_mode = "auto"
    _attr_fan_modes = ["auto", "off"]
    _attr_swing_mode = "auto"
    _attr_swing_modes = ["auto", "off"]
    _attr_swing_horizontal_mode = "on"
    _attr_swing_horizontal_modes = [SWING_HORIZONTAL_ON, SWING_HORIZONTAL_OFF]
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_target_temperature = 20
    _attr_native_target_temperature_high = 25
    _attr_native_target_temperature_low = 15

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVACMode.*.
        """
        return HVACMode.HEAT

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVACMode.OFF, HVACMode.HEAT]

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        self._attr_preset_mode = preset_mode

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        self._attr_fan_mode = fan_mode

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        self._attr_swing_mode = swing_mode

    def set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set horizontal swing mode."""
        self._attr_swing_horizontal_mode = swing_horizontal_mode

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        self._attr_hvac_mode = hvac_mode

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            self._attr_native_target_temperature = kwargs[ATTR_TEMPERATURE]
        if ATTR_TARGET_TEMP_HIGH in kwargs:
            self._attr_native_target_temperature_high = kwargs[ATTR_TARGET_TEMP_HIGH]
            self._attr_native_target_temperature_low = kwargs[ATTR_TARGET_TEMP_LOW]


class MockClimateEntityTestMethods(MockClimateEntity):
    """Mock Climate device."""

    def turn_on(self) -> None:
        """Turn on."""

    def turn_off(self) -> None:
        """Turn off."""


async def test_sync_turn_on(hass: HomeAssistant) -> None:
    """Test if async turn_on calls sync turn_on."""
    climate = MockClimateEntityTestMethods()
    climate.hass = hass

    climate.turn_on = MagicMock()
    await climate.async_turn_on()

    assert climate.turn_on.called


async def test_sync_turn_off(hass: HomeAssistant) -> None:
    """Test if async turn_off calls sync turn_off."""
    climate = MockClimateEntityTestMethods()
    climate.hass = hass

    climate.turn_off = MagicMock()
    await climate.async_turn_off()

    assert climate.turn_off.called


def _create_tuples(enum: type[Enum], constant_prefix: str) -> list[tuple[Enum, str]]:
    return [
        (enum_field, constant_prefix)
        for enum_field in enum
        if enum_field
        not in [
            ClimateEntityFeature.TURN_ON,
            ClimateEntityFeature.TURN_OFF,
            ClimateEntityFeature.SWING_HORIZONTAL_MODE,
        ]
    ]


async def test_temperature_features_is_valid(
    hass: HomeAssistant,
    register_test_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test correct features for setting temperature."""

    class MockClimateTempEntity(MockClimateEntity):
        @property
        def supported_features(self) -> int:
            """Return supported features."""
            return ClimateEntityFeature.TARGET_TEMPERATURE_RANGE

    class MockClimateTempRangeEntity(MockClimateEntity):
        @property
        def supported_features(self) -> int:
            """Return supported features."""
            return ClimateEntityFeature.TARGET_TEMPERATURE

    climate_temp_entity = MockClimateTempEntity(
        name="test", entity_id="climate.test_temp"
    )
    climate_temp_range_entity = MockClimateTempRangeEntity(
        name="test", entity_id="climate.test_range"
    )

    setup_test_component_platform(
        hass,
        DOMAIN,
        entities=[climate_temp_entity, climate_temp_range_entity],
        from_config_entry=True,
    )
    await hass.config_entries.async_setup(register_test_integration.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(
        ServiceValidationError,
        match=(
            "Set temperature action was used with the"
            " 'Target temperature' parameter but the"
            " entity does not support it"
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                "entity_id": "climate.test_temp",
                "temperature": 20,
            },
            blocking=True,
        )

    with pytest.raises(
        ServiceValidationError,
        match=(
            "Set temperature action was used with the"
            " 'Lower/Upper target temperature' parameter"
            " but the entity does not support it"
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                "entity_id": "climate.test_range",
                "target_temp_low": 20,
                "target_temp_high": 25,
            },
            blocking=True,
        )


async def test_mode_validation(
    hass: HomeAssistant,
    register_test_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test mode validation for hvac_mode, fan, swing and preset."""
    climate_entity = MockClimateEntity(name="test", entity_id="climate.test")

    setup_test_component_platform(
        hass, DOMAIN, entities=[climate_entity], from_config_entry=True
    )
    await hass.config_entries.async_setup(register_test_integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.test")
    assert state.state == "heat"
    assert state.attributes.get(ATTR_PRESET_MODE) == "home"
    assert state.attributes.get(ATTR_FAN_MODE) == "auto"
    assert state.attributes.get(ATTR_SWING_MODE) == "auto"
    assert state.attributes.get(ATTR_SWING_HORIZONTAL_MODE) == "on"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            "entity_id": "climate.test",
            "preset_mode": "away",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_SWING_MODE,
        {
            "entity_id": "climate.test",
            "swing_mode": "off",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_SWING_HORIZONTAL_MODE,
        {
            "entity_id": "climate.test",
            "swing_horizontal_mode": "off",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {
            "entity_id": "climate.test",
            "fan_mode": "off",
        },
        blocking=True,
    )
    state = hass.states.get("climate.test")
    assert state.attributes.get(ATTR_PRESET_MODE) == "away"
    assert state.attributes.get(ATTR_FAN_MODE) == "off"
    assert state.attributes.get(ATTR_SWING_MODE) == "off"
    assert state.attributes.get(ATTR_SWING_HORIZONTAL_MODE) == "off"

    with pytest.raises(
        ServiceValidationError,
        match="HVAC mode auto is not valid. Valid HVAC modes are: off, heat",
    ) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                "entity_id": "climate.test",
                "hvac_mode": "auto",
            },
            blocking=True,
        )
    assert (
        str(exc.value) == "HVAC mode auto is not valid. Valid HVAC modes are: off, heat"
    )
    assert exc.value.translation_key == "not_valid_hvac_mode"

    with pytest.raises(
        ServiceValidationError,
        match="Preset mode invalid is not valid. Valid preset modes are: home, away",
    ) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                "entity_id": "climate.test",
                "preset_mode": "invalid",
            },
            blocking=True,
        )
    assert (
        str(exc.value)
        == "Preset mode invalid is not valid. Valid preset modes are: home, away"
    )
    assert exc.value.translation_key == "not_valid_preset_mode"

    with pytest.raises(
        ServiceValidationError,
        match="Swing mode invalid is not valid. Valid swing modes are: auto, off",
    ) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SWING_MODE,
            {
                "entity_id": "climate.test",
                "swing_mode": "invalid",
            },
            blocking=True,
        )
    assert (
        str(exc.value)
        == "Swing mode invalid is not valid. Valid swing modes are: auto, off"
    )
    assert exc.value.translation_key == "not_valid_swing_mode"

    with pytest.raises(
        ServiceValidationError,
        match=(
            "Horizontal swing mode invalid is not valid."
            " Valid horizontal swing modes are: on, off"
        ),
    ) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            {
                "entity_id": "climate.test",
                "swing_horizontal_mode": "invalid",
            },
            blocking=True,
        )
    assert (
        str(exc.value) == "Horizontal swing mode invalid is not valid."
        " Valid horizontal swing modes are: on, off"
    )
    assert exc.value.translation_key == "not_valid_horizontal_swing_mode"

    with pytest.raises(
        ServiceValidationError,
        match="Fan mode invalid is not valid. Valid fan modes are: auto, off",
    ) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_FAN_MODE,
            {
                "entity_id": "climate.test",
                "fan_mode": "invalid",
            },
            blocking=True,
        )
    assert (
        str(exc.value)
        == "Fan mode invalid is not valid. Valid fan modes are: auto, off"
    )
    assert exc.value.translation_key == "not_valid_fan_mode"


async def test_turn_on_off_toggle(hass: HomeAssistant) -> None:
    """Test turn_on/turn_off/toggle methods."""

    class MockClimateEntityTest(MockClimateEntity):
        """Mock Climate device."""

        _attr_hvac_mode = HVACMode.OFF

        @property
        def hvac_mode(self) -> HVACMode:
            """Return hvac mode."""
            return self._attr_hvac_mode

        async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
            """Set new target hvac mode."""
            self._attr_hvac_mode = hvac_mode

    climate = MockClimateEntityTest()
    climate.hass = hass

    await climate.async_turn_on()
    assert climate.hvac_mode == HVACMode.HEAT

    await climate.async_turn_off()
    assert climate.hvac_mode == HVACMode.OFF

    await climate.async_toggle()
    assert climate.hvac_mode == HVACMode.HEAT
    await climate.async_toggle()
    assert climate.hvac_mode == HVACMode.OFF


async def test_sync_toggle(hass: HomeAssistant) -> None:
    """Test if async toggle calls sync toggle."""

    class MockClimateEntityTest(MockClimateEntity):
        """Mock Climate device."""

        _attr_supported_features = (
            ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
        )

        @property
        def hvac_mode(self) -> HVACMode:
            """Return hvac operation ie. heat, cool mode.

            Need to be one of HVACMode.*.
            """
            return HVACMode.HEAT

        @property
        def hvac_modes(self) -> list[HVACMode]:
            """Return the list of available hvac operation modes.

            Need to be a subset of HVAC_MODES.
            """
            return [HVACMode.OFF, HVACMode.HEAT]

        def turn_on(self) -> None:
            """Turn on."""

        def turn_off(self) -> None:
            """Turn off."""

        def toggle(self) -> None:
            """Toggle."""

    climate = MockClimateEntityTest()
    climate.hass = hass

    climate.toggle = Mock()
    await climate.async_toggle()

    assert climate.toggle.called


async def test_humidity_validation(
    hass: HomeAssistant,
    register_test_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validation for humidity."""

    class MockClimateEntityHumidity(MockClimateEntity):
        """Mock climate class with mocked aux heater."""

        _attr_supported_features = ClimateEntityFeature.TARGET_HUMIDITY
        _attr_target_humidity = 50
        _attr_min_humidity = 50
        _attr_max_humidity = 60
        _attr_target_humidity_step = 5

        def set_humidity(self, humidity: int) -> None:
            """Set new target humidity."""
            self._attr_target_humidity = humidity

    test_climate = MockClimateEntityHumidity(
        name="Test",
        unique_id="unique_climate_test",
    )

    setup_test_component_platform(
        hass, DOMAIN, entities=[test_climate], from_config_entry=True
    )
    await hass.config_entries.async_setup(register_test_integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.test")
    assert state.attributes.get(ATTR_HUMIDITY) == 50
    assert state.attributes.get(ATTR_TARGET_HUMIDITY_STEP) == 5

    with pytest.raises(
        ServiceValidationError,
        match="Provided humidity 1 is not valid. Accepted range is 50 to 60",
    ) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HUMIDITY,
            {
                "entity_id": "climate.test",
                ATTR_HUMIDITY: "1",
            },
            blocking=True,
        )

    assert exc.value.translation_key == "humidity_out_of_range"
    assert "Check valid humidity 1 in range 50 - 60" in caplog.text

    with pytest.raises(
        ServiceValidationError,
        match="Provided humidity 70 is not valid. Accepted range is 50 to 60",
    ) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HUMIDITY,
            {
                "entity_id": "climate.test",
                ATTR_HUMIDITY: "70",
            },
            blocking=True,
        )


async def test_temperature_validation(
    hass: HomeAssistant, register_test_integration: MockConfigEntry
) -> None:
    """Test validation for temperatures."""

    class MockClimateEntityTemp(MockClimateEntity):
        """Mock climate class with mocked aux heater."""

        _attr_supported_features = (
            ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        )
        _attr_native_target_temperature = 15
        _attr_native_target_temperature_high = 18
        _attr_native_target_temperature_low = 10
        _attr_target_temperature_step = PRECISION_WHOLE

        def set_temperature(self, **kwargs: Any) -> None:
            """Set new target temperature."""
            if ATTR_TEMPERATURE in kwargs:
                self._attr_native_target_temperature = kwargs[ATTR_TEMPERATURE]
            if ATTR_TARGET_TEMP_HIGH in kwargs:
                self._attr_native_target_temperature_high = kwargs[
                    ATTR_TARGET_TEMP_HIGH
                ]
                self._attr_native_target_temperature_low = kwargs[ATTR_TARGET_TEMP_LOW]

    test_climate = MockClimateEntityTemp(
        name="Test",
        unique_id="unique_climate_test",
    )

    setup_test_component_platform(
        hass, DOMAIN, entities=[test_climate], from_config_entry=True
    )
    await hass.config_entries.async_setup(register_test_integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.test")
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) is None
    assert state.attributes.get(ATTR_MIN_TEMP) == 7
    assert state.attributes.get(ATTR_MAX_TEMP) == 35

    with pytest.raises(
        ServiceValidationError,
        match="Provided temperature 40.0 is not valid. Accepted range is 7 to 35",
    ) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                "entity_id": "climate.test",
                ATTR_TEMPERATURE: "40",
            },
            blocking=True,
        )
    assert (
        str(exc.value)
        == "Provided temperature 40.0 is not valid. Accepted range is 7 to 35"
    )
    assert exc.value.translation_key == "temp_out_of_range"

    with pytest.raises(
        ServiceValidationError,
        match="Provided temperature 0.0 is not valid. Accepted range is 7 to 35",
    ) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                "entity_id": "climate.test",
                ATTR_TARGET_TEMP_HIGH: "25",
                ATTR_TARGET_TEMP_LOW: "0",
            },
            blocking=True,
        )
    assert (
        str(exc.value)
        == "Provided temperature 0.0 is not valid. Accepted range is 7 to 35"
    )
    assert exc.value.translation_key == "temp_out_of_range"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            "entity_id": "climate.test",
            ATTR_TARGET_TEMP_HIGH: "25",
            ATTR_TARGET_TEMP_LOW: "10",
        },
        blocking=True,
    )

    state = hass.states.get("climate.test")
    assert state.attributes.get(ATTR_TARGET_TEMP_LOW) == 10
    assert state.attributes.get(ATTR_TARGET_TEMP_HIGH) == 25


async def test_target_temp_high_higher_than_low(
    hass: HomeAssistant, register_test_integration: MockConfigEntry
) -> None:
    """Test that target high is higher than target low."""

    class MockClimateEntityTemp(MockClimateEntity):
        """Mock climate class with mocked aux heater."""

        _attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        )
        _attr_native_current_temperature = 15
        _attr_native_target_temperature = 15
        _attr_native_target_temperature_high = 18
        _attr_native_target_temperature_low = 10
        _attr_target_temperature_step = PRECISION_WHOLE

        def set_temperature(self, **kwargs: Any) -> None:
            """Set new target temperature."""
            if ATTR_TEMPERATURE in kwargs:
                self._attr_native_target_temperature = kwargs[ATTR_TEMPERATURE]
            if ATTR_TARGET_TEMP_HIGH in kwargs:
                self._attr_native_target_temperature_high = kwargs[
                    ATTR_TARGET_TEMP_HIGH
                ]
                self._attr_native_target_temperature_low = kwargs[ATTR_TARGET_TEMP_LOW]

    test_climate = MockClimateEntityTemp(
        name="Test",
        unique_id="unique_climate_test",
    )

    setup_test_component_platform(
        hass, DOMAIN, entities=[test_climate], from_config_entry=True
    )
    await hass.config_entries.async_setup(register_test_integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.test")
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 15
    assert state.attributes.get(ATTR_MIN_TEMP) == 7
    assert state.attributes.get(ATTR_MAX_TEMP) == 35

    with pytest.raises(
        ServiceValidationError,
        match=(
            "'Lower target temperature' cannot be higher"
            " than 'Upper target temperature'"
        ),
    ) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                "entity_id": "climate.test",
                ATTR_TARGET_TEMP_HIGH: "15",
                ATTR_TARGET_TEMP_LOW: "20",
            },
            blocking=True,
        )
    assert (
        str(exc.value)
        == "'Lower target temperature' cannot be higher than 'Upper target temperature'"
    )
    assert exc.value.translation_key == "low_temp_higher_than_high_temp"


class MockShimClimateEntity(MockClimateEntity):
    """Climate entity with every temperature feature and a wrong native baseline.

    The deprecated members under test must win over the baseline values.
    """

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )
    _attr_native_current_temperature = 99.0
    _attr_native_target_temperature = 99.0
    _attr_native_target_temperature_high = 99.0
    _attr_native_target_temperature_low = 99.0


def _legacy_property(member: str, value: Any) -> type[MockShimClimateEntity]:
    """Return a subclass overriding the deprecated member with a plain property."""

    return type(
        "LegacyPropertyClimateEntity",
        (MockShimClimateEntity,),
        {"__module__": __name__, member: property(lambda self: value)},
    )


def _legacy_cached_property(member: str, value: Any) -> type[MockShimClimateEntity]:
    """Return a subclass overriding the deprecated member with a cached property."""

    return type(
        "LegacyCachedPropertyClimateEntity",
        (MockShimClimateEntity,),
        {"__module__": __name__, member: cached_property(lambda self: value)},
    )


def _legacy_class_value(member: str, value: Any) -> type[MockShimClimateEntity]:
    """Return a subclass overriding the deprecated member with a class attribute."""

    return type(
        "LegacyClassValueClimateEntity",
        (MockShimClimateEntity,),
        {"__module__": __name__, member: value},
    )


def _legacy_class_attribute(member: str, value: Any) -> type[MockShimClimateEntity]:
    """Return a subclass setting the deprecated _attr_ member at class level."""

    return type(
        "LegacyClassAttributeClimateEntity",
        (MockShimClimateEntity,),
        {"__module__": __name__, f"_attr_{member}": value},
    )


def _legacy_instance_attribute(member: str, value: Any) -> type[MockShimClimateEntity]:
    """Return a subclass setting the deprecated _attr_ member at runtime."""

    def __init__(self: MockShimClimateEntity, **values: Any) -> None:
        MockShimClimateEntity.__init__(self, **values)
        setattr(self, f"_attr_{member}", value)

    return type(
        "LegacyInstanceAttributeClimateEntity",
        (MockShimClimateEntity,),
        {"__module__": __name__, "__init__": __init__},
    )


def _legacy_slots(member: str, value: Any) -> type[MockShimClimateEntity]:
    """Return a subclass declaring the deprecated member in __slots__."""

    def __init__(self: MockShimClimateEntity, **values: Any) -> None:
        MockShimClimateEntity.__init__(self, **values)
        setattr(self, member, value)

    return type(
        "LegacySlotsClimateEntity",
        (MockShimClimateEntity,),
        {"__module__": __name__, "__slots__": (member,), "__init__": __init__},
    )


def _count_warnings(caplog: pytest.LogCaptureFixture, warning: str) -> int:
    """Return the number of logged records mentioning the warning."""
    return sum(warning in record.getMessage() for record in caplog.records)


DEPRECATED_MEMBERS = [
    pytest.param(
        "current_temperature",
        21.4,
        ClimateEntityStateAttribute.CURRENT_TEMPERATURE,
        21.4,
        id="current_temperature",
    ),
    pytest.param(
        "target_temperature",
        21.4,
        ClimateEntityStateAttribute.TARGET_TEMPERATURE,
        21.4,
        id="target_temperature",
    ),
    pytest.param(
        "target_temperature_high",
        21.4,
        ClimateEntityStateAttribute.TARGET_TEMP_HIGH,
        21.4,
        id="target_temperature_high",
    ),
    pytest.param(
        "target_temperature_low",
        21.4,
        ClimateEntityStateAttribute.TARGET_TEMP_LOW,
        21.4,
        id="target_temperature_low",
    ),
    pytest.param(
        "temperature_unit",
        UnitOfTemperature.FAHRENHEIT,
        # The native unit is not published, it converts the published temperatures
        ClimateEntityStateAttribute.CURRENT_TEMPERATURE,
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
        "native_{member}",
        0,
        id="property",
    ),
    pytest.param(
        _legacy_cached_property,
        "is overriding the deprecated {member} property",
        "native_{member}",
        0,
        id="cached-property",
    ),
    pytest.param(
        _legacy_class_value,
        "is overriding the deprecated {member} property",
        "native_{member}",
        0,
        id="class-value",
    ),
    pytest.param(
        _legacy_class_attribute,
        "is setting the deprecated _attr_{member} class attribute",
        "_attr_native_{member}",
        1,
        id="class-attribute",
    ),
    pytest.param(
        _legacy_instance_attribute,
        "is setting the deprecated _attr_{member} attribute",
        "_attr_native_{member}",
        1,
        id="instance-attribute",
    ),
    pytest.param(
        _legacy_slots,
        "is declaring the deprecated {member} in __slots__",
        "_attr_native_{member}",
        0,
        id="slots",
    ),
]


@pytest.mark.parametrize(
    ("unit_system", "native_unit", "expected_temperature", "expected_unit"),
    [
        pytest.param(
            METRIC_SYSTEM,
            UnitOfTemperature.CELSIUS,
            21.4,
            UnitOfTemperature.CELSIUS,
            id="metric-native-celsius",
        ),
        pytest.param(
            METRIC_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            -5.9,
            UnitOfTemperature.CELSIUS,
            id="metric-native-fahrenheit",
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.CELSIUS,
            71,
            UnitOfTemperature.FAHRENHEIT,
            id="us-customary-native-celsius",
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            21,
            UnitOfTemperature.FAHRENHEIT,
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
    expected_unit: UnitOfTemperature,
) -> None:
    """Test the native unit converts the published temperatures."""
    hass.config.units = unit_system
    entity = MockClimateEntity(name="Test", unique_id="unique_climate_test")
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

    state = hass.states.get("climate.test")
    assert (
        state.attributes[ClimateEntityStateAttribute.CURRENT_TEMPERATURE]
        == expected_temperature
    )
    # The published unit is the one the published temperatures are converted to
    assert (
        state.attributes[ClimateEntityStateAttribute.TEMPERATURE_UNIT] == expected_unit
    )


async def test_native_temperature_unit_property(hass: HomeAssistant) -> None:
    """Test an entity may provide the native unit through a property."""

    class NativePropertyClimateEntity(MockClimateEntity):
        """Climate entity overriding native_temperature_unit."""

        @property
        def native_temperature_unit(self) -> str:
            """Return the unit of measurement the entity reports temperatures in."""
            return UnitOfTemperature.FAHRENHEIT

    entity = NativePropertyClimateEntity()
    entity.hass = hass
    entity._attr_native_current_temperature = 68.0

    assert entity.native_temperature_unit == UnitOfTemperature.FAHRENHEIT
    # The deprecated alias dispatches to the override instead of reading the
    # storage the override bypasses
    assert entity.temperature_unit == UnitOfTemperature.FAHRENHEIT
    state_attributes = entity.state_attributes
    assert state_attributes[ClimateEntityStateAttribute.CURRENT_TEMPERATURE] == 20.0


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
    entity = MockShimClimateEntity()
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
            7,
            35,
            7.0,
            35.0,
            id="metric-native-celsius",
        ),
        pytest.param(
            METRIC_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            44.6,
            95,
            7.0,
            35.0,
            id="metric-native-fahrenheit",
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.CELSIUS,
            7,
            35,
            45,
            95,
            id="us-customary-native-celsius",
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            44.6,
            95,
            45,
            95,
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
    entity = MockClimateEntity()
    entity.hass = hass
    entity._attr_native_temperature_unit = native_unit

    assert entity.min_temp == pytest.approx(expected_min_temp, abs=0.01)
    assert entity.max_temp == pytest.approx(expected_max_temp, abs=0.01)

    capability_attributes = entity.capability_attributes
    assert (
        capability_attributes[ClimateEntityCapabilityAttribute.MIN_TEMP]
        == expected_capability_min_temp
    )
    assert (
        capability_attributes[ClimateEntityCapabilityAttribute.MAX_TEMP]
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

    class TargetTemperatureClimateEntity(MockClimateEntity):
        """Climate entity supporting a target temperature."""

        _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    entity = TargetTemperatureClimateEntity()
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
    ("entity_factory", "expected_warning", "expected_replacement", "expected_reads"),
    DEPRECATED_SHAPES,
)
async def test_deprecated_temperature_member(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    entity_factory: Callable[[str, Any], type[MockShimClimateEntity]],
    expected_warning: str,
    expected_replacement: str,
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
        f"use ClimateEntity.{expected_replacement.format(member=member)} instead"
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
    assert entity.min_temp == pytest.approx(44.6, abs=0.01)
    assert entity.max_temp == pytest.approx(95, abs=0.01)

    state_attributes = entity.state_attributes
    assert state_attributes[ClimateEntityStateAttribute.CURRENT_TEMPERATURE] == 20.0


@pytest.mark.parametrize(
    ("member", "first_value", "second_value"), DEPRECATED_MEMBER_WRITES
)
async def test_deprecated_temperature_member_setter(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    member: str,
    first_value: Any,
    second_value: Any,
) -> None:
    """Test writing a deprecated _attr_ temperature member at runtime."""
    warning = (
        f"is setting the deprecated _attr_{member} attribute, this will be "
        "unsupported from Home Assistant 2027.11, "
        f"use ClimateEntity._attr_native_{member} instead"
    )
    entity = MockShimClimateEntity()
    entity.hass = hass

    setattr(entity, f"_attr_{member}", first_value)

    assert getattr(entity, f"_attr_{member}") == first_value
    assert getattr(entity, f"_attr_native_{member}") == first_value
    assert getattr(entity, f"native_{member}") == first_value
    assert caplog.text.count(warning) == 1

    setattr(entity, f"_attr_{member}", second_value)

    assert getattr(entity, f"native_{member}") == second_value
    assert caplog.text.count(warning) == 1


@pytest.mark.parametrize(("member", "native_value"), DEPRECATED_MEMBER_VALUES)
@pytest.mark.parametrize(
    "declarations",
    [pytest.param({}, id="plain"), pytest.param({"_attr_{member}": None}, id="attr")],
)
async def test_deprecated_temperature_member_public_write_raises(
    hass: HomeAssistant, declarations: dict[str, Any], member: str, native_value: Any
) -> None:
    """Test a deprecated public member cannot be written.

    Only the _attr_ shorthands keep a setter. Below a deprecated _attr_ declaration a
    write to the public member would otherwise land in storage nothing reads.
    """
    entity = type(
        "PublicWriterClimateEntity",
        (MockShimClimateEntity,),
        {
            "__module__": __name__,
            **{name.format(member=member): v for name, v in declarations.items()},
        },
    )()
    entity.hass = hass

    with pytest.raises(AttributeError, match=f"property '{member}' .* has no setter"):
        setattr(entity, member, native_value)


@pytest.mark.parametrize(("member", "native_value"), DEPRECATED_MEMBER_VALUES)
async def test_deprecated_temperature_member_setter_reported_once_per_class(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    member: str,
    native_value: Any,
) -> None:
    """Test a deprecated write is reported once per class, not once per entity.

    A multi-zone integration builds one entity per zone from a single class, so a
    once-per-instance report is one log line per zone per setup.
    """
    warning = f"is setting the deprecated _attr_{member} attribute"
    first = type(
        "FirstWriterClimateEntity", (MockShimClimateEntity,), {"__module__": __name__}
    )
    second = type(
        "SecondWriterClimateEntity", (MockShimClimateEntity,), {"__module__": __name__}
    )
    # A class attribute would be inherited, silencing a subclass of a reported class
    subclass = type("SubclassWriterClimateEntity", (first,), {"__module__": __name__})

    def write(entity_class: type[MockShimClimateEntity]) -> None:
        """Write the deprecated member on three fresh entities of the class."""
        for _ in range(3):
            entity = entity_class()
            entity.hass = hass
            setattr(entity, f"_attr_{member}", native_value)

    write(first)

    assert f"{__name__}::FirstWriterClimateEntity {warning}" in caplog.text
    assert _count_warnings(caplog, warning) == 1

    write(second)

    assert f"{__name__}::SecondWriterClimateEntity {warning}" in caplog.text
    assert _count_warnings(caplog, warning) == 2

    write(subclass)

    assert f"{__name__}::SubclassWriterClimateEntity {warning}" in caplog.text
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
        "MigratedClimateEntity",
        (MockShimClimateEntity,),
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
async def test_deprecated_temperature_member_write_not_reported_as_read(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    member: str,
    native_value: Any,
) -> None:
    """Test writing a deprecated temperature member does not report a read of it."""
    entity = type(
        "WriteOnlyClimateEntity",
        (MockShimClimateEntity,),
        {"__module__": __name__},
    )()
    entity.hass = hass

    setattr(entity, f"_attr_{member}", native_value)

    assert getattr(entity, f"native_{member}") == native_value
    assert entity.state_attributes

    assert (
        _count_warnings(caplog, f"is setting the deprecated _attr_{member} attribute")
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
    entity_factory: Callable[[str, Any], type[MockShimClimateEntity]],
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
        "MigratedClimateEntity",
        (MockShimClimateEntity,),
        {"__module__": __name__, "_attr_native_current_temperature": 21.4},
    )()
    entity.hass = hass

    assert entity.current_temperature == 21.4

    assert (
        "Detected that custom integration 'my_integration' is reading the deprecated "
        "current_temperature property, use ClimateEntity.native_current_temperature "
        "instead at custom_components/my_integration/light.py, line 23"
    ) in caplog.text
    assert "MigratedClimateEntity" not in caplog.text


async def test_deprecated_temperature_member_read_without_frame_helper(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a read before the frame helper is set up is reported on the class."""
    entity = type(
        "EarlyReadClimateEntity",
        (MockShimClimateEntity,),
        {"__module__": __name__, "_attr_native_current_temperature": 21.4},
    )()

    assert entity.current_temperature == 21.4

    assert (
        f"{__name__}::EarlyReadClimateEntity is reading the deprecated "
        "current_temperature property, this will be unsupported from Home Assistant "
        "2027.11, use ClimateEntity.native_current_temperature instead"
    ) in caplog.text


@pytest.mark.parametrize(
    ("member", "first_value", "second_value"), DEPRECATED_MEMBER_WRITES
)
async def test_deprecated_temperature_member_does_not_win_over_native(
    hass: HomeAssistant, member: str, first_value: Any, second_value: Any
) -> None:
    """Test a subclass providing both members keeps the native one."""
    entity = type(
        "BothMembersClimateEntity",
        (MockShimClimateEntity,),
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
        "NativeOverrideClimateEntity",
        (MockShimClimateEntity,),
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

    class NativeClimateEntity(MockShimClimateEntity):
        """Climate entity using the native members only."""

        _attr_native_temperature_unit = UnitOfTemperature.FAHRENHEIT
        _attr_native_current_temperature = 68.0

    entity = NativeClimateEntity()
    entity.hass = hass
    entity._attr_native_target_temperature = 70.0

    assert entity.native_temperature_unit == UnitOfTemperature.FAHRENHEIT
    assert entity.native_current_temperature == 68.0
    assert entity.native_target_temperature == 70.0
    assert entity._attr_native_current_temperature == 68.0
    assert (
        entity.state_attributes[ClimateEntityStateAttribute.CURRENT_TEMPERATURE] == 20.0
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
        "MixinClimateEntity",
        (mixin, MockShimClimateEntity),
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
        "ParentClimateEntity",
        (MockShimClimateEntity,),
        {
            "__module__": __name__,
            parent_member_template.format(member=member): property(
                lambda self: native_value
            ),
        },
    )
    child: type[MockShimClimateEntity] = type(
        "DelegatingClimateEntity",
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
        "CustomReplacesClimateEntity",
        (parent,),
        {"__module__": __name__, member: property(lambda self: value)},
    )


def _custom_delegates(parent: type, member: str, value: Any, parent_value: Any) -> type:
    """Return a third party subclass transforming what its parent reports."""
    child: type = type(
        "CustomDelegatesClimateEntity",
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
    entity_factory: Callable[[type, str, Any, Any], type[MockShimClimateEntity]],
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
        "MigratedParentClimateEntity",
        (MockShimClimateEntity,),
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

    def _read(self: MockShimClimateEntity) -> float:
        self.reads += 1
        return float(self.reads)

    entity = type(
        "DynamicClimateEntity",
        (MockShimClimateEntity,),
        {"__module__": __name__, member: property(_read)},
    )()
    entity.hass = hass
    entity.reads = 0

    assert [getattr(entity, f"native_{member}") for _ in range(3)] == [1.0, 2.0, 3.0]


@pytest.mark.parametrize(
    ("member", "native_value", "state_attribute", "expected_state_value"),
    DEPRECATED_MEMBERS,
)
@pytest.mark.parametrize(
    "grandparent_declarations",
    [
        pytest.param({}, id="legacy-parent"),
        pytest.param(
            {"native_{member}": property(lambda self: "grandparent")},
            id="legacy-parent-over-migrated-grandparent",
        ),
    ],
)
@pytest.mark.parametrize("depth", [1, 2], ids=["child", "grandchild"])
async def test_migrated_child_wins_over_deprecated_parent_attribute(
    hass: HomeAssistant,
    depth: int,
    grandparent_declarations: dict[str, Any],
    member: str,
    native_value: Any,
    state_attribute: str,
    expected_state_value: Any,
) -> None:
    """Test a class setting _attr_native_ wins over a parent's deprecated _attr_.

    The parent's deprecated storage gets a fallback installed, which the migrated
    class, and anything inheriting from it, must not keep serving.
    """
    grandparent = type(
        "GrandparentClimateEntity",
        (MockShimClimateEntity,),
        {
            "__module__": __name__,
            **{
                name.format(member=member): value
                for name, value in grandparent_declarations.items()
            },
        },
    )
    entity_class = type(
        "LegacyParentClimateEntity",
        (grandparent,),
        {"__module__": __name__, f"_attr_{member}": MIGRATED_PARENT_VALUES[member]},
    )
    entity_class = type(
        "MigratedChildClimateEntity",
        (entity_class,),
        {"__module__": __name__, f"_attr_native_{member}": native_value},
    )
    for _ in range(depth - 1):
        entity_class = type(
            "GrandchildClimateEntity", (entity_class,), {"__module__": __name__}
        )
    entity = entity_class()
    entity.hass = hass

    assert getattr(entity, f"native_{member}") == native_value
    assert getattr(entity, member) == native_value
    assert entity.state_attributes[state_attribute] == expected_state_value
