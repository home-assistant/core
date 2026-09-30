"""Reolink additional services."""

import os
from typing import TYPE_CHECKING

import probatio
from reolink_aio.api import Chime
from reolink_aio.enums import ChimeToneEnum

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.const import ATTR_DEVICE_ID, CONF_FILENAME
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.template import Template

from .const import DOMAIN, SUPPORT_PTZ_SPEED
from .host import ReolinkHost
from .util import get_device_uid_and_ch, raise_translated_error

if TYPE_CHECKING:
    from .camera import ReolinkCamera

ATTR_RINGTONE = "ringtone"
ATTR_SPEED = "speed"
ATTR_TIMESTAMP = "timestamp"
SERVICE_PTZ_MOVE = "ptz_move"
SERVICE_SNAPSHOT_PAST = "snapshot_past"


def _write_image(to_file: str, image: bytes) -> None:
    """Write the image to a file, called in the executor."""
    os.makedirs(os.path.dirname(to_file), exist_ok=True)
    with open(to_file, "wb") as img_file:
        img_file.write(image)


async def _async_snapshot_past(
    camera: ReolinkCamera, service_call: ServiceCall
) -> None:
    """Save a snapshot of a past moment in time to a file."""
    hass = camera.hass
    filename: Template = service_call.data[CONF_FILENAME]
    snapshot_file = filename.async_render()

    if not hass.config.is_allowed_path(snapshot_file):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_access_to_path",
            translation_placeholders={"filename": snapshot_file},
        )

    image = await camera.async_camera_image_past(service_call.data[ATTR_TIMESTAMP])

    try:
        await hass.async_add_executor_job(_write_image, snapshot_file, image)
    except OSError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="write_image_error",
            translation_placeholders={"filename": snapshot_file, "err": str(err)},
        ) from err


@raise_translated_error
async def _async_play_chime(service_call: ServiceCall) -> None:
    """Play a ringtone."""
    service_data = service_call.data

    for device_id in service_data[ATTR_DEVICE_ID]:
        device, config_entry = service.async_get_device_and_config_entry(
            service_call.hass, DOMAIN, device_id
        )
        host: ReolinkHost = config_entry.runtime_data.host
        (_device_uid, chime_id, is_chime) = get_device_uid_and_ch(
            device.identifiers, host
        )
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
        schema=probatio.Schema(
            {
                probatio.Required(ATTR_DEVICE_ID): list[str],
                probatio.Required(ATTR_RINGTONE): probatio.In(
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
        schema={probatio.Required(ATTR_SPEED): cv.positive_int},
        func="async_ptz_move",
        required_features=[SUPPORT_PTZ_SPEED],
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SNAPSHOT_PAST,
        entity_domain=CAMERA_DOMAIN,
        schema={
            probatio.Required(CONF_FILENAME): cv.template,
            probatio.Required(ATTR_TIMESTAMP): cv.datetime,
        },
        func=_async_snapshot_past,
    )
