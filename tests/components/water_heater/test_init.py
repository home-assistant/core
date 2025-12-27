"""The tests for the water heater component."""

from __future__ import annotations

from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol

from homeassistant.components import water_heater
from homeassistant.components.water_heater import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    SET_TEMPERATURE_SCHEMA,
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from tests.common import (
    MockConfigEntry,
    MockEntity,
    MockModule,
    MockPlatform,
    async_mock_service,
    import_and_test_deprecated_constant,
    mock_integration,
    mock_platform,
    setup_test_component_platform,
)


async def test_set_temp_schema_no_req(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the set temperature schema with missing required data."""
    service = "test_set_temperature"
    schema = SET_TEMPERATURE_SCHEMA
    calls = async_mock_service(hass, DOMAIN, service, schema)

    data = {"hvac_mode": "off", "entity_id": ["water_heater.test_id"]}
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, service, data)
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_set_temp_schema(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the set temperature schema with ok required data."""
    service = "test_set_temperature"
    schema = SET_TEMPERATURE_SCHEMA
    calls = async_mock_service(hass, DOMAIN, service, schema)

    data = {
        "temperature": 20.0,
        "operation_mode": "gas",
        "entity_id": ["water_heater.test_id"],
    }
    await hass.services.async_call(DOMAIN, service, data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[-1].data == data


class MockWaterHeaterEntity(MockEntity, WaterHeaterEntity):
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
    setattr(water_heater, "turn_on", MagicMock())
    await water_heater.async_turn_on()

    assert water_heater.turn_on.call_count == 1

    # Test with async_turn_on method defined
    setattr(water_heater, "async_turn_on", AsyncMock())
    await water_heater.async_turn_on()

    assert water_heater.async_turn_on.call_count == 1


async def test_sync_turn_off(hass: HomeAssistant) -> None:
    """Test if async turn_off calls sync turn_off."""
    water_heater = MockWaterHeaterEntity()
    water_heater.hass = hass

    # Test with turn_off method defined
    setattr(water_heater, "turn_off", MagicMock())
    await water_heater.async_turn_off()

    assert water_heater.turn_off.call_count == 1

    # Test with async_turn_off method defined
    setattr(water_heater, "async_turn_off", AsyncMock())
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


@pytest.mark.parametrize(
    ("constant_name", "replacement_name", "replacement"),
    [
        (
            "WaterHeaterEntityEntityDescription",
            "WaterHeaterEntityDescription",
            WaterHeaterEntityDescription,
        ),
    ],
)
def test_deprecated_constants(
    caplog: pytest.LogCaptureFixture,
    constant_name: str,
    replacement_name: str,
    replacement: Any,
) -> None:
    """Test deprecated automation constants."""
    import_and_test_deprecated_constant(
        caplog,
        water_heater,
        constant_name,
        replacement_name,
        replacement,
        "2026.1",
    )


async def test_target_temp(
    hass: HomeAssistant, register_test_integration: MockConfigEntry
) -> None:
    """Test set temp service with target temperature."""

    class MockWaterHeaterEntityTemp(MockWaterHeaterEntity):
        """Mock Water heater class."""

        _attr_target_temperature = 15
        _attr_current_temperature = 15
        _attr_supported_features = (
            WaterHeaterEntityFeature.ON_OFF
            | WaterHeaterEntityFeature.TARGET_TEMPERATURE
        )

        def set_temperature(self, **kwargs: Any) -> None:
            """Set new target temperature."""
            if ATTR_TEMPERATURE in kwargs:
                self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
            if ATTR_TARGET_TEMP_HIGH in kwargs:
                self._attr_target_temperature_high = kwargs[ATTR_TARGET_TEMP_HIGH]
                self._attr_target_temperature_low = kwargs[ATTR_TARGET_TEMP_LOW]
            self.async_write_ha_state()

    test_heater = MockWaterHeaterEntityTemp(
        name="Test",
        unique_id="unique_heater_test",
    )

    setup_test_component_platform(
        hass, DOMAIN, entities=[test_heater], from_config_entry=True
    )
    await hass.config_entries.async_setup(register_test_integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.test")
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 15
    assert state.attributes.get(ATTR_TEMPERATURE) == 15
    assert state.attributes.get(ATTR_TARGET_TEMP_HIGH) is None
    assert state.attributes.get(ATTR_TARGET_TEMP_LOW) is None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            "entity_id": "water_heater.test",
            ATTR_TEMPERATURE: "20",
        },
        blocking=True,
    )

    state = hass.states.get("water_heater.test")
    assert state.attributes.get(ATTR_TEMPERATURE) == 20

    with pytest.raises(
        ServiceValidationError,
        match="Set temperature action was used with the target temperature low/high parameter but the entity does not support it",
    ) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                "entity_id": "water_heater.test",
                ATTR_TARGET_TEMP_HIGH: "20",
                ATTR_TARGET_TEMP_LOW: "15",
            },
            blocking=True,
        )
    assert (
        str(exc.value)
        == "Set temperature action was used with the target temperature low/high parameter but the entity does not support it"
    )
    assert (
        exc.value.translation_key == "missing_target_temperature_range_entity_feature"
    )


async def test_target_temp_range(
    hass: HomeAssistant, register_test_integration: MockConfigEntry
) -> None:
    """Test set temp service with target temperature range."""

    class MockWaterHeaterEntityTemp(MockWaterHeaterEntity):
        """Mock Water heater class."""

        _attr_target_temperature = 15
        _attr_target_temperature_low = 10
        _attr_target_temperature_high = 20
        _attr_current_temperature = 15
        _attr_supported_features = (
            WaterHeaterEntityFeature.ON_OFF
            | WaterHeaterEntityFeature.TARGET_TEMPERATURE_RANGE
        )

        def set_temperature(self, **kwargs: Any) -> None:
            """Set new target temperature."""
            if ATTR_TEMPERATURE in kwargs:
                self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
            if ATTR_TARGET_TEMP_HIGH in kwargs:
                self._attr_target_temperature_high = kwargs[ATTR_TARGET_TEMP_HIGH]
                self._attr_target_temperature_low = kwargs[ATTR_TARGET_TEMP_LOW]
            self.async_write_ha_state()

    test_heater = MockWaterHeaterEntityTemp(
        name="Test",
        unique_id="unique_heater_test",
    )

    setup_test_component_platform(
        hass, DOMAIN, entities=[test_heater], from_config_entry=True
    )
    await hass.config_entries.async_setup(register_test_integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.test")
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 15
    assert state.attributes.get(ATTR_TEMPERATURE) == 15
    assert state.attributes.get(ATTR_TARGET_TEMP_HIGH) == 20
    assert state.attributes.get(ATTR_TARGET_TEMP_LOW) == 10

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            "entity_id": "water_heater.test",
            ATTR_TARGET_TEMP_HIGH: "20",
            ATTR_TARGET_TEMP_LOW: "15",
        },
        blocking=True,
    )

    state = hass.states.get("water_heater.test")
    assert state.attributes.get(ATTR_TARGET_TEMP_HIGH) == 20
    assert state.attributes.get(ATTR_TARGET_TEMP_LOW) == 15

    with pytest.raises(
        ServiceValidationError,
        match="Set temperature action was used with the target temperature parameter but the entity does not support it",
    ) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                "entity_id": "water_heater.test",
                ATTR_TEMPERATURE: "15",
            },
            blocking=True,
        )
    assert (
        str(exc.value)
        == "Set temperature action was used with the target temperature parameter but the entity does not support it"
    )
    assert exc.value.translation_key == "missing_target_temperature_entity_feature"
