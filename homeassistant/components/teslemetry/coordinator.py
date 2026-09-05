"""Teslemetry Data Coordinator."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, override

from aiopowerwall import PowerwallEnergySite, PowerwallError
from tesla_fleet_api.const import TeslaEnergyPeriod, VehicleDataEndpoint
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
from tesla_fleet_api.router import merge_live_status, merge_site_info
from tesla_fleet_api.teslemetry import EnergySite, Teslemetry, Vehicle

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from . import TeslemetryConfigEntry

from .const import DOMAIN, ENERGY_HISTORY_FIELDS, LOGGER
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
ENERGY_HISTORY_INTERVAL = timedelta(seconds=60)
METADATA_INTERVAL = timedelta(hours=1)
# A paired Powerwall's LAN gateway is not on the stream, so it is polled: the
# live document every 5s and the slower-changing config.json every 30s.
ENERGY_LIVE_INTERVAL = timedelta(seconds=5)
ENERGY_CONFIG_INTERVAL = timedelta(seconds=30)

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
    recovery only. Success/error state is therefore stream-owned. A paired site
    additionally polls its LAN gateway on an independent timer (never via
    ``update_interval``, so a burst of stream pushes cannot postpone it) and
    overlays the locally-owned keys onto the cloud document via
    ``merge_live_status``, re-running the merge on every update from either side
    so neither cadence can transiently clobber the other's keys. Both the local
    poll and a paired stream push publish directly with ``async_update_listeners``
    rather than through the update path, so a local poll never touches the
    stream-owned success/error state; a key the gateway does not serve, or a
    failed poll, falls back to the cloud value.
    """

    config_entry: TeslemetryConfigEntry
    updated_once: bool
    # Raw, un-indexed cloud snapshot merged against on a paired site; seeded
    # from the pre-index cold read and refreshed on every stream push.
    _cloud_live: dict[str, Any]

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
        self._local_live: dict[str, Any] | None = None
        self._local_poll_in_progress = False
        self.data = _index_wall_connectors(data)

    def enable_local_polling(
        self, local: PowerwallEnergySite, cloud_live: dict[str, Any]
    ) -> None:
        """Poll a paired site's LAN gateway and merge it over the cloud stream.

        The poll runs on its own interval rather than ``update_interval`` so a
        stream push can never postpone it. The timer is cancelled on unload.
        """
        self._local = local
        self._cloud_live = cloud_live
        self.config_entry.async_on_unload(
            async_track_time_interval(
                self.hass, self._async_local_poll, ENERGY_LIVE_INTERVAL
            )
        )

    async def _async_local_poll(self, now: datetime) -> None:
        """Read the LAN gateway on the interval and publish the merged view.

        Publishes with ``async_update_listeners`` rather than through the update
        path, so a poll never touches the stream-owned success/error state. A
        failed poll degrades the owned keys to their cloud values.
        """
        # live_status performs sequential network reads that can exceed the
        # interval; skip a tick while a poll is still running so a slow poll
        # cannot replace a newer snapshot with stale data.
        if self._local is None or self._local_poll_in_progress:
            return
        self._local_poll_in_progress = True
        try:
            try:
                self._local_live = (await self._local.live_status())["response"]
            except PowerwallError as e:
                self._local_live = None
                LOGGER.debug(
                    "Local live poll for %s failed, using cloud values: %s",
                    self.api.energy_site_id,
                    e,
                )
            self.data = self._merged()
            self.async_update_listeners()
        finally:
            self._local_poll_in_progress = False

    def _merged(self) -> dict[str, Any]:
        """Overlay the cached local snapshot onto the cached cloud snapshot.

        Both snapshots stay raw; ``_index_wall_connectors`` runs once here on the
        merge result, since it is not idempotent and ``wall_connectors`` is never
        locally owned.
        """
        return _index_wall_connectors(
            merge_live_status(self._cloud_live, self._local_live)
        )

    def handle_stream_update(self, data: dict[str, Any]) -> None:
        """Handle a live_status document from the stream."""
        if self._local is None:
            self.async_set_updated_data(_index_wall_connectors(data))
            return
        # A paired site's local poll is timer-driven and its success/error state
        # is stream-owned, so publish the re-merged push directly: this resets no
        # timer and does not run through the update path. The re-merge keeps a
        # push from reverting a locally-owned key between local polls.
        self._cloud_live = data
        self.data = self._merged()
        self.async_update_listeners()

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Cold-read the cloud live_status (setup and manual recovery only).

        A paired site's LAN gateway is polled by :meth:`_async_local_poll` on its
        own timer, never through this stream-owned update path.
        """
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
    changes, so a removed field or a cleared tariff never lingers. Cloud updates
    are driven by stream events; the REST update method is retained for the
    deterministic setup cold read and manual recovery only. Success/error state
    is therefore stream-owned, which is what the cloud-only site-info and tariff
    entities key their availability off. A paired site additionally polls its LAN
    gateway's ``config.json`` on an independent timer (never via
    ``update_interval``) and overlays the locally-owned keys onto the composed
    cloud view via ``merge_site_info``, re-running the merge on every update from
    either side. That poll publishes directly with ``async_update_listeners``
    rather than through the update path, so it never touches the stream-owned
    success/error state; a key the gateway does not serve, or a failed poll,
    falls back to the cloud value.
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
        self._local_poll_in_progress = False
        self.data = product

    def enable_local_polling(self, local: PowerwallEnergySite) -> None:
        """Poll a paired site's LAN config.json and merge it over the cloud.

        The poll runs on its own interval rather than ``update_interval`` so a
        stream push can never postpone it. The timer is cancelled on unload.
        """
        self._local = local
        self.config_entry.async_on_unload(
            async_track_time_interval(
                self.hass, self._async_local_poll, ENERGY_CONFIG_INTERVAL
            )
        )

    async def _async_local_poll(self, now: datetime) -> None:
        """Read the LAN config.json on the interval and publish the merged view.

        Publishes with ``async_update_listeners`` rather than through the update
        path, so a poll never touches the stream-owned success/error state that
        the cloud-only entities depend on. A failed poll degrades the owned keys
        to their cloud values.
        """
        # Skip a tick while a poll is still running so a slow poll cannot replace
        # a newer snapshot with stale data.
        if self._local is None or self._local_poll_in_progress:
            return
        self._local_poll_in_progress = True
        try:
            try:
                self._local_config = await self._local.local_config()
            except PowerwallError as e:
                self._local_config = None
                LOGGER.debug(
                    "Local config poll for %s failed, using cloud values: %s",
                    self.api.energy_site_id,
                    e,
                )
            self.data = self._merged()
            self.async_update_listeners()
        finally:
            self._local_poll_in_progress = False

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
        """Overlay the cached local config onto the composed cloud view."""
        return merge_site_info(self._compose(), self._local_config)

    def _ingest_site_info(self, site_info: dict[str, Any]) -> dict[str, Any]:
        """Split a full REST site_info response into both partitions.

        The REST document carries both tariff versions inline; the V2 tariff
        moves to its own partition (matching the slim stream event shape) so
        removal semantics stay identical across both delivery paths.
        """
        site_info = dict(site_info)
        self._tariff_content_v2 = site_info.pop("tariff_content_v2", None)
        self._site_info = site_info
        return self._merged()

    def handle_site_info(self, site_info: dict[str, Any]) -> None:
        """Handle a slim site_info document from the stream."""
        self._site_info = site_info
        self.async_set_updated_data(self._merged())

    def handle_tariff_content_v2(self, tariff: dict[str, Any] | None) -> None:
        """Handle a V2 tariff document (or removal) from the stream."""
        self._tariff_content_v2 = tariff
        self.async_set_updated_data(self._merged())

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Cold-read the cloud site_info (setup and manual recovery only).

        A paired site's LAN ``config.json`` is polled by :meth:`_async_local_poll`
        on its own timer, never through this stream-owned update path.
        """
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
    """Class to manage fetching energy site info from the Teslemetry API."""

    config_entry: TeslemetryConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslemetryConfigEntry,
        api: EnergySite,
    ) -> None:
        """Initialize Teslemetry Energy Info coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"Teslemetry Energy History {api.energy_site_id}",
            update_interval=ENERGY_HISTORY_INTERVAL,
        )
        self.api = api
        self.data = {}

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Update energy site data using Teslemetry API."""
        try:
            data = (await self.api.energy_history(TeslaEnergyPeriod.DAY))["response"]
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

        if not data or not isinstance(data.get("time_series"), list):
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed_invalid_data",
            )

        # Add all time periods together
        output = dict.fromkeys(ENERGY_HISTORY_FIELDS, None)
        for period in data.get("time_series", []):
            for key in ENERGY_HISTORY_FIELDS:
                if key in period:
                    if output[key] is None:
                        output[key] = period[key]
                    else:
                        output[key] += period[key]

        return output
