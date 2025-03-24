"""Helper methods for common tasks."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any, Concatenate, overload

from requests.exceptions import Timeout
from soco import SoCo
from soco.exceptions import SoCoException, SoCoUPnPException

from homeassistant.helpers.dispatcher import dispatcher_send

from .const import SONOS_SPEAKER_ACTIVITY
from .exception import SonosUpdateError

if TYPE_CHECKING:
    from .entity import SonosEntity
    from .household_coordinator import SonosHouseholdCoordinator
    from .media import SonosMedia
    from .speaker import SonosSpeaker

UID_PREFIX = "RINCON_"
UID_POSTFIX = "01400"

_LOGGER = logging.getLogger(__name__)

type _SonosEntitiesType = (
    SonosSpeaker | SonosMedia | SonosEntity | SonosHouseholdCoordinator
)
type _FuncType[_T, **_P, _R] = Callable[Concatenate[_T, _P], _R]
type _ReturnFuncType[_T, **_P, _R] = Callable[Concatenate[_T, _P], _R | None]


@overload
def soco_error[_T: _SonosEntitiesType, **_P, _R](
    errorcodes: None = ...,
) -> Callable[[_FuncType[_T, _P, _R]], _FuncType[_T, _P, _R]]: ...


@overload
def soco_error[_T: _SonosEntitiesType, **_P, _R](
    errorcodes: list[str],
) -> Callable[[_FuncType[_T, _P, _R]], _ReturnFuncType[_T, _P, _R]]: ...


def soco_error[_T: _SonosEntitiesType, **_P, _R](
    errorcodes: list[str] | None = None,
) -> Callable[[_FuncType[_T, _P, _R]], _ReturnFuncType[_T, _P, _R]]:
    """Filter out specified UPnP errors and raise exceptions for service calls."""

    def decorator(funct: _FuncType[_T, _P, _R]) -> _ReturnFuncType[_T, _P, _R]:
        """Decorate functions."""

        def wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> _R | None:
            """Wrap for all soco UPnP exception."""
            args_soco = next((arg for arg in args if isinstance(arg, SoCo)), None)
            try:
                result = funct(self, *args, **kwargs)
            except (OSError, SoCoException, SoCoUPnPException, Timeout) as err:
                error_code = getattr(err, "error_code", None)
                function = funct.__qualname__
                if errorcodes and error_code in errorcodes:
                    _LOGGER.debug(
                        "Error code %s ignored in call to %s", error_code, function
                    )
                    return None

                if (target := _find_target_identifier(self, args_soco)) is None:
                    raise RuntimeError("Unexpected use of soco_error") from err

                message = f"Error calling {function} on {target}: {err}"
                raise SonosUpdateError(message) from err

            dispatch_soco = args_soco or self.soco  # type: ignore[union-attr]
            dispatcher_send(
                self.hass,
                f"{SONOS_SPEAKER_ACTIVITY}-{dispatch_soco.uid}",
                funct.__qualname__,
            )
            return result

        return wrapper

    return decorator


def _find_target_identifier(instance: Any, fallback_soco: SoCo | None) -> str | None:
    """Extract the best available target identifier from the provided instance object."""
    if entity_id := getattr(instance, "entity_id", None):
        # SonosEntity instance
        return entity_id
    if zone_name := getattr(instance, "zone_name", None):
        # SonosSpeaker instance
        return zone_name
    if speaker := getattr(instance, "speaker", None):
        # Holds a SonosSpeaker instance attribute
        return speaker.zone_name
    if soco := getattr(instance, "soco", fallback_soco):
        # Holds a SoCo instance attribute
        # Only use attributes with no I/O
        return soco._player_name or soco.ip_address  # noqa: SLF001
    return None


def hostname_to_uid(hostname: str) -> str:
    """Convert a Sonos hostname to a uid."""
    if hostname.startswith("Sonos-"):
        baseuid = hostname.removeprefix("Sonos-").replace(".local.", "")
    elif hostname.startswith("sonos"):
        baseuid = hostname.removeprefix("sonos").replace(".local.", "")
    else:
        raise ValueError(f"{hostname} is not a sonos device.")
    return f"{UID_PREFIX}{baseuid}{UID_POSTFIX}"


def sync_get_visible_zones(soco: SoCo) -> set[SoCo]:
    """Ensure I/O attributes are cached and return visible zones."""
    _ = soco.household_id
    _ = soco.uid
    return soco.visible_zones
