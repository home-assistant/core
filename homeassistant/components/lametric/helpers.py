"""Helpers for LaMetric."""

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from demetriek import Device, LaMetricConnectionError, LaMetricError
import probatio

from homeassistant.components import media_source
from homeassistant.components.media_player import async_process_play_media_url
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN
from .coordinator import LaMetricConfigEntry, LaMetricDataUpdateCoordinator
from .entity import LaMetricEntity


def lametric_exception_handler[_LaMetricEntityT: LaMetricEntity, **_P](
    func: Callable[Concatenate[_LaMetricEntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_LaMetricEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate LaMetric calls to handle LaMetric exceptions.

    A decorator that wraps the passed in function, catches LaMetric errors,
    and handles the availability of the device in the data coordinator.
    """

    async def handler(
        self: _LaMetricEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        try:
            await func(self, *args, **kwargs)
            self.coordinator.async_update_listeners()

        except LaMetricConnectionError as error:
            self.coordinator.last_update_success = False
            self.coordinator.async_update_listeners()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error

        except LaMetricError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_response",
            ) from error

    return handler


@callback
def async_get_coordinator_by_device_id(
    hass: HomeAssistant, device_id: str
) -> LaMetricDataUpdateCoordinator:
    """Get the LaMetric coordinator for this device ID."""
    config_entry: LaMetricConfigEntry
    _, config_entry = service.async_get_device_and_config_entry(hass, DOMAIN, device_id)
    return config_entry.runtime_data


def has_audio(device: Device) -> bool:
    """Return whether the device can play sounds.

    A device without audio, like a SKY, refuses a notification with a sound.
    """
    return bool(device.audio and device.audio.available)


async def async_resolve_sound_url(hass: HomeAssistant, sound: str) -> str:
    """Turn picked media or a URL into a URL the device can fetch the sound from.

    The device fetches the sound itself, so media from Home Assistant becomes
    a full URL to Home Assistant, which the device reaches on the network.
    """
    invalid = ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_sound_url",
        translation_placeholders={"url": sound},
    )

    # An empty value, or picked media without an ID, is no sound at all.
    if not sound:
        raise invalid

    if media_source.is_media_source_id(sound):
        media = await media_source.async_resolve_media(hass, sound, None)
        sound = media.url

    url = async_process_play_media_url(hass, sound)
    try:
        return cv.url(url)
    except probatio.Invalid as err:
        raise invalid from err


def media_content_id(value: Any) -> str:
    """Return the media content ID of picked media, or the value as it is.

    The media selector hands over a dictionary, while a URL in an automation
    is plain text.
    """
    if isinstance(value, dict):
        return str(value.get("media_content_id", ""))
    return str(value)
