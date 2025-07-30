"""Support for services."""

from aioamazondevices.sounds import SOUNDS_LIST
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .coordinator import AmazonConfigEntry

ATTR_TEXT_COMMAND = "text_command"
ATTR_SOUND = "sound"
ATTR_SOUND_VARIANT = "sound_variant"
SERVICE_TEXT_COMMAND = "send_text_command"
SERVICE_SOUND_NOTIFICATION = "send_sound"

SCHEMA_SOUND_SERVICE = vol.Schema(
    {
        vol.Required(ATTR_SOUND): cv.string,
        vol.Required(ATTR_SOUND_VARIANT): cv.positive_int,
        vol.Required(ATTR_DEVICE_ID): cv.string,
    },
)
SCHEMA_CUSTOM_COMMAND = vol.Schema(
    {
        vol.Required(ATTR_TEXT_COMMAND): cv.string,
        vol.Required(ATTR_DEVICE_ID): cv.string,
    }
)


@callback
def async_get_entry_id_for_service_call(
    call: ServiceCall,
) -> tuple[dr.DeviceEntry, AmazonConfigEntry]:
    """Get the entry ID related to a service call (by device ID)."""
    device_registry = dr.async_get(call.hass)
    device_id = call.data[ATTR_DEVICE_ID]
    if (device_entry := device_registry.async_get(device_id)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device_id",
            translation_placeholders={"device_id": device_id},
        )

    for entry_id in device_entry.config_entries:
        if (entry := call.hass.config_entries.async_get_entry(entry_id)) is None:
            continue
        if entry.domain == DOMAIN:
            if entry.state is not ConfigEntryState.LOADED:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="entry_not_loaded",
                    translation_placeholders={"entry": entry.title},
                )
            return (device_entry, entry)

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="config_entry_not_found",
        translation_placeholders={"device_id": device_id},
    )


async def _async_execute_action(call: ServiceCall, attribute: str) -> None:
    """Execute action on the device."""
    device, config_entry = async_get_entry_id_for_service_call(call)
    assert device.serial_number
    value: str = call.data[attribute]

    coordinator = config_entry.runtime_data

    if attribute == ATTR_SOUND:
        variant: int = call.data[ATTR_SOUND_VARIANT]
        pad = "_" if variant > 10 else "_0"
        file = f"{value}{pad}{variant!s}"
        if value not in SOUNDS_LIST or variant > SOUNDS_LIST[value]:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_sound_value",
                translation_placeholders={"sound": value, "variant": str(variant)},
            )
        await coordinator.api.call_alexa_sound(
            coordinator.data[device.serial_number], file
        )
    elif attribute == ATTR_TEXT_COMMAND:
        await coordinator.api.call_alexa_text_command(
            coordinator.data[device.serial_number], value
        )


async def async_send_sound_notification(call: ServiceCall) -> None:
    """Send a sound notification to a AmazonDevice."""
    await _async_execute_action(call, ATTR_SOUND)


async def async_send_text_command(call: ServiceCall) -> None:
    """Send a custom command to a AmazonDevice."""
    await _async_execute_action(call, ATTR_TEXT_COMMAND)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Amazon Devices integration."""
    for service_name, method, schema in (
        (
            SERVICE_SOUND_NOTIFICATION,
            async_send_sound_notification,
            SCHEMA_SOUND_SERVICE,
        ),
        (
            SERVICE_TEXT_COMMAND,
            async_send_text_command,
            SCHEMA_CUSTOM_COMMAND,
        ),
    ):
        hass.services.async_register(DOMAIN, service_name, method, schema=schema)
