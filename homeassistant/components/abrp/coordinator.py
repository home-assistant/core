"""Telemetry coordinator for the A Better Routeplanner integration."""

import asyncio
from dataclasses import dataclass
import logging

from aioabrp import (
    AbrpApiError,
    AbrpAuthError,
    AbrpClient,
    AbrpVehicle,
    ConnectionEvent,
    ConnectionState,
    Telemetry,
    VehicleModelDisplay,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AbrpData:
    """Runtime data stored on the config entry."""

    vehicles: list[tuple[AbrpVehicle, VehicleModelDisplay | None]]
    telemetry_coordinator: AbrpTelemetryCoordinator


type AbrpConfigEntry = ConfigEntry[AbrpData]


async def async_fetch_garage(
    client: AbrpClient,
) -> list[tuple[AbrpVehicle, VehicleModelDisplay | None]]:
    """Fetch the garage once at setup, pairing each vehicle with its display."""
    try:
        raw_vehicles = await client.async_get_vehicles()
    except AbrpAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="abrp_session_invalid",
        ) from err
    except AbrpApiError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="abrp_update_failed",
        ) from err

    results = await asyncio.gather(
        *(
            client.async_get_vehicle_model_display(raw.vehicle_model)
            for raw in raw_vehicles
        ),
        return_exceptions=True,
    )
    paired: list[tuple[AbrpVehicle, VehicleModelDisplay | None]] = []
    for raw, result in zip(raw_vehicles, results, strict=True):
        if isinstance(result, AbrpAuthError):
            # Not fatal: the display lookup authenticates separately from the garage.
            _LOGGER.warning(
                "Display metadata for typecode %s rejected (%s); the device "
                "falls back to the raw typecode",
                raw.vehicle_model,
                result,
            )
            paired.append((raw, None))
            continue
        if isinstance(result, (AbrpApiError, TimeoutError)):
            _LOGGER.debug(
                "Display metadata for typecode %s failed (%s); the device "
                "falls back to the raw typecode",
                raw.vehicle_model,
                result,
            )
            paired.append((raw, None))
            continue
        if isinstance(result, BaseException):
            if isinstance(result, Exception):
                _LOGGER.warning(
                    "Unexpected display-metadata failure for typecode %s: %s",
                    raw.vehicle_model,
                    result,
                )
                paired.append((raw, None))
                continue
            raise result
        paired.append((raw, result))
    return paired


class AbrpTelemetryCoordinator(DataUpdateCoordinator[dict[int, Telemetry]]):
    """Thin push-mode coordinator for the v2 telemetry stream."""

    config_entry: AbrpConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AbrpConfigEntry,
    ) -> None:
        """Initialize the telemetry coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} telemetry",
            update_interval=None,
        )
        self.data = {}
        self.last_connection_event: ConnectionEvent | None = None
        self.stream_auth_failed: bool = False

    @callback
    def on_update(self, vehicle_id: int, telemetry: Telemetry) -> None:
        """Apply one stream frame and notify coordinator listeners.

        An empty frame is dropped before the notify fan-out.
        """
        if next(telemetry.items(), None) is None:
            return
        stored = self.data.get(vehicle_id)
        self.data[vehicle_id] = telemetry if stored is None else stored.merge(telemetry)
        self.async_set_updated_data(self.data)

    @callback
    def on_connection_change(self, event: ConnectionEvent) -> None:
        """Record a stream connection-state transition.

        Availability is value-based and deliberately ignores connection state:
        ABRP closes idle streams (~200 s) as steady state, so a disconnect only
        logs and never marks entities unavailable. ``AUTH_FAILED`` is the one
        exception: the library stops the stream for good, so entities stop
        claiming values nothing will refresh. Clearing that flag on a reconnect
        rather than on any later event is defensive: aioabrp returns from its
        run loop once it has dispatched ``AUTH_FAILED``, so today nothing
        follows it at all.
        """
        previous = self.last_connection_event
        changed = previous is None or previous.state is not event.state
        self.last_connection_event = event

        if changed:
            if event.state is ConnectionState.CONNECTED:
                _LOGGER.info("ABRP telemetry stream connected")
            elif event.state is ConnectionState.DISCONNECTED:
                _LOGGER.info(
                    "ABRP telemetry stream disconnected (%s)",
                    event.reason or "no reason given",
                )
            elif event.state is ConnectionState.AUTH_FAILED:
                _LOGGER.warning(
                    "ABRP telemetry stream auth failed (%s)",
                    event.reason or "no reason given",
                )

            if event.state is ConnectionState.AUTH_FAILED:
                self.stream_auth_failed = True
                self.async_update_listeners()
            elif event.state is ConnectionState.CONNECTED and self.stream_auth_failed:
                self.stream_auth_failed = False
                self.async_update_listeners()
