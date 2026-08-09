"""The tests for the water heater component."""

from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol

from homeassistant.components.water_heater import (
    DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SET_TEMPERATURE_SCHEMA,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    async_mock_service,
    mock_integration,
    mock_platform,
)


async def async_setup_water_heater_entity(
    hass: HomeAssistant, water_heater_entity: WaterHeaterEntity
) -> None:
    """Set up a mock water heater entity with test integration and platform."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.WATER_HEATER]
        )
        return True

    async def async_setup_entry_water_heater_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
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


async def test_set_temp_schema_no_req(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the set temperature schema with missing required data."""
    domain = "climate"
    service = "test_set_temperature"
    schema = cv.make_entity_service_schema(SET_TEMPERATURE_SCHEMA)
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


@pytest.mark.parametrize(
    (
        "temperature_unit",
        "input_temperature",
        "expected_check_temp",
    ),
    [
        (UnitOfTemperature.CELSIUS, 20.0, "20.0"),
        (UnitOfTemperature.FAHRENHEIT, 40.0, "104.0"),
        (UnitOfTemperature.FAHRENHEIT, 61.0, "141.8"),
    ],
    ids=[
        "matching_units",
        "conversion_below_min",
        "conversion_above_max",
    ],
)
async def test_set_temperature_raises_out_of_range(
    hass: HomeAssistant,
    config_flow_fixture: None,
    temperature_unit: str,
    input_temperature: float,
    expected_check_temp: str,
) -> None:
    """Test setting temperature outside of range raises validation error."""
    water_heater_entity = MockWaterHeaterEntity()
    water_heater_entity.hass = hass
    water_heater_entity._attr_name = "test"
    water_heater_entity._attr_unique_id = "test"
    water_heater_entity._attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
    )
    water_heater_entity._attr_temperature_unit = temperature_unit

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.WATER_HEATER]
        )
        return True

    async def async_setup_entry_water_heater_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        async_add_entities([water_heater_entity])

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=async_setup_entry_init,
        ),
        built_in=False,
    )
    await async_setup_water_heater_entity(hass, water_heater_entity)

    data = {"entity_id": "water_heater.test", "temperature": input_temperature}

    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            DOMAIN,
            "set_temperature",
            data,
            blocking=True,
        )

    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "temp_out_of_range"
    assert exc.value.translation_placeholders == {
        "entity_id": "water_heater.test",
        "check_temp": expected_check_temp,
        "min_temp": str(water_heater_entity.min_temp),
        "max_temp": str(water_heater_entity.max_temp),
        "temperature_unit": water_heater_entity.temperature_unit,
    }


@pytest.mark.parametrize(
    ("input_temperature", "expected_check_temp"),
    [
        (43.3, 110.0),
        (60.0, 140.0),
    ],
    ids=["displayed_min", "displayed_max"],
)
async def test_set_temperature_accepts_displayed_boundary_value(
    hass: HomeAssistant,
    config_flow_fixture: None,
    input_temperature: float,
    expected_check_temp: float,
) -> None:
    """Test temperature at the displayed boundary values is accepted."""

    class BoundaryWaterHeater(MockWaterHeaterEntity):
        def __init__(self) -> None:
            super().__init__()
            self.last_set_temperature: dict[str, Any] | None = None

        async def async_set_temperature(self, **kwargs: Any) -> None:
            self.last_set_temperature = kwargs

    water_heater_entity = BoundaryWaterHeater()
    water_heater_entity.hass = hass
    water_heater_entity._attr_name = "test"
    water_heater_entity._attr_unique_id = "test"
    water_heater_entity._attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
    )
    water_heater_entity._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.WATER_HEATER]
        )
        return True

    async def async_setup_entry_water_heater_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
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

    data = {"entity_id": "water_heater.test", "temperature": input_temperature}

    await hass.services.async_call(
        DOMAIN,
        "set_temperature",
        data,
        blocking=True,
    )
    await hass.async_block_till_done()

    assert water_heater_entity.last_set_temperature == {
        "entity_id": ["water_heater.test"],
        "temperature": expected_check_temp,
    }


async def test_set_temperature_with_no_bounds_skips_validation(
    hass: HomeAssistant, config_flow_fixture: None
) -> None:
    """Test set temperature does not validate when bounds are not available."""

    class NoBoundsWaterHeater(MockWaterHeaterEntity):
        def __init__(self) -> None:
            super().__init__()
            self.last_set_temperature: dict[str, Any] | None = None

        @property
        def min_temp(self) -> None:
            return None

        @property
        def max_temp(self) -> None:
            return None

        async def async_set_temperature(self, **kwargs: Any) -> None:
            self.last_set_temperature = kwargs

    water_heater_entity = NoBoundsWaterHeater()
    water_heater_entity.hass = hass
    water_heater_entity._attr_name = "test"
    water_heater_entity._attr_unique_id = "test"
    water_heater_entity._attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
    )
    water_heater_entity._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.WATER_HEATER]
        )
        return True

    async def async_setup_entry_water_heater_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        async_add_entities([water_heater_entity])

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=async_setup_entry_init,
        ),
        built_in=False,
    )
    await async_setup_water_heater_entity(hass, water_heater_entity)

    await hass.services.async_call(
        DOMAIN,
        "set_temperature",
        {"entity_id": "water_heater.test", "temperature": 40.0},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert water_heater_entity.last_set_temperature == {
        "entity_id": ["water_heater.test"],
        "temperature": 104.0,
    }


class MockWaterHeaterEntity(WaterHeaterEntity):
    """Mock water heater device to use in tests."""

    _attr_operation_list: list[str] | None = ["off", "heat_pump", "gas"]
    _attr_operation = "heat_pump"
    _attr_supported_features = WaterHeaterEntityFeature.ON_OFF
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

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
