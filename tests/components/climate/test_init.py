"""The tests for the climate component."""

from __future__ import annotations

from enum import Enum
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
import voluptuous as vol

from homeassistant.components.climate import (
    DOMAIN,
    SET_TEMPERATURE_SCHEMA,
    ClimateEntity,
    HVACMode,
)
from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
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
    ClimateEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

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
    with pytest.raises(vol.Invalid):
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
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature = 20
    _attr_target_temperature_high = 25
    _attr_target_temperature_low = 15

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
            self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
        if ATTR_TARGET_TEMP_HIGH in kwargs:
            self._attr_target_temperature_high = kwargs[ATTR_TARGET_TEMP_HIGH]
            self._attr_target_temperature_low = kwargs[ATTR_TARGET_TEMP_LOW]


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
        match="Set temperature action was used with the 'Target temperature' parameter but the entity does not support it",
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
        match="Set temperature action was used with the 'Lower/Upper target temperature' parameter but the entity does not support it",
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
        match="Horizontal swing mode invalid is not valid. Valid horizontal swing modes are: on, off",
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
        str(exc.value)
        == "Horizontal swing mode invalid is not valid. Valid horizontal swing modes are: on, off"
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
        _attr_target_temperature = 15
        _attr_target_temperature_high = 18
        _attr_target_temperature_low = 10
        _attr_target_temperature_step = PRECISION_WHOLE

        def set_temperature(self, **kwargs: Any) -> None:
            """Set new target temperature."""
            if ATTR_TEMPERATURE in kwargs:
                self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
            if ATTR_TARGET_TEMP_HIGH in kwargs:
                self._attr_target_temperature_high = kwargs[ATTR_TARGET_TEMP_HIGH]
                self._attr_target_temperature_low = kwargs[ATTR_TARGET_TEMP_LOW]

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
        _attr_current_temperature = 15
        _attr_target_temperature = 15
        _attr_target_temperature_high = 18
        _attr_target_temperature_low = 10
        _attr_target_temperature_step = PRECISION_WHOLE

        def set_temperature(self, **kwargs: Any) -> None:
            """Set new target temperature."""
            if ATTR_TEMPERATURE in kwargs:
                self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
            if ATTR_TARGET_TEMP_HIGH in kwargs:
                self._attr_target_temperature_high = kwargs[ATTR_TARGET_TEMP_HIGH]
                self._attr_target_temperature_low = kwargs[ATTR_TARGET_TEMP_LOW]

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
        match="'Lower target temperature' can not be higher than 'Upper target temperature'",
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
        == "'Lower target temperature' can not be higher than 'Upper target temperature'"
    )
    assert exc.value.translation_key == "low_temp_higher_than_high_temp"
