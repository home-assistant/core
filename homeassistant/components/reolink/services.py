"""Reolink additional services."""

from __future__ import annotations

from reolink_aio.api import Chime
from reolink_aio.enums import ChimeToneEnum
from reolink_aio.exceptions import InvalidParameterError, ReolinkError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .host import ReolinkHost
from .util import get_device_uid_and_ch

ATTR_RINGTONE = "ringtone"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Reolink services."""

    async def async_play_chime(service_call: ServiceCall) -> None:
        """Play a ringtone."""
        service_data = service_call.data
        device_registry = dr.async_get(hass)

        for device_id in service_data[ATTR_DEVICE_ID]:
            config_entry = None
            device = device_registry.async_get(device_id)
            if device is not None:
                for entry_id in device.config_entries:
                    config_entry = hass.config_entries.async_get_entry(entry_id)
                    if config_entry is not None and config_entry.domain == DOMAIN:
                        break
            if (
                config_entry is None
                or device is None
                or config_entry.state == ConfigEntryState.NOT_LOADED
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="service_entry_ex",
                    translation_placeholders={"service_name": "play_chime"},
                )
            host: ReolinkHost = config_entry.runtime_data.host
            (device_uid, chime_id, is_chime) = get_device_uid_and_ch(device, host)
            chime: Chime | None = host.api.chime(chime_id)
            if not is_chime or chime is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="service_not_chime",
                    translation_placeholders={"device_name": str(device.name)},
                )

            ringtone = service_data[ATTR_RINGTONE]
            try:
                await chime.play(ChimeToneEnum[ringtone].value)
            except InvalidParameterError as err:
                raise ServiceValidationError(err) from err
            except ReolinkError as err:
                raise HomeAssistantError(err) from err

    hass.services.async_register(
        DOMAIN,
        "play_chime",
        async_play_chime,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): list[str],
                vol.Required(ATTR_RINGTONE): vol.In(
                    [method.name for method in ChimeToneEnum][1:]
                ),
            }
        ),
    )
