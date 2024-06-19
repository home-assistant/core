"""Basic checks for HomeKit select entities."""

from aiohomekit.model import Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.characteristics.const import TemperatureDisplayUnits
from aiohomekit.model.services import ServicesTypes

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import Helper, get_next_aid, setup_test_component


def create_service_with_ecobee_mode(accessory: Accessory):
    """Define a thermostat with ecobee mode characteristics."""
    service = accessory.add_service(ServicesTypes.THERMOSTAT, add_required=True)

    current_mode = service.add_char(CharacteristicsTypes.VENDOR_ECOBEE_CURRENT_MODE)
    current_mode.value = 0
    current_mode.perms.append("ev")

    service.add_char(CharacteristicsTypes.VENDOR_ECOBEE_SET_HOLD_SCHEDULE)

    return service


def create_service_with_temperature_units(accessory: Accessory):
    """Define a thermostat with ecobee mode characteristics."""
    service = accessory.add_service(ServicesTypes.TEMPERATURE_SENSOR, add_required=True)

    units = service.add_char(CharacteristicsTypes.TEMPERATURE_UNITS)
    units.value = 0

    return service


async def test_migrate_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test we can migrate a select unique id."""
    aid = get_next_aid()
    select = entity_registry.async_get_or_create(
        "select",
        "homekit_controller",
        f"homekit-0001-aid:{aid}-sid:8-cid:14",
        suggested_object_id="testdevice_current_mode",
    )

    await setup_test_component(hass, create_service_with_ecobee_mode)

    assert (
        entity_registry.async_get(select.entity_id).unique_id
        == f"00:00:00:00:00:00_{aid}_8_14"
    )


async def test_read_current_mode(hass: HomeAssistant) -> None:
    """Test that Ecobee mode can be correctly read and show as human readable text."""
    helper = await setup_test_component(hass, create_service_with_ecobee_mode)

    # Helper will be for the primary entity, which is the service. Make a helper for the sensor.
    ecobee_mode = Helper(
        hass,
        "select.testdevice_current_mode",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    state = await ecobee_mode.async_update(
        ServicesTypes.THERMOSTAT,
        {
            CharacteristicsTypes.VENDOR_ECOBEE_CURRENT_MODE: 0,
        },
    )
    assert state.state == "home"

    state = await ecobee_mode.async_update(
        ServicesTypes.THERMOSTAT,
        {
            CharacteristicsTypes.VENDOR_ECOBEE_CURRENT_MODE: 1,
        },
    )
    assert state.state == "sleep"

    state = await ecobee_mode.async_update(
        ServicesTypes.THERMOSTAT,
        {
            CharacteristicsTypes.VENDOR_ECOBEE_CURRENT_MODE: 2,
        },
    )
    assert state.state == "away"


async def test_write_current_mode(hass: HomeAssistant) -> None:
    """Test can set a specific mode."""
    helper = await setup_test_component(hass, create_service_with_ecobee_mode)
    helper.accessory.services.first(service_type=ServicesTypes.THERMOSTAT)

    # Helper will be for the primary entity, which is the service. Make a helper for the sensor.
    current_mode = Helper(
        hass,
        "select.testdevice_current_mode",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.testdevice_current_mode", "option": "home"},
        blocking=True,
    )
    current_mode.async_assert_service_values(
        ServicesTypes.THERMOSTAT,
        {CharacteristicsTypes.VENDOR_ECOBEE_SET_HOLD_SCHEDULE: 0},
    )

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.testdevice_current_mode", "option": "sleep"},
        blocking=True,
    )
    current_mode.async_assert_service_values(
        ServicesTypes.THERMOSTAT,
        {CharacteristicsTypes.VENDOR_ECOBEE_SET_HOLD_SCHEDULE: 1},
    )

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.testdevice_current_mode", "option": "away"},
        blocking=True,
    )
    current_mode.async_assert_service_values(
        ServicesTypes.THERMOSTAT,
        {CharacteristicsTypes.VENDOR_ECOBEE_SET_HOLD_SCHEDULE: 2},
    )


async def test_read_select(hass: HomeAssistant) -> None:
    """Test the generic select can read the current value."""
    helper = await setup_test_component(hass, create_service_with_temperature_units)

    # Helper will be for the primary entity, which is the service. Make a helper for the sensor.
    select_entity = Helper(
        hass,
        "select.testdevice_temperature_display_units",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    state = await select_entity.async_update(
        ServicesTypes.TEMPERATURE_SENSOR,
        {
            CharacteristicsTypes.TEMPERATURE_UNITS: 0,
        },
    )
    assert state.state == "celsius"

    state = await select_entity.async_update(
        ServicesTypes.TEMPERATURE_SENSOR,
        {
            CharacteristicsTypes.TEMPERATURE_UNITS: 1,
        },
    )
    assert state.state == "fahrenheit"


async def test_write_select(hass: HomeAssistant) -> None:
    """Test can set a value."""
    helper = await setup_test_component(hass, create_service_with_temperature_units)
    helper.accessory.services.first(service_type=ServicesTypes.THERMOSTAT)

    # Helper will be for the primary entity, which is the service. Make a helper for the sensor.
    current_mode = Helper(
        hass,
        "select.testdevice_temperature_display_units",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.testdevice_temperature_display_units",
            "option": "fahrenheit",
        },
        blocking=True,
    )
    current_mode.async_assert_service_values(
        ServicesTypes.TEMPERATURE_SENSOR,
        {CharacteristicsTypes.TEMPERATURE_UNITS: TemperatureDisplayUnits.FAHRENHEIT},
    )

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.testdevice_temperature_display_units",
            "option": "celsius",
        },
        blocking=True,
    )
    current_mode.async_assert_service_values(
        ServicesTypes.TEMPERATURE_SENSOR,
        {CharacteristicsTypes.TEMPERATURE_UNITS: TemperatureDisplayUnits.CELSIUS},
    )
