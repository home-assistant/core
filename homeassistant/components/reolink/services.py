"""Reolink additional services."""

from reolink_aio.api import Chime
from reolink_aio.enums import ChimeToneEnum
import voluptuous as vol

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, SUPPORT_PTZ_SPEED
from .host import ReolinkHost
from .util import get_device_uid_and_ch, raise_translated_error

ATTR_RINGTONE = "ringtone"
ATTR_SPEED = "speed"
SERVICE_PTZ_MOVE = "ptz_move"


@raise_translated_error
async def _async_play_chime(service_call: ServiceCall) -> None:
    """Play a ringtone."""
    service_data = service_call.data

    for device_id in service_data[ATTR_DEVICE_ID]:
        device, config_entry = service.async_get_device_and_config_entry(
            service_call.hass, DOMAIN, device_id
        )
        host: ReolinkHost = config_entry.runtime_data.host
        (_device_uid, chime_id, is_chime) = get_device_uid_and_ch(device, host)
        chime: Chime | None = host.api.chime(chime_id)
        if not is_chime or chime is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_not_chime",
                translation_placeholders={"device_name": str(device.name)},
            )

        ringtone = service_data[ATTR_RINGTONE]
        await chime.play(ChimeToneEnum[ringtone].value)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Reolink services."""

    hass.services.async_register(
        DOMAIN,
        "play_chime",
        _async_play_chime,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): list[str],
                vol.Required(ATTR_RINGTONE): vol.In(
                    [method.name for method in ChimeToneEnum][1:]
                ),
            }
        ),
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_PTZ_MOVE,
        entity_domain=BUTTON_DOMAIN,
        schema={vol.Required(ATTR_SPEED): cv.positive_int},
        func="async_ptz_move",
        required_features=[SUPPORT_PTZ_SPEED],
    )
