"""Helper methods for common tasks."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast

from soco.exceptions import SoCoException, SoCoUPnPException

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import SONOS_SPEAKER_ACTIVITY
from .exception import SpeakerUnavailable

if TYPE_CHECKING:
    from .entity import SonosEntity
    from .speaker import SonosSpeaker

UID_PREFIX = "RINCON_"
UID_POSTFIX = "01400"

WrapFuncType = TypeVar("WrapFuncType", bound=Callable[..., Any])

_LOGGER = logging.getLogger(__name__)


def soco_error(
    errorcodes: list[str] | None = None, raise_on_err: bool = True
) -> Callable:
    """Filter out specified UPnP errors and raise exceptions for service calls."""

    def decorator(funct: WrapFuncType) -> WrapFuncType:
        """Decorate functions."""

        def wrapper(self: SonosSpeaker | SonosEntity, *args: Any, **kwargs: Any) -> Any:
            """Wrap for all soco UPnP exception."""
            try:
                result = funct(self, *args, **kwargs)
            except SpeakerUnavailable:
                return None
            except (OSError, SoCoException, SoCoUPnPException) as err:
                error_code = getattr(err, "error_code", None)
                function = funct.__name__
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
                self.hass, f"{SONOS_SPEAKER_ACTIVITY}-{self.soco.uid}", funct.__name__
            )
            return result

        return cast(WrapFuncType, wrapper)

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
