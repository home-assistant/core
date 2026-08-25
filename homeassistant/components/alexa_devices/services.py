"""Support for services."""

from aioamazondevices.const.metadata import ALEXA_INFO_SKILLS
from aioamazondevices.const.sounds import SOUNDS_LIST
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    service,
)

from .const import DOMAIN, INFO_SKILLS_MAPPING
from .coordinator import AmazonConfigEntry, alexa_api_call

ATTR_TEXT_COMMAND = "text_command"
ATTR_SOUND = "sound"
ATTR_INFO_SKILL = "info_skill"

SCHEMA_SOUND_SERVICE = vol.Schema(
    {
        vol.Required(ATTR_SOUND): cv.string,
        vol.Required(ATTR_DEVICE_ID): cv.string,
    },
)
SCHEMA_CUSTOM_COMMAND = vol.Schema(
    {
        vol.Required(ATTR_TEXT_COMMAND): cv.string,
        vol.Required(ATTR_DEVICE_ID): cv.string,
    }
)
SCHEMA_INFO_SKILL = vol.Schema(
    {
        vol.Required(ATTR_INFO_SKILL): cv.string,
        vol.Required(ATTR_DEVICE_ID): cv.string,
    }
)


@callback
def async_get_entry_id_for_service_call(
    call: ServiceCall,
) -> tuple[dr.DeviceEntry, AmazonConfigEntry]:
    """Get the entry ID related to a service call (by device ID)."""
    config_entry: AmazonConfigEntry
    device, config_entry = service.async_get_device_and_config_entry(
        call.hass, DOMAIN, call.data[ATTR_DEVICE_ID]
    )
    return (device, config_entry)


async def _async_execute_action(call: ServiceCall, attribute: str) -> None:
    """Execute action on the device."""
    device, config_entry = async_get_entry_id_for_service_call(call)
    assert device.serial_number
    value: str = call.data[attribute]

    coordinator = config_entry.runtime_data

    if attribute == ATTR_SOUND:
        if value not in SOUNDS_LIST:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_sound_value",
                translation_placeholders={"sound": value},
            )
        async with alexa_api_call():
            await coordinator.api.call_alexa_sound(
                coordinator.data[device.serial_number], value
            )
    elif attribute == ATTR_TEXT_COMMAND:
        async with alexa_api_call():
            await coordinator.api.call_alexa_text_command(
                coordinator.data[device.serial_number], value
            )
    elif attribute == ATTR_INFO_SKILL:
        info_skill = INFO_SKILLS_MAPPING.get(value)
        if info_skill not in ALEXA_INFO_SKILLS:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_info_skill_value",
                translation_placeholders={"info_skill": value},
            )
        async with alexa_api_call():
            await coordinator.api.call_alexa_info_skill(
                coordinator.data[device.serial_number], info_skill
            )


async def async_send_sound_notification(call: ServiceCall) -> None:
    """Send a sound notification to a AmazonDevice."""
    await _async_execute_action(call, ATTR_SOUND)


async def async_send_text_command(call: ServiceCall) -> None:
    """Send a custom command to a AmazonDevice."""
    await _async_execute_action(call, ATTR_TEXT_COMMAND)


async def async_send_info_skill(call: ServiceCall) -> None:
    """Send an info skill command to a AmazonDevice."""
    await _async_execute_action(call, ATTR_INFO_SKILL)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Amazon Devices integration."""
    for service_name, method, schema in (
        (
            "send_sound",
            async_send_sound_notification,
            SCHEMA_SOUND_SERVICE,
        ),
        (
            "send_text_command",
            async_send_text_command,
            SCHEMA_CUSTOM_COMMAND,
        ),
        (
            "send_info_skill",
            async_send_info_skill,
            SCHEMA_INFO_SKILL,
        ),
    ):
        hass.services.async_register(DOMAIN, service_name, method, schema=schema)
