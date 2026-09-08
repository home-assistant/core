"""Teslemetry Data Coordinator."""

from dataclasses import asdict
from datetime import date, datetime, time, timedelta, tzinfo
from typing import TYPE_CHECKING, Any, override

from tesla_fleet_api.const import VehicleDataEndpoint
from tesla_fleet_api.exceptions import (
    GatewayTimeout,
    InsufficientCredits,
    InvalidResponse,
    InvalidToken,
    LoginRequired,
    RateLimited,
    ServiceUnavailable,
    SubscriptionRequired,
    TeslaFleetError,
)
from tesla_fleet_api.teslemetry import EnergySite, Teslemetry, Vehicle
from teslemetry_stream.const import EnergyTotalsEvent

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from . import TeslemetryConfigEntry

from .const import DOMAIN, LOGGER
from .helpers import async_update_device_sw_version, flatten

RETRY_EXCEPTIONS = (
    InvalidResponse,
    RateLimited,
    ServiceUnavailable,
    GatewayTimeout,
)


def _get_retry_after(e: TeslaFleetError) -> float:
    """Calculate wait time from exception."""
    if isinstance(e.data, dict):
        if after := e.data.get("after"):
            return float(after)
    return 10.0


VEHICLE_INTERVAL = timedelta(seconds=60)
VEHICLE_WAIT = timedelta(minutes=15)

# Kept well under Home Assistant's stage-2 setup budget (SLOW_SETUP_MAX_WAIT, 300s)
# so a sleeping vehicle raises ConfigEntryNotReady and the entry retries instead of
# being cancelled into a non-retried setup error.
VEHICLE_FIRST_REFRESH_TIMEOUT = 60
METADATA_INTERVAL = timedelta(hours=1)

# Start of the day the energy history totals cover. Kept out of
# ENERGY_HISTORY_FIELDS, which is the list of keys that become sensors.
PERIOD_START = "_period_start"

# Keys within tariff_content_v2 kept as nested dicts rather than flattened,
# since entities and calendars read them as whole structures.
TARIFF_SKIP_KEYS = ["daily_charges", "demand_charges", "energy_charges", "seasons"]

# Insufficient credits will not resolve themselves quickly, so back off polling
# instead of hammering the API at the coordinator's normal interval.
INSUFFICIENT_CREDITS_RETRY_AFTER = timedelta(hours=1).total_seconds()

ENDPOINTS = [
    VehicleDataEndpoint.CHARGE_STATE,
    VehicleDataEndpoint.CLIMATE_STATE,
    VehicleDataEndpoint.DRIVE_STATE,
    VehicleDataEndpoint.LOCATION_DATA,
    VehicleDataEndpoint.VEHICLE_STATE,
    VehicleDataEndpoint.VEHICLE_CONFIG,
]


class TeslemetryMetadataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to poll for subscription changes via metadata."""

    config_entry: TeslemetryConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslemetryConfigEntry,
        teslemetry: Teslemetry,
    ) -> None:
        """Initialize Teslemetry Metadata coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Teslemetry Metadata",
            update_interval=METADATA_INTERVAL,
        )
        self.teslemetry = teslemetry

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest metadata for subscription status."""
        try:
            data = await self.teslemetry.metadata()
        except (InvalidToken, SubscriptionRequired, LoginRequired) as e:
            raise ConfigEntryAuthFailed from e
        except RETRY_EXCEPTIONS as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"message": e.message},
                retry_after=_get_retry_after(e),
            ) from e
        except TeslaFleetError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"message": e.message},
            ) from e

        return data


class TeslemetryVehicleDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Teslemetry API."""

    config_entry: TeslemetryConfigEntry
    vin: str

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslemetryConfigEntry,
        api: Vehicle,
        product: dict[str, Any],
    ) -> None:
        """Initialize Teslemetry Vehicle Update Coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Teslemetry Vehicle",
        )
        if product["command_signing"] == "off":
            # Only allow automatic polling if its included
            self.update_interval = VEHICLE_INTERVAL

        self.api = api
        self.vin = product["vin"]
        self.data = flatten(product)

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Update vehicle data using Teslemetry API."""
        try:
            data = (await self.api.vehicle_data(endpoints=ENDPOINTS))["response"]
        except (InvalidToken, SubscriptionRequired, LoginRequired) as e:
            raise ConfigEntryAuthFailed from e
        except InsufficientCredits as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed_insufficient_credits",
                retry_after=INSUFFICIENT_CREDITS_RETRY_AFTER,
            ) from e
        except RETRY_EXCEPTIONS as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"message": e.message},
                retry_after=_get_retry_after(e),
            ) from e
        except TeslaFleetError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"message": e.message},
            ) from e

        data = flatten(data)
        if version := data.get("vehicle_state_car_version"):
            # Consume firmware opportunistically rather than through a listener
            # that would keep this coordinator polling after every entity is
            # disabled. Drop the build suffix (e.g. "2024.44.25 x" -> "2024.44.25").
            async_update_device_sw_version(
                self.hass, self.vin, self.config_entry.entry_id, version.split(" ")[0]
            )
        return data


def _index_wall_connectors(data: dict[str, Any]) -> dict[str, Any]:
    """Convert the live_status wall_connectors list into a DIN-keyed dict."""
    data["wall_connectors"] = {
        wc["din"]: wc for wc in (data.get("wall_connectors") or [])
    }
    return data


class TeslemetryEnergySiteLiveCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage energy site live status from the Teslemetry stream.

    Updates are driven by ``live_status`` stream events; the REST update
    method is retained for the deterministic setup cold read and manual
    recovery only.
    """

    config_entry: TeslemetryConfigEntry
    updated_once: bool

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslemetryConfigEntry,
        api: EnergySite,
        data: dict[str, Any],
    ) -> None:
        """Initialize Teslemetry Energy Site Live coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Teslemetry Energy Site Live",
        )
        self.api = api
        self.data = _index_wall_connectors(data)

    def handle_stream_update(self, data: dict[str, Any]) -> None:
        """Handle a live_status document from the stream."""
        self.async_set_updated_data(_index_wall_connectors(data))

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Update energy site data using Teslemetry API."""
        try:
            data: dict[str, Any] = (await self.api.live_status())["response"]
        except (InvalidToken, SubscriptionRequired, LoginRequired) as e:
            raise ConfigEntryAuthFailed from e
        except RETRY_EXCEPTIONS as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"message": e.message},
                retry_after=_get_retry_after(e),
            ) from e
        except TeslaFleetError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"message": e.message},
            ) from e
        return _index_wall_connectors(data)


class TeslemetryEnergySiteInfoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage energy site info from the Teslemetry stream.

    Site info and the V2 tariff are two independently replaceable partitions.
    The flattened coordinator view is recomposed from both whenever either
    changes, so a removed field or a cleared tariff never lingers. Stream
    events drive updates; the REST update method is retained for the
    deterministic setup cold read and manual recovery only.
    """

    config_entry: TeslemetryConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslemetryConfigEntry,
        api: EnergySite,
        product: dict[str, Any],
    ) -> None:
        """Initialize Teslemetry Energy Info coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Teslemetry Energy Site Info",
        )
        self.api = api
        self._site_info: dict[str, Any] = product
        self._tariff_content_v2: dict[str, Any] | None = None
        self.data = product

    def _compose(self) -> dict[str, Any]:
        """Flatten the two partitions into the coordinator view."""
        result = flatten(self._site_info, skip_keys=TARIFF_SKIP_KEYS)
        if self._tariff_content_v2 is not None:
            result.update(
                flatten(
                    {"tariff_content_v2": self._tariff_content_v2},
                    skip_keys=TARIFF_SKIP_KEYS,
                )
            )
        return result

    def _ingest_site_info(self, site_info: dict[str, Any]) -> dict[str, Any]:
        """Split a full REST site_info response into both partitions.

        The REST document carries both tariff versions inline; the V2 tariff
        moves to its own partition (matching the slim stream event shape) so
        removal semantics stay identical across both delivery paths.
        """
        site_info = dict(site_info)
        self._tariff_content_v2 = site_info.pop("tariff_content_v2", None)
        self._site_info = site_info
        return self._compose()

    def handle_site_info(self, site_info: dict[str, Any]) -> None:
        """Handle a slim site_info document from the stream."""
        self._site_info = site_info
        self.async_set_updated_data(self._compose())

    def handle_tariff_content_v2(self, tariff: dict[str, Any] | None) -> None:
        """Handle a V2 tariff document (or removal) from the stream."""
        self._tariff_content_v2 = tariff
        self.async_set_updated_data(self._compose())

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Update energy site data using Teslemetry API."""
        try:
            data = (await self.api.site_info())["response"]
        except (InvalidToken, SubscriptionRequired, LoginRequired) as e:
            raise ConfigEntryAuthFailed from e
        except RETRY_EXCEPTIONS as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"message": e.message},
                retry_after=_get_retry_after(e),
            ) from e
        except TeslaFleetError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"message": e.message},
            ) from e

        return self._ingest_site_info(data)


class TeslemetryEnergyHistoryCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage energy site history totals from the Teslemetry stream.

    The server sums each day's periods itself and publishes cumulative
    ``energy_totals``; there is no REST poll and no local accumulation.
    """

    config_entry: TeslemetryConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslemetryConfigEntry,
        site_id: int,
    ) -> None:
        """Initialize Teslemetry Energy History coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"Teslemetry Energy History {site_id}",
        )
        self.site_id = site_id
        self.time_zone: tzinfo | None = None
        self.data = {}

    async def async_set_time_zone(self, name: str | None) -> None:
        """Resolve the site's installation timezone."""
        if not name:
            return
        if (zone := await dt_util.async_get_time_zone(name)) is None:
            LOGGER.warning(
                "Unknown timezone %s for energy site %s, falling back to the Home Assistant timezone",
                name,
                self.site_id,
            )
            return
        self.time_zone = zone

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Return the current totals; there is nothing to fetch.

        Only reached through the generic entity update service, which must not
        fail on a coordinator the stream alone feeds.
        """
        return self.data

    def handle_stream_update(self, event: EnergyTotalsEvent) -> None:
        """Handle an energy_totals document from the stream."""
        data: dict[str, Any] = asdict(event.totals)
        # The server finalises a day after the site's local midnight, so a late
        # event must stay on the day it reports rather than the current one.
        data[PERIOD_START] = datetime.combine(
            date.fromisoformat(event.date),
            time(),
            tzinfo=self.time_zone or dt_util.get_default_time_zone(),
        )
        self.async_set_updated_data(data)
