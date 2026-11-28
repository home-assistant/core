"""Teslemetry Data Coordinator."""

from abc import abstractmethod
from copy import deepcopy
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, tzinfo
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, override

from aiopowerwall import PowerwallClient, PowerwallEnergySite, PowerwallError
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
from tesla_fleet_api.router import (
    LOCAL_SITE_INFO_KEYS,
    merge_live_status,
    merge_site_info,
)
from tesla_fleet_api.teslemetry import EnergySite, Teslemetry, Vehicle
from teslemetry_stream.const import EnergyTotalsEvent, WallConnectorTotalsEvent

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_interval
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
METADATA_INTERVAL = timedelta(hours=1)
# A paired Powerwall's LAN gateway is not on the stream, so it is polled: the
# live document every 5s and the slower-changing config.json every 30s.
ENERGY_LIVE_INTERVAL = timedelta(seconds=5)
ENERGY_LIVE_LOCAL_MAX_BACKOFF = timedelta(minutes=1)
ENERGY_CONFIG_INTERVAL = timedelta(seconds=30)
LOCAL_STATUS_INTERVAL = timedelta(seconds=10)

# Start of the day the energy history totals cover. Kept out of
# ENERGY_HISTORY_FIELDS, which is the list of keys that become sensors.
PERIOD_START = "_period_start"

# Wh delivered per Wall Connector DIN on the reported day.
WALL_CONNECTOR_TOTALS = "totals"

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

    Cloud updates are driven by ``live_status`` stream events; the REST update
    method is retained for the deterministic setup cold read and manual
    recovery only, so success/error state is stream-owned. A paired site also
    polls its LAN gateway and overlays the locally-owned keys, without touching
    that state.
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
        self._local: PowerwallEnergySite | None = None
        # Kept un-indexed as the merge base, since _index_wall_connectors mutates.
        self._cloud_live = deepcopy(data)
        self._local_live: dict[str, Any] | None = None
        self._local_poll_in_progress = False
        self._local_backoff_ticks = 1
        self._local_ticks_to_skip = 0
        self.data = _index_wall_connectors(data)

    def enable_local_polling(self, local: PowerwallEnergySite) -> None:
        """Poll a paired site's LAN gateway and merge it over the cloud stream."""
        self._local = local
        # Its own timer, not update_interval, so stream pushes cannot postpone it.
        self.config_entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                partial(self._async_local_poll, local),
                ENERGY_LIVE_INTERVAL,
            )
        )

    async def _async_local_poll(
        self, local: PowerwallEnergySite, now: datetime
    ) -> None:
        """Read the LAN gateway and publish the merged view.

        A failed read falls back to the cloud values and doubles the gap between
        reads up to ENERGY_LIVE_LOCAL_MAX_BACKOFF.
        """
        # live_status is several sequential reads and can outrun the interval.
        if self._local_poll_in_progress:
            return
        # Skip ticks rather than reschedule so the unload-cancelled timer is kept.
        if self._local_ticks_to_skip:
            self._local_ticks_to_skip -= 1
            return
        self._local_poll_in_progress = True
        try:
            try:
                self._local_live = (await local.live_status())["response"]
            except PowerwallError as e:
                self._local_live = None
                LOGGER.log(
                    logging.DEBUG if self._local_backoff_ticks > 1 else logging.WARNING,
                    "Local live poll for %s failed, using cloud values: %s",
                    self.api.energy_site_id,
                    e,
                )
                self._local_backoff_ticks = min(
                    self._local_backoff_ticks * 2,
                    ENERGY_LIVE_LOCAL_MAX_BACKOFF // ENERGY_LIVE_INTERVAL,
                )
                self._local_ticks_to_skip = self._local_backoff_ticks - 1
            else:
                if self._local_backoff_ticks > 1:
                    LOGGER.info(
                        "Local live poll for %s recovered", self.api.energy_site_id
                    )
                self._local_backoff_ticks = 1
            self.data = self._merged()
            # Not async_set_updated_data: availability stays with the stream.
            self.async_update_listeners()
        finally:
            self._local_poll_in_progress = False

    def _merged(self) -> dict[str, Any]:
        """Overlay the cached local snapshot onto the cached cloud snapshot."""
        return _index_wall_connectors(
            merge_live_status(self._cloud_live, self._local_live)
        )

    def handle_stream_update(self, data: dict[str, Any]) -> None:
        """Handle a live_status document from the stream."""
        if self._local is None:
            self.async_set_updated_data(_index_wall_connectors(data))
            return
        self._cloud_live = data
        self.async_set_updated_data(self._merged())

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Cold-read the cloud live_status (setup and manual recovery only)."""
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
        if self._local is None:
            return _index_wall_connectors(data)
        self._cloud_live = data
        return self._merged()


class TeslemetryEnergySiteInfoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage energy site info from the Teslemetry stream.

    Site info and the V2 tariff are two independently replaceable partitions.
    The flattened coordinator view is recomposed from both whenever either
    changes, so a removed field or a cleared tariff never lingers. Cloud updates
    are driven by stream events; the REST update method is retained for the
    deterministic setup cold read and manual recovery only, so success/error
    state is stream-owned. A paired site also polls its LAN ``config.json`` and
    overlays the locally-owned keys, without touching that state.
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
        self._local: PowerwallEnergySite | None = None
        self._local_config: dict[str, Any] | None = None
        self._cloud_optimistic: dict[str, Any] = {}
        # Lets a poll in flight detect a command that landed during its read.
        self._local_config_generation = 0
        self._local_poll_in_progress = False
        self.data = product

    def enable_local_polling(self, local: PowerwallEnergySite) -> None:
        """Poll a paired site's LAN config.json and merge it over the cloud."""
        self._local = local
        # Its own timer, not update_interval, so stream pushes cannot postpone it.
        self.config_entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                partial(self._async_local_poll, local),
                ENERGY_CONFIG_INTERVAL,
            )
        )

    async def _async_local_poll(
        self, local: PowerwallEnergySite, now: datetime
    ) -> None:
        """Read the LAN config.json and publish the merged view.

        A failed read falls back to the cloud values.
        """
        if self._local_poll_in_progress:
            return
        self._local_poll_in_progress = True
        generation = self._local_config_generation
        try:
            try:
                local_config = await local.local_config()
            except PowerwallError as e:
                local_config = None
                LOGGER.debug(
                    "Local config poll for %s failed, using cloud values: %s",
                    self.api.energy_site_id,
                    e,
                )
            # A command landed mid-read, so this snapshot predates its value.
            if self._local_config_generation != generation:
                return
            self._local_config = local_config
            if local_config is not None:
                for key in LOCAL_SITE_INFO_KEYS:
                    # A key the gateway did not report keeps its held value.
                    if local_config.get(key) is not None:
                        self._cloud_optimistic.pop(key, None)
            self.data = self._merged()
            # Not async_set_updated_data: availability stays with the stream.
            self.async_update_listeners()
        finally:
            self._local_poll_in_progress = False

    def async_set_command_value(self, key: str, value: Any) -> None:
        """Hold a paired site's successful command value until its source next reports.

        A locally-owned key is held until a LAN poll reports it, and every key
        until the next cloud site_info, so neither a poll in between nor a
        failed LAN poll can revert it.
        """
        if self._local is None:
            return
        if key in LOCAL_SITE_INFO_KEYS:
            self._local_config = {**(self._local_config or {}), key: value}
            self._local_config_generation += 1
        self._cloud_optimistic[key] = value
        self.data = self._merged()
        self.async_update_listeners()

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

    def _merged(self) -> dict[str, Any]:
        """Overlay the local config onto the cloud view and held command values."""
        return merge_site_info(
            self._compose() | self._cloud_optimistic, self._local_config
        )

    def _ingest_site_info(self, site_info: dict[str, Any]) -> dict[str, Any]:
        """Split a full REST site_info response into both partitions.

        The REST document carries both tariff versions inline; the V2 tariff
        moves to its own partition (matching the slim stream event shape) so
        removal semantics stay identical across both delivery paths.
        """
        site_info = dict(site_info)
        self._tariff_content_v2 = site_info.pop("tariff_content_v2", None)
        self._site_info = site_info
        self._cloud_optimistic = {}
        return self._merged()

    def handle_site_info(self, site_info: dict[str, Any]) -> None:
        """Handle a slim site_info document from the stream."""
        self._site_info = site_info
        self._cloud_optimistic = {}
        self.async_set_updated_data(self._merged())

    def handle_tariff_content_v2(self, tariff: dict[str, Any] | None) -> None:
        """Handle a V2 tariff document (or removal) from the stream."""
        self._tariff_content_v2 = tariff
        self.async_set_updated_data(self._merged())

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Cold-read the cloud site_info (setup and manual recovery only)."""
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


class TeslemetryStreamTotalsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Base class for daily energy totals pushed by the Teslemetry stream.

    The server sums each day itself and publishes the totals; there is no
    REST poll and no local accumulation.
    """

    config_entry: TeslemetryConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslemetryConfigEntry,
        site_id: int,
        name: str,
    ) -> None:
        """Initialize the stream totals coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{name} {site_id}",
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

    def _period_start(self, day: str) -> datetime:
        """Return the start of a site-local day reported by the stream."""
        # The server finalises a day after the site's local midnight, so a late
        # event must stay on the day it reports rather than the current one.
        return datetime.combine(
            date.fromisoformat(day),
            time(),
            tzinfo=self.time_zone or dt_util.get_default_time_zone(),
        )


class TeslemetryEnergyHistoryCoordinator(TeslemetryStreamTotalsCoordinator):
    """Class to manage energy site history totals from the Teslemetry stream."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslemetryConfigEntry,
        site_id: int,
    ) -> None:
        """Initialize Teslemetry Energy History coordinator."""
        super().__init__(hass, config_entry, site_id, "Teslemetry Energy History")

    def handle_stream_update(self, event: EnergyTotalsEvent) -> None:
        """Handle an energy_totals document from the stream."""
        data: dict[str, Any] = asdict(event.totals)
        data[PERIOD_START] = self._period_start(event.date)
        self.async_set_updated_data(data)


class TeslemetryLocalCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Base class for polling a locally paired Powerwall gateway."""

    config_entry: TeslemetryConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslemetryConfigEntry,
        client: PowerwallClient,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize a local Powerwall coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
        )
        self.client = client

    @abstractmethod
    async def _async_fetch(self) -> _DataT:
        """Fetch the payload from the local gateway."""

    @override
    async def _async_update_data(self) -> _DataT:
        """Update data from the local gateway."""
        try:
            return await self._async_fetch()
        except PowerwallError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="local_update_failed",
                translation_placeholders={"message": str(e)},
            ) from e


class TeslemetryLocalStatusCoordinator(TeslemetryLocalCoordinator[dict[str, Any]]):
    """Class to poll the status of a locally paired Powerwall gateway."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslemetryConfigEntry,
        client: PowerwallClient,
        site_id: int,
    ) -> None:
        """Initialize the local Powerwall status coordinator."""
        super().__init__(
            hass,
            config_entry,
            client,
            f"Teslemetry Powerwall Status {site_id}",
            LOCAL_STATUS_INTERVAL,
        )

    @override
    async def _async_fetch(self) -> dict[str, Any]:
        """Fetch the gateway status."""
        return await self.client.get_status()


class TeslemetryWallConnectorTotalsCoordinator(TeslemetryStreamTotalsCoordinator):
    """Class to manage daily Wall Connector energy totals from the Teslemetry stream."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslemetryConfigEntry,
        site_id: int,
    ) -> None:
        """Initialize Teslemetry Wall Connector Totals coordinator."""
        super().__init__(
            hass, config_entry, site_id, "Teslemetry Wall Connector Totals"
        )
        self._created_at: datetime | None = None

    def handle_stream_update(self, event: WallConnectorTotalsEvent) -> None:
        """Handle a wall_connector_totals document from the stream."""
        # A connect-time replay can be older than a live event already applied.
        if self._created_at is not None and event.created_at < self._created_at:
            return
        self._created_at = event.created_at
        self.async_set_updated_data(
            {
                WALL_CONNECTOR_TOTALS: event.totals,
                PERIOD_START: self._period_start(event.date),
            }
        )
