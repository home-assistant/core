"""The tests for the water heater component."""

from __future__ import annotations

from unittest import mock
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol

from homeassistant.components import water_heater
from homeassistant.components.water_heater import (
    ATTR_OPERATION_LIST,
    ATTR_OPERATION_MODE,
    DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SET_TEMPERATURE_SCHEMA,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    async_mock_service,
    help_test_all,
    import_and_test_deprecated_constant_enum,
    mock_integration,
    mock_platform,
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
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    async def async_setup_entry_water_heater_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
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


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(water_heater)


@pytest.mark.parametrize(
    ("enum"),
    [
        WaterHeaterEntityFeature.TARGET_TEMPERATURE,
        WaterHeaterEntityFeature.OPERATION_MODE,
        WaterHeaterEntityFeature.AWAY_MODE,
    ],
)
def test_deprecated_constants(
    caplog: pytest.LogCaptureFixture,
    enum: WaterHeaterEntityFeature,
) -> None:
    """Test deprecated constants."""
    import_and_test_deprecated_constant_enum(
        caplog, water_heater, enum, "SUPPORT_", "2025.1"
    )


def test_deprecated_supported_features_ints(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test deprecated supported features ints."""

    class MockWaterHeaterEntity(WaterHeaterEntity):
        _attr_operation_list = ["mode1", "mode2"]
        _attr_temperature_unit = UnitOfTemperature.CELSIUS
        _attr_current_operation = "mode1"
        _attr_supported_features = WaterHeaterEntityFeature.OPERATION_MODE.value

    entity = MockWaterHeaterEntity()
    entity.hass = hass
    assert entity.supported_features_compat is WaterHeaterEntityFeature(2)
    assert "MockWaterHeaterEntity" in caplog.text
    assert "is using deprecated supported features values" in caplog.text
    assert "Instead it should use" in caplog.text
    assert "WaterHeaterEntityFeature.OPERATION_MODE" in caplog.text
    caplog.clear()
    assert entity.supported_features_compat is WaterHeaterEntityFeature(2)
    assert "is using deprecated supported features values" not in caplog.text
    assert entity.state_attributes[ATTR_OPERATION_MODE] == "mode1"
    assert entity.capability_attributes[ATTR_OPERATION_LIST] == ["mode1", "mode2"]
