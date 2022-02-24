"""Helper methods for common tasks."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, TypeVar

from soco import SoCo
from soco.exceptions import SoCoException, SoCoUPnPException
from typing_extensions import Concatenate, ParamSpec

from homeassistant.helpers.dispatcher import dispatcher_send

from .const import SONOS_SPEAKER_ACTIVITY
from .exception import SonosUpdateError

if TYPE_CHECKING:
    from .entity import SonosEntity
    from .household_coordinator import SonosHouseholdCoordinator
    from .speaker import SonosSpeaker

UID_PREFIX = "RINCON_"
UID_POSTFIX = "01400"

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T", bound="SonosSpeaker | SonosEntity | SonosHouseholdCoordinator")
_R = TypeVar("_R")
_P = ParamSpec("_P")


def soco_error(
    errorcodes: list[str] | None = None,
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
            args_soco = next((arg for arg in args if isinstance(arg, SoCo)), None)
            try:
                result = funct(self, *args, **kwargs)
            except (OSError, SoCoException, SoCoUPnPException) as err:
                error_code = getattr(err, "error_code", None)
                function = funct.__qualname__
                if errorcodes and error_code in errorcodes:
                    _LOGGER.debug(
                        "Error code %s ignored in call to %s", error_code, function
                    )
                    return None

                # In order of preference:
                #  * SonosSpeaker instance
                #  * SoCo instance passed as an arg
                #  * SoCo instance (as self)
                speaker_or_soco = getattr(self, "speaker", args_soco or self)
                zone_name = speaker_or_soco.zone_name
                # Prefer the entity_id if available, zone name as a fallback
                # Needed as SonosSpeaker instances are not entities
                target = getattr(self, "entity_id", zone_name)
                message = f"Error calling {function} on {target}: {err}"
                raise SonosUpdateError(message) from err

            dispatch_soco = args_soco or self.soco
            dispatcher_send(
                self.hass,
                f"{SONOS_SPEAKER_ACTIVITY}-{dispatch_soco.uid}",
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
