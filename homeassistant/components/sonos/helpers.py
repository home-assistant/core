"""Helper methods for common tasks."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, TypeVar

from soco.exceptions import SoCoException, SoCoUPnPException
from typing_extensions import Concatenate, ParamSpec

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import SONOS_SPEAKER_ACTIVITY
from .exception import SpeakerUnavailable

if TYPE_CHECKING:
    from .entity import SonosEntity
    from .speaker import SonosSpeaker

UID_PREFIX = "RINCON_"
UID_POSTFIX = "01400"

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T", bound="SonosSpeaker | SonosEntity")
_R = TypeVar("_R")
_P = ParamSpec("_P")


def soco_error(
    errorcodes: list[str] | None = None, raise_on_err: bool = True
) -> Callable[  # type: ignore[misc]
    [Callable[Concatenate[_T, _P], _R]], Callable[Concatenate[_T, _P], _R | None]
]:
    """Filter out specified UPnP errors and raise exceptions for service calls."""

    def decorator(
        funct: Callable[Concatenate[_T, _P], _R]  # type: ignore[misc]
    ) -> Callable[Concatenate[_T, _P], _R | None]:  # type: ignore[misc]
        """Decorate functions."""

        def wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> _R | None:
            """Wrap for all soco UPnP exception."""
            try:
                result = funct(self, *args, **kwargs)
            except SpeakerUnavailable:
                return None
            except (OSError, SoCoException, SoCoUPnPException) as err:
                error_code = getattr(err, "error_code", None)
                function = funct.__qualname__
                if errorcodes and error_code in errorcodes:
                    _LOGGER.debug(
                        "Error code %s ignored in call to %s", error_code, function
                    )
                    return None

                # Prefer the entity_id if available, zone name as a fallback
                # Needed as SonosSpeaker instances are not entities
                zone_name = getattr(self, "speaker", self).zone_name
                target = getattr(self, "entity_id", zone_name)
                message = f"Error calling {function} on {target}: {err}"
                if raise_on_err:
                    raise HomeAssistantError(message) from err

                _LOGGER.warning(message)
                return None

            dispatcher_send(
                self.hass,
                f"{SONOS_SPEAKER_ACTIVITY}-{self.soco.uid}",
                funct.__qualname__,
            )
            return result

        return wrapper

    return decorator


def hostname_to_uid(hostname: str) -> str:
    """Convert a Sonos hostname to a uid."""
    if hostname.startswith("Sonos-"):
        baseuid = hostname.split("-")[1].replace(".local.", "")
    elif hostname.startswith("sonos"):
        baseuid = hostname[5:].replace(".local.", "")
    else:
        raise ValueError(f"{hostname} is not a sonos device.")
    return f"{UID_PREFIX}{baseuid}{UID_POSTFIX}"
