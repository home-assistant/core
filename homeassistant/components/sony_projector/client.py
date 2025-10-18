"""Client helpers for the Sony Projector integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
import logging
import time
from typing import Any

import pysdcp_extended

from .const import CONTROL_PORT, DISCOVERY_PORT, DISCOVERY_TIMEOUT

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DiscoveredProjector:
    """Representation of a discovered projector."""

    host: str
    model: str | None
    serial: str | None


@dataclass(slots=True)
class ProjectorState:
    """State snapshot for a projector."""

    is_on: bool
    current_input: str | None
    inputs: list[str]
    picture_mute: bool | None
    lamp_hours: int | None
    aspect_ratio: str | None
    aspect_ratio_options: list[str]
    picture_mode: str | None
    picture_mode_options: list[str]
    model: str | None
    serial: str | None


class ProjectorClientError(Exception):
    """Raised when a projector operation fails."""


class ProjectorClient:
    """Async wrapper around the pysdcp extended projector client."""

    def __init__(self, host: str) -> None:
        """Initialize the projector client."""

        self._host = host
        self._projector = pysdcp_extended.Projector(host)
        self._model: str | None = None
        self._serial: str | None = None

    @property
    def host(self) -> str:
        """Return the host for the projector."""

        return self._host

    @property
    def model(self) -> str | None:
        """Return the cached model for the projector."""

        return self._model

    @property
    def serial(self) -> str | None:
        """Return the cached serial for the projector."""

        return self._serial

    async def async_refresh_device_info(self) -> None:
        """Refresh cached model and serial information."""

        try:
            info = await _run_in_executor(
                self._projector.get_pjinfo,
                timeout=DISCOVERY_TIMEOUT,
                udp_port=DISCOVERY_PORT,
            )
        except Exception as err:
            raise ProjectorClientError(
                "Unable to retrieve projector information"
            ) from err

        self._model = info.get("model")
        serial = info.get("serial")
        self._serial = str(serial) if serial is not None else None

    async def async_get_state(self) -> ProjectorState:
        """Return the current projector state."""

        try:
            is_on = await _run_in_executor(self._projector.get_power)
            current_input = await _run_in_executor(self._projector.get_input)
        except Exception as err:
            raise ProjectorClientError("Failed to query projector state") from err

        picture_mute = await _call_optional(self._projector.get_muting)
        lamp_hours_raw = await _call_optional(self._projector.get_lamp_hours)
        lamp_hours = int(lamp_hours_raw) if lamp_hours_raw is not None else None

        aspect_ratio = await _call_screen_get(
            "ASPECT_RATIO", pysdcp_extended.ASPECT_RATIOS, self._projector
        )
        picture_mode = await _call_screen_get(
            "CALIBRATION_PRESET",
            pysdcp_extended.CALIBRATION_PRESETS,
            self._projector,
        )

        # Capture updated device information from the projector metadata if available.
        info = self._projector.info
        if info.product_name:
            self._model = info.product_name
        if info.serial_number:
            self._serial = str(info.serial_number)

        return ProjectorState(
            is_on=bool(is_on),
            current_input=current_input,
            inputs=["HDMI 1", "HDMI 2"],
            picture_mute=picture_mute,
            lamp_hours=lamp_hours,
            aspect_ratio=aspect_ratio,
            aspect_ratio_options=sorted(pysdcp_extended.ASPECT_RATIOS.keys()),
            picture_mode=picture_mode,
            picture_mode_options=sorted(pysdcp_extended.CALIBRATION_PRESETS.keys()),
            model=self._model,
            serial=self._serial,
        )

    async def async_set_power(self, on: bool) -> None:
        """Set the power state for the projector."""

        try:
            await _run_in_executor(self._projector.set_power, on)
        except Exception as err:
            raise ProjectorClientError("Unable to set power state") from err

    async def async_set_input(self, source: str) -> None:
        """Select a HDMI input."""

        hdmi_number = 1 if source.endswith("1") else 2
        try:
            await _run_in_executor(self._projector.set_HDMI_input, hdmi_number)
        except Exception as err:
            raise ProjectorClientError("Unable to set projector input") from err

    async def async_set_picture_mute(self, mute: bool) -> None:
        """Set the projector picture mute status."""

        try:
            await _run_in_executor(self._projector.set_muting, mute)
        except Exception as err:
            raise ProjectorClientError("Unable to set picture muting") from err

    async def async_toggle_picture_mute(self) -> None:
        """Toggle the picture mute state."""

        current = await _call_optional(self._projector.get_muting)
        await self.async_set_picture_mute(not current if current is not None else True)

    async def async_set_aspect_ratio(self, option: str) -> None:
        """Set the projector aspect ratio."""

        await _call_screen_set(
            "ASPECT_RATIO", option, pysdcp_extended.ASPECT_RATIOS, self._projector
        )

    async def async_set_picture_mode(self, option: str) -> None:
        """Set the projector picture mode."""

        await _call_screen_set(
            "CALIBRATION_PRESET",
            option,
            pysdcp_extended.CALIBRATION_PRESETS,
            self._projector,
        )


async def async_discover(
    loop: Any, timeout: float = DISCOVERY_TIMEOUT
) -> list[DiscoveredProjector]:
    """Discover projectors via SDAP."""

    return await loop.run_in_executor(None, partial(_discover_sync, timeout))


def _discover_sync(timeout: float) -> list[DiscoveredProjector]:
    """Perform synchronous discovery on a background thread."""

    discovered: dict[str, DiscoveredProjector] = {}
    deadline = time.monotonic() + timeout

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break

        projector = pysdcp_extended.Projector(
            udp_port=DISCOVERY_PORT,
            tcp_port=CONTROL_PORT,
        )

        try:
            result = projector.find_projector(timeout=remaining)
        except OSError as err:
            _LOGGER.debug("Discovery socket error: %s", err)
            break
        except Exception as err:  # noqa: BLE001 - library raises generic exceptions
            _LOGGER.debug("Unexpected discovery failure: %s", err)
            break

        if result is False:
            break
        if not projector.is_init or projector.info is None:
            continue

        serial = projector.info.serial_number
        serial_str = str(serial) if serial is not None else None
        discovered[projector.ip] = DiscoveredProjector(
            host=projector.ip,
            model=projector.info.product_name,
            serial=serial_str,
        )

    return list(discovered.values())


async def _run_in_executor(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run a synchronous function in the executor."""

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


async def _call_optional(func: Callable[[], Any]) -> Any:
    """Call a function that may not be supported by the projector."""

    try:
        return await _run_in_executor(func)
    except Exception:  # noqa: BLE001 - projector may not support the call
        return None


async def _call_screen_get(
    command: str,
    options: dict[str, int],
    projector: pysdcp_extended.Projector,
) -> str | None:
    """Query a screen setting if supported."""

    try:
        value = await _run_in_executor(
            projector._send_command,  # noqa: SLF001 - library does not expose a helper
            pysdcp_extended.ACTIONS["GET"],
            pysdcp_extended.COMMANDS[command],
        )
    except Exception:  # noqa: BLE001
        return None

    for name, option_value in options.items():
        if option_value == value:
            return name

    return None


async def _call_screen_set(
    command: str,
    option: str,
    options: dict[str, int],
    projector: pysdcp_extended.Projector,
) -> None:
    """Set a screen configuration on the projector."""

    if option not in options:
        raise ProjectorClientError(f"Unsupported option {option} for {command}")

    try:
        await _run_in_executor(
            projector._send_command,  # noqa: SLF001 - library does not expose a helper
            pysdcp_extended.ACTIONS["SET"],
            pysdcp_extended.COMMANDS[command],
            options[option],
        )
    except Exception as err:
        raise ProjectorClientError(f"Failed to set {command}") from err
