"""Telemetry coordinator for the A Better Routeplanner integration."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging

from aioabrp import (
    AbrpApiError,
    AbrpAuthError,
    AbrpClient,
    AbrpVehicle,
    ConnectionEvent,
    ConnectionState,
    Metric,
    Telemetry,
    TelemetryStream,
    VehicleModelDisplay,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import TimestampDataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AbrpData:
    """Runtime data stored on the config entry."""

    session: OAuth2Session
    vehicles: list[tuple[AbrpVehicle, VehicleModelDisplay | None]]
    telemetry_coordinator: AbrpTelemetryCoordinator
    stream: TelemetryStream | None


type AbetterrouteplannerConfigEntry = ConfigEntry[AbrpData]


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
            _LOGGER.debug(
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


class AbrpTelemetryCoordinator(TimestampDataUpdateCoordinator[dict[int, Telemetry]]):
    """Thin push-mode coordinator for the v2 telemetry stream."""

    config_entry: AbetterrouteplannerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AbetterrouteplannerConfigEntry,
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
        # Receipt time, not the wire timestamp.
        self.last_reported_at: dict[int, dict[Metric, datetime]] = {}
        # Sticky on omission: a frame without a provider keeps the prior value.
        self.last_provider: dict[int, dict[Metric, str]] = {}
        self.last_connection_event: ConnectionEvent | None = None
        self.last_connection_at: datetime | None = None
        self.connect_count: int = 0
        self.stream_auth_failed: bool = False

    @callback
    def _apply_metrics(self, vehicle_id: int, delta: Telemetry) -> None:
        """Apply a typed Telemetry delta to the per-vehicle state.

        Does not notify coordinator listeners — the caller decides.
        """
        if next(delta.items(), None) is None:
            return
        now = dt_util.utcnow()
        stored = self.data.get(vehicle_id)
        self.data[vehicle_id] = delta if stored is None else stored.merge(delta)
        reported = self.last_reported_at.setdefault(vehicle_id, {})
        providers = self.last_provider.setdefault(vehicle_id, {})
        for metric, metric_value in delta.items():
            reported[metric] = now
            if metric_value.provider is not None:
                providers[metric] = metric_value.provider

    @callback
    def on_update(self, vehicle_id: int, telemetry: Telemetry) -> None:
        """Apply one stream frame and notify coordinator listeners.

        An empty frame is dropped before the notify fan-out.
        """
        if next(telemetry.items(), None) is None:
            return
        self._apply_metrics(vehicle_id, telemetry)
        now = dt_util.utcnow()
        self.async_set_updated_data(self.data)
        # ``async_set_updated_data`` skips the polling path that stamps this.
        self.last_update_success_time = now

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
        self.last_connection_at = dt_util.utcnow()
        if event.state is ConnectionState.CONNECTED:
            self.connect_count += 1

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
