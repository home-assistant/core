"""The tests for HomeKit Device device actions."""

from collections.abc import Callable
from datetime import timedelta

from aiohomekit.model import Accessory, Service
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.homekit_controller import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .common import setup_test_component

from tests.common import (
    async_get_device_automation_capabilities,
    async_get_device_automations,
)

DEFAULT_HOLD_TIME = "2040-01-01T13:35:00"


def create_ecobee_thermostat(accessory: Accessory):
    """Create Ecobee thermostat with the NEXT_SCHEDULED_CHANGE_TIME characteristic."""
    service = accessory.add_service(ServicesTypes.THERMOSTAT)

    char = service.add_char(CharacteristicsTypes.HEATING_COOLING_TARGET)
    char.value = 0
    char.minValue = 0
    char.maxValue = 1

    char = service.add_char(
        CharacteristicsTypes.VENDOR_ECOBEE_NEXT_SCHEDULED_CHANGE_TIME
    )
    char.value = DEFAULT_HOLD_TIME


def create_generic_thermostat(accessory: Accessory) -> None:
    """Create generic thermostat with no characteristics."""
    service = accessory.add_service(ServicesTypes.THERMOSTAT)

    char = service.add_char(CharacteristicsTypes.HEATING_COOLING_TARGET)
    char.value = 0
    char.minValue = 0
    char.maxValue = 1


async def test_get_ecobee_hold_action(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    get_next_aid: Callable[[], int],
) -> None:
    """Test we get the expected Ecobee hold action."""
    await setup_test_component(hass, get_next_aid(), create_ecobee_thermostat)

    ecobee_thermostat_entry = entity_registry.async_get("button.testdevice_identify")

    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, ecobee_thermostat_entry.device_id
    )

    expected_action = {
        "domain": DOMAIN,
        "type": "ecobee_set_hold_duration",
        "device_id": ecobee_thermostat_entry.device_id,
        "metadata": {},
    }

    assert expected_action in actions


async def test_hold_action_not_on_device_without_characteristic(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    get_next_aid: Callable[[], int],
) -> None:
    """Test we do not get the device action on a device without the matching characteristic."""
    await setup_test_component(hass, get_next_aid(), create_generic_thermostat)

    thermostat_entry = entity_registry.async_get("button.testdevice_identify")

    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, thermostat_entry.device_id
    )

    expected_action = {
        "domain": DOMAIN,
        "type": "ecobee_set_hold_duration",
        "device_id": thermostat_entry.device_id,
        "metadata": {},
    }

    assert expected_action not in actions


async def test_ecobee_hold_action(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    get_next_aid: Callable[[], int],
) -> None:
    """Test firing the hold action changes the next scheduled change time."""

    helper = await setup_test_component(hass, get_next_aid(), create_ecobee_thermostat)
    service: Service = helper.accessory.services.first(
        characteristics={
            CharacteristicsTypes.VENDOR_ECOBEE_NEXT_SCHEDULED_CHANGE_TIME: DEFAULT_HOLD_TIME
        }
    )

    thermostat_entry = entity_registry.async_get(helper.entity_id)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_hold_duration_set",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": thermostat_entry.device_id,
                        "type": "ecobee_set_hold_duration",
                        "ecobee_timezone": "America/New_York",
                        "hold_duration": timedelta(minutes=30),
                    },
                },
            ]
        },
    )

    assert (
        service.value(CharacteristicsTypes.VENDOR_ECOBEE_NEXT_SCHEDULED_CHANGE_TIME)
        == DEFAULT_HOLD_TIME
    )

    hass.bus.async_fire("test_hold_duration_set")
    await hass.async_block_till_done()
    assert (
        service.value(CharacteristicsTypes.VENDOR_ECOBEE_NEXT_SCHEDULED_CHANGE_TIME)
        != DEFAULT_HOLD_TIME
    )


async def test_ecobee_hold_action_capabilities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    get_next_aid: Callable[[], int],
) -> None:
    """Verify hold duration capabilities."""
    helper = await setup_test_component(hass, get_next_aid(), create_ecobee_thermostat)

    thermostat_entry = entity_registry.async_get(helper.entity_id)

    capabilities = await async_get_device_automation_capabilities(
        hass,
        DeviceAutomationType.ACTION,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": thermostat_entry.device_id,
            "type": "ecobee_set_hold_duration",
        },
    )

    expected_capabilities = {
        "extra_fields": [
            {"name": "hold_duration", "required": True, "type": "string"},
            {"name": "ecobee_timezone", "required": True, "type": "string"},
        ]
    }

    assert capabilities == expected_capabilities
