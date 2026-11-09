"""Helpers for LaMetric."""

from collections import Counter
from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from demetriek import App, Device, LaMetricConnectionError, LaMetricError
import probatio

from homeassistant.components import media_source
from homeassistant.components.media_player import async_process_play_media_url
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaMetricConfigEntry, LaMetricDataUpdateCoordinator


def lametric_exception_handler[_LaMetricEntityT: CoordinatorEntity[Any], **_P](
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
    return config_entry.runtime_data.device


def widget_labels(apps: dict[str, App]) -> list[tuple[str, str, str]]:
    """Return all widgets of a device as (label, package, widget ID).

    Widgets are ordered like the carousel on the device. A widget is named
    after its own title, falling back to the title of its app. Names that
    occur more than once get their position in the carousel appended; a
    generated label never collides with another widget's name.
    """
    entries = [
        (
            widget.index,
            app.package,
            widget_id,
            str(widget.settings.get("_title") or app.title),
        )
        for app in apps.values()
        for widget_id, widget in app.widgets.items()
    ]
    entries.sort()
    counts = Counter(entry[3] for entry in entries)
    # Reserve the names of the widgets that keep theirs, so a generated
    # label cannot take the place of an actual title.
    used = {label for _, _, _, label in entries if counts[label] == 1}
    labeled: list[tuple[str, str, str]] = []
    for index, package, widget_id, label in entries:
        if counts[label] == 1:
            labeled.append((label, package, widget_id))
            continue
        name = f"{label} {index}"
        while name in used:
            # The position is already taken by another widget's title;
            # step forward until the label is free.
            index += 1
            name = f"{label} {index}"
        used.add(name)
        labeled.append((name, package, widget_id))
    return labeled


def widget_options(apps: dict[str, App]) -> list[str]:
    """Return the selectable widgets of a device, in carousel order."""
    return [label for label, _, _ in widget_labels(apps)]


def current_widget(apps: dict[str, App]) -> str | None:
    """Return the widget currently shown on a device.

    Devices with firmware older than 2.3.0 do not report which widget is
    visible, so there may be no current widget even though apps are known.
    """
    for label, package, widget_id in widget_labels(apps):
        if apps[package].widgets[widget_id].visible:
            return label
    return None


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

    try:
        return cv.url(async_process_play_media_url(hass, sound))
    except (probatio.Invalid, ValueError) as err:
        raise invalid from err


def media_content_id(value: Any) -> str:
    """Return the media content ID of picked media, or the value as it is.

    The media selector hands over a dictionary, while a URL in an automation
    is plain text.
    """
    if isinstance(value, dict):
        return str(value.get("media_content_id", ""))
    return str(value)
