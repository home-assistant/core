"""Basic checks for HomeKit sensor."""

from collections.abc import Callable
from unittest.mock import patch

from aiohomekit.model import Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes
import pytest

from homeassistant.components.number import NumberDeviceClass, NumberMode
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import PlatformData

from .common import Helper, setup_test_component


def create_switch_with_spray_level(accessory: Accessory) -> Service:
    """Define battery level characteristics."""
    service = accessory.add_service(ServicesTypes.OUTLET)

    spray_level = service.add_char(
        CharacteristicsTypes.VENDOR_VOCOLINC_HUMIDIFIER_SPRAY_LEVEL
    )

    spray_level.perms.append("ev")
    spray_level.value = 1
    spray_level.minStep = 1
    spray_level.minValue = 1
    spray_level.maxValue = 5
    spray_level.format = "float"

    cur_state = service.add_char(CharacteristicsTypes.ON)
    cur_state.value = True

    return service


def create_valve_with_set_duration(accessory: Accessory) -> Service:
    """Define valve characteristics with a set duration."""
    service = accessory.add_service(ServicesTypes.VALVE)

    active = service.add_char(CharacteristicsTypes.ACTIVE)
    active.value = False

    set_duration = service.add_char(CharacteristicsTypes.SET_DURATION)
    set_duration.value = 1200
    set_duration.minValue = 0
    set_duration.maxValue = 5400
    set_duration.minStep = 60

    return service


def create_thermostat_with_ecobee_targets(accessory: Accessory) -> Service:
    """Define a thermostat with Ecobee comfort setting target characteristics."""
    service = accessory.add_service(ServicesTypes.THERMOSTAT, add_required=True)

    for char_type, value, min_value, max_value in (
        (CharacteristicsTypes.VENDOR_ECOBEE_HOME_TARGET_HEAT, 20.0, 7.2, 26.1),
        (CharacteristicsTypes.VENDOR_ECOBEE_HOME_TARGET_COOL, 24.0, 18.3, 33.3),
        (CharacteristicsTypes.VENDOR_ECOBEE_SLEEP_TARGET_HEAT, 17.0, 7.2, 26.1),
        (CharacteristicsTypes.VENDOR_ECOBEE_SLEEP_TARGET_COOL, 25.5, 18.3, 33.3),
        (CharacteristicsTypes.VENDOR_ECOBEE_AWAY_TARGET_HEAT, 13.0, 7.2, 26.1),
        (CharacteristicsTypes.VENDOR_ECOBEE_AWAY_TARGET_COOL, 28.0, 18.3, 33.3),
    ):
        char = service.add_char(char_type)
        char.value = value
        char.minValue = min_value
        char.maxValue = max_value
        char.minStep = 0.1
        char.format = "float"
        char.unit = "celsius"

    return service


async def test_migrate_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    get_next_aid: Callable[[], int],
) -> None:
    """Test a we can migrate a number unique id."""
    aid = get_next_aid()
    number = entity_registry.async_get_or_create(
        "number",
        "homekit_controller",
        f"homekit-0001-aid:{aid}-sid:8-cid:9",
        suggested_object_id="testdevice_spray_quantity",
    )
    await setup_test_component(hass, aid, create_switch_with_spray_level)

    assert (
        entity_registry.async_get(number.entity_id).unique_id
        == f"00:00:00:00:00:00_{aid}_8_9"
    )


async def test_translated_name_uses_english_object_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    get_next_aid: Callable[[], int],
) -> None:
    """Test translated names use English for non-native entity IDs."""
    hass.config.language = "ja"

    async def async_load_translations(platform_data: PlatformData) -> None:
        """Load translations for the spray quantity entity."""
        translation_key = (
            "component.homekit_controller.entity.number.spray_quantity.name"
        )
        platform_data.platform_translations = {translation_key: "噴霧量"}
        platform_data.object_id_platform_translations = {
            translation_key: "Spray quantity"
        }
        platform_data.default_language_platform_translations = {
            translation_key: "Spray quantity"
        }

    with patch.object(
        PlatformData,
        "async_load_translations",
        async_load_translations,
    ):
        await setup_test_component(hass, get_next_aid(), create_switch_with_spray_level)

    entity_id = "number.testdevice_spray_quantity"
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.has_entity_name
    assert entry.original_name == "噴霧量"

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["friendly_name"] == "TestDevice 噴霧量"


async def test_read_number(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test a switch service that has a sensor characteristic is correctly handled."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_switch_with_spray_level
    )

    # Helper will be for the primary entity, which is the outlet. Make a helper for the
    # sensor.
    spray_level = Helper(
        hass,
        "number.testdevice_spray_quantity",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    state = await spray_level.poll_and_get_state()
    assert state.state == "1"
    assert state.attributes["step"] == 1
    assert state.attributes["min"] == 1
    assert state.attributes["max"] == 5

    state = await spray_level.async_update(
        ServicesTypes.OUTLET,
        {CharacteristicsTypes.VENDOR_VOCOLINC_HUMIDIFIER_SPRAY_LEVEL: 5},
    )
    assert state.state == "5"


async def test_write_number(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test a switch service that has a sensor characteristic is correctly handled."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_switch_with_spray_level
    )

    # Helper will be for the primary entity, which is the outlet. Make a helper for the
    # sensor.
    spray_level = Helper(
        hass,
        "number.testdevice_spray_quantity",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.testdevice_spray_quantity", "value": 5},
        blocking=True,
    )
    spray_level.async_assert_service_values(
        ServicesTypes.OUTLET,
        {CharacteristicsTypes.VENDOR_VOCOLINC_HUMIDIFIER_SPRAY_LEVEL: 5},
    )

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.testdevice_spray_quantity", "value": 3},
        blocking=True,
    )
    spray_level.async_assert_service_values(
        ServicesTypes.OUTLET,
        {CharacteristicsTypes.VENDOR_VOCOLINC_HUMIDIFIER_SPRAY_LEVEL: 3},
    )


async def test_valve_set_duration_number(
    hass: HomeAssistant,
    get_next_aid: Callable[[], int],
) -> None:
    """Test a valve service set duration characteristic is correctly handled."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_valve_with_set_duration
    )

    set_duration = Helper(
        hass,
        "number.testdevice_duration",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    state = await set_duration.poll_and_get_state()
    assert state.state == "1200"
    assert state.attributes["device_class"] == NumberDeviceClass.DURATION
    assert state.attributes["unit_of_measurement"] == UnitOfTime.SECONDS
    assert state.attributes["step"] == 60
    assert state.attributes["min"] == 0
    assert state.attributes["max"] == 5400

    state = await set_duration.async_update(
        ServicesTypes.VALVE,
        {CharacteristicsTypes.SET_DURATION: 1800},
    )
    assert state.state == "1800"

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.testdevice_duration", "value": 600},
        blocking=True,
    )
    set_duration.async_assert_service_values(
        ServicesTypes.VALVE,
        {CharacteristicsTypes.SET_DURATION: 600},
    )


@pytest.mark.parametrize(
    (
        "entity_id",
        "char_type",
        "initial_value",
        "updated_value",
        "written_value",
        "min_value",
        "max_value",
    ),
    [
        (
            "number.testdevice_home_heating_target",
            CharacteristicsTypes.VENDOR_ECOBEE_HOME_TARGET_HEAT,
            20.0,
            21.5,
            20.5,
            7.2,
            26.1,
        ),
        (
            "number.testdevice_home_cooling_target",
            CharacteristicsTypes.VENDOR_ECOBEE_HOME_TARGET_COOL,
            24.0,
            25.0,
            23.5,
            18.3,
            33.3,
        ),
        (
            "number.testdevice_sleep_heating_target",
            CharacteristicsTypes.VENDOR_ECOBEE_SLEEP_TARGET_HEAT,
            17.0,
            18.0,
            16.5,
            7.2,
            26.1,
        ),
        (
            "number.testdevice_sleep_cooling_target",
            CharacteristicsTypes.VENDOR_ECOBEE_SLEEP_TARGET_COOL,
            25.5,
            26.0,
            24.5,
            18.3,
            33.3,
        ),
        (
            "number.testdevice_away_heating_target",
            CharacteristicsTypes.VENDOR_ECOBEE_AWAY_TARGET_HEAT,
            13.0,
            14.0,
            12.5,
            7.2,
            26.1,
        ),
        (
            "number.testdevice_away_cooling_target",
            CharacteristicsTypes.VENDOR_ECOBEE_AWAY_TARGET_COOL,
            28.0,
            29.0,
            27.5,
            18.3,
            33.3,
        ),
    ],
)
async def test_ecobee_comfort_target_numbers(
    hass: HomeAssistant,
    get_next_aid: Callable[[], int],
    entity_id: str,
    char_type: str,
    initial_value: float,
    updated_value: float,
    written_value: float,
    min_value: float,
    max_value: float,
) -> None:
    """Test Ecobee comfort setting target characteristics are exposed as numbers."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_thermostat_with_ecobee_targets
    )

    target = Helper(
        hass,
        entity_id,
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    state = await target.poll_and_get_state()
    assert float(state.state) == pytest.approx(initial_value)
    assert state.attributes["device_class"] == NumberDeviceClass.TEMPERATURE
    assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS
    assert state.attributes["mode"] == NumberMode.BOX
    assert state.attributes["step"] == 0.1
    assert state.attributes["min"] == min_value
    assert state.attributes["max"] == max_value

    state = await target.async_update(
        ServicesTypes.THERMOSTAT,
        {char_type: updated_value},
    )
    assert float(state.state) == pytest.approx(updated_value)

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": written_value},
        blocking=True,
    )
    target.async_assert_service_values(
        ServicesTypes.THERMOSTAT,
        {char_type: written_value},
    )
