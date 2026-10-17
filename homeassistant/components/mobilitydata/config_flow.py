"""Config flow for the MobilityData integration."""

import asyncio
from collections import Counter
from collections.abc import Mapping
import json
import logging
from statistics import median
from typing import Any, override

from aiomobilitydatabase import (
    DataType,
    FeedStatus,
    GtfsRtFeed,
    MobilityDatabaseAuthenticationError,
    MobilityDatabaseConnectionError,
    MobilityDatabaseError,
)
from aiomobilitydatabase.feeds import (
    ArrivalsQuery,
    Circle,
    MobilityFeedsClient,
    MobilityFeedsError,
    Route,
    SourceAuthenticationError,
    StaticBuildProgress,
    StationGroup,
    TransitFeedHandle,
)
import probatio

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_LOCATION, CONF_STOP, CONF_ZONE
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    LocationSelector,
    LocationSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import _cache_dir
from .const import (
    CONF_FEED_ID,
    CONF_REFRESH_TOKEN,
    CONF_ROUTE_DESTINATIONS,
    CONF_ROUTE_IDS,
    CONF_SEARCH_QUERY,
    CONF_STATION_ID,
    CONF_STOP_IDS,
    CONF_STOP_NAME,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
)
from .coordinator import MobilityDataConfigEntry, requires_api_key

_LOGGER = logging.getLogger(__name__)

ACCOUNT_URL = "https://mobilitydatabase.org"

TOKEN_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_REFRESH_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)
API_KEY_SCHEMA = probatio.Schema(
    {
        # Optional: a blank key runs the entry on the published schedule
        # alone, rather than locking out everyone without a producer key.
        probatio.Optional(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)


def _coverage_center(handle: TransitFeedHandle) -> dict[str, float] | None:
    """Return the center of the feed's stops for the map picker.

    Computed from the indexed stops rather than catalog metadata (the
    catalog's dataset bounding box is unpopulated for many feeds), using the
    median so outlying suburban stops don't drag the center away from the
    system's core.
    """
    latitudes = [stop.latitude for stop in handle.stops if stop.latitude is not None]
    longitudes = [stop.longitude for stop in handle.stops if stop.longitude is not None]
    if not latitudes or not longitudes:
        return None
    return {
        "latitude": median(latitudes),
        "longitude": median(longitudes),
        "radius": 1000,
    }


def _auth_info_url(rt_feeds: list[GtfsRtFeed], feed_id: str) -> str | None:
    """Return where to get an API key, or None if no sibling needs one.

    Falls back to the feed's Mobility Database page when the provider does
    not publish authentication instructions.
    """
    for rt_feed in rt_feeds:
        if requires_api_key(rt_feed):
            assert rt_feed.source_info is not None
            return (
                rt_feed.source_info.authentication_info_url
                or f"{ACCOUNT_URL}/feeds/{feed_id}"
            )
    return None


async def _probe_realtime(handle: TransitFeedHandle) -> str | None:
    """Return an error key if the realtime producer refuses us, else None.

    The producer key authenticates REALTIME fetches, not the catalog or the
    static download, so opening the feed proves nothing -- only an actual
    realtime request does. One arrivals query over a single stop is the
    smallest call that makes one.
    """
    if not handle.stops:
        return None
    try:
        await handle.get_arrivals([ArrivalsQuery([handle.stops[0].id])])
    except SourceAuthenticationError:
        return "invalid_auth"
    except MobilityDatabaseError, MobilityFeedsError:
        return "cannot_connect"
    return None


# A station id comes from the feed and never contains this, so it cleanly
# separates the station from the JSON-encoded filters in a board's id.
_BOARD_ID_SEPARATOR = "#"
# Enough routes to tell two same-named stations apart, short enough to read.
_MAX_DISAMBIGUATING_ROUTES = 6


class MobilityDataConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MobilityData."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._client: MobilityFeedsClient | None = None
        self._refresh_token: str | None = None
        self._feed_options: list[SelectOptionDict] = []
        self._static_feed_id: str | None = None
        self._title: str | None = None
        self._api_key: str | None = None
        self._api_key_error: str | None = None
        self._auth_url: str | None = None
        self._build_task: asyncio.Task[None] | None = None
        self._build_error: str | None = None

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {SUBENTRY_TYPE_STOP: StopSubentryFlowHandler}

    @callback
    @override
    def async_remove(self) -> None:
        """Clean up the flow's client when the flow is removed."""
        if self._client is not None:
            self.hass.async_create_task(self._client.close())

    def _get_client(self) -> MobilityFeedsClient:
        assert self._refresh_token is not None
        if self._client is None:
            self._client = MobilityFeedsClient(
                self._refresh_token,
                session=async_get_clientsession(self.hass),
                cache_dir=_cache_dir(self.hass),
            )
        return self._client

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt for and validate the Mobility Database refresh token.

        The token is account-wide, so when another feed entry already holds a
        working one, reuse it and skip straight to the feed search.
        """
        errors: dict[str, str] = {}
        if user_input is None:
            known_tokens = {
                entry.data[CONF_REFRESH_TOKEN]
                for entry in self._async_current_entries(include_ignore=False)
            }
            for token in known_tokens:
                self._refresh_token = token
                client = self._get_client()
                try:
                    await client.catalog.get_metadata()
                except MobilityDatabaseError:
                    self._refresh_token = None
                    self._client = None
                    await client.close()
                else:
                    return await self.async_step_search()
        else:
            self._refresh_token = user_input[CONF_REFRESH_TOKEN]
            client = self._get_client()
            try:
                await client.catalog.get_metadata()
            except MobilityDatabaseAuthenticationError:
                errors["base"] = "invalid_auth"
            except MobilityDatabaseConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_search()
            self._client = None
            await client.close()
        return self.async_show_form(
            step_id="user",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
            description_placeholders={"account_url": ACCOUNT_URL},
        )

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search the catalog and pick a feed; re-submit a query to refine."""
        errors: dict[str, str] = {}
        client = self._get_client()
        if user_input is not None:
            if feed_id := user_input.get(CONF_FEED_ID):
                try:
                    return await self._async_resolve_feed_family(feed_id)
                except MobilityDatabaseConnectionError:
                    errors["base"] = "cannot_connect"
                except MobilityDatabaseError:
                    errors["base"] = "unknown"
            elif query := user_input.get(CONF_SEARCH_QUERY):
                # GTFS only: realtime siblings resolve automatically and would
                # otherwise clutter the results (often several unnamed entries
                # per provider). Active only: skip deprecated legacy feeds.
                try:
                    results = await client.catalog.search_feeds(
                        search_query=query,
                        data_types=[DataType.GTFS],
                        statuses=[FeedStatus.ACTIVE],
                        limit=25,
                    )
                except MobilityDatabaseConnectionError:
                    errors["base"] = "cannot_connect"
                else:
                    self._feed_options = [
                        SelectOptionDict(
                            value=result.id,
                            label=f"{result.provider or result.id}"
                            f"{f' — {result.feed_name}' if result.feed_name else ''}"
                            f" ({result.id})",
                        )
                        for result in results.results
                        if result.id
                    ]
                    if not self._feed_options:
                        errors["base"] = "no_results"
            else:
                errors["base"] = "search_or_select"

        schema: dict[probatio.Marker, Any] = {
            probatio.Optional(CONF_SEARCH_QUERY): TextSelector()
        }
        if self._feed_options:
            schema[probatio.Optional(CONF_FEED_ID)] = SelectSelector(
                SelectSelectorConfig(
                    options=self._feed_options, mode=SelectSelectorMode.DROPDOWN
                )
            )
        return self.async_show_form(
            step_id="search", data_schema=probatio.Schema(schema), errors=errors
        )

    async def _async_resolve_feed_family(self, feed_id: str) -> ConfigFlowResult:
        """Look up the picked GTFS feed and its realtime siblings."""
        catalog = self._get_client().catalog
        static_feed = await catalog.get_gtfs_feed(feed_id)
        rt_feeds = await catalog.get_gtfs_feed_gtfs_rt_feeds(feed_id)

        await self.async_set_unique_id(feed_id)
        self._abort_if_unique_id_configured()

        self._static_feed_id = feed_id
        # Providers often publish several feeds (for example Rail and Bus);
        # the feed name keeps their entry titles distinct.
        self._title = static_feed.provider or feed_id
        if static_feed.feed_name:
            self._title = f"{self._title} {static_feed.feed_name}"
        self._auth_url = _auth_info_url(rt_feeds, feed_id)
        if self._auth_url is not None:
            return await self.async_step_api_key()
        return await self.async_step_build()

    async def async_step_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt for the realtime producer's API key, or none at all."""
        errors: dict[str, str] = {}
        if self._api_key_error is not None:
            # The build just proved the last key wrong and routed back here.
            # Home Assistant re-enters this step with that SAME submitted
            # input, so it must not be taken as a new submission -- that
            # would rebuild, re-probe and route back here forever. Show the
            # error and wait for a real answer.
            errors["base"] = self._api_key_error
            self._api_key_error = None
        elif user_input is not None:
            # Blank means schedule-only, so it has nothing to prove.
            self._api_key = user_input.get(CONF_API_KEY) or None
            return await self.async_step_build()
        assert self._auth_url is not None
        return self.async_show_form(
            step_id="api_key",
            data_schema=API_KEY_SCHEMA,
            errors=errors,
            description_placeholders={"authentication_info_url": self._auth_url},
        )

    async def async_step_build(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Download and index the static dataset, reporting progress."""
        if self._build_task is None:
            self._build_task = self.hass.async_create_task(self._async_build())
        if not self._build_task.done():
            return self.async_show_progress(
                step_id="build",
                progress_action="build",
                progress_task=self._build_task,
            )
        try:
            await self._build_task
        except (MobilityDatabaseError, MobilityFeedsError) as err:
            self._build_error = str(err)
            self._build_task = None
            return self.async_show_progress_done(next_step_id="build_failed")
        self._build_task = None
        if self._api_key_error is not None:
            # The schedule is indexed and cached, so going back for another
            # key costs no second download.
            return self.async_show_progress_done(next_step_id="api_key")
        return self.async_show_progress_done(next_step_id="finish")

    async def _async_build(self) -> None:
        """Warm the static index cache; the runtime reopens it instantly."""
        assert self._static_feed_id is not None

        def on_progress(progress: StaticBuildProgress) -> None:
            if not progress.total_bytes:
                return
            fraction = progress.done_bytes / progress.total_bytes
            if progress.phase == "download":
                value = 0.5 * fraction
            else:
                value = 0.5 + 0.5 * fraction
            # The library reports indexing progress from a worker thread.
            self.hass.loop.call_soon_threadsafe(
                self.async_update_progress, min(value, 1.0)
            )

        handle = await self._get_client().get_transit_feed(
            self._static_feed_id, self._api_key, on_progress=on_progress
        )
        try:
            # Prove the key before saving it: a typo would otherwise only
            # surface after setup, as a realtime auth failure and a reauth.
            if self._api_key is not None:
                self._api_key_error = await _probe_realtime(handle)
        finally:
            handle.close()

    async def async_step_build_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort after a failed static build."""
        return self.async_abort(
            reason="build_failed",
            description_placeholders={"error": self._build_error or "unknown"},
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the config entry after a successful build."""
        assert self._refresh_token is not None
        assert self._static_feed_id is not None
        assert self._title is not None
        data: dict[str, Any] = {
            CONF_REFRESH_TOKEN: self._refresh_token,
            CONF_FEED_ID: self._static_feed_id,
        }
        if self._api_key is not None:
            data[CONF_API_KEY] = self._api_key
        return self.async_create_entry(title=self._title, data=data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Determine which credential failed and route to the right prompt."""
        entry = self._get_reauth_entry()
        client = MobilityFeedsClient(
            entry.data[CONF_REFRESH_TOKEN],
            session=async_get_clientsession(self.hass),
        )
        feed_id: str = entry.data[CONF_FEED_ID]
        try:
            await client.catalog.get_metadata()
            rt_feeds = await client.catalog.get_gtfs_feed_gtfs_rt_feeds(feed_id)
        except MobilityDatabaseAuthenticationError:
            return await self.async_step_reauth_token()
        except MobilityDatabaseConnectionError:
            return self.async_abort(reason="cannot_connect")
        finally:
            await client.close()
        self._auth_url = (
            _auth_info_url(rt_feeds, feed_id) or f"{ACCOUNT_URL}/feeds/{feed_id}"
        )
        return await self.async_step_reauth_api_key()

    async def async_step_reauth_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt for a new refresh token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = MobilityFeedsClient(
                user_input[CONF_REFRESH_TOKEN],
                session=async_get_clientsession(self.hass),
            )
            try:
                await client.catalog.get_metadata()
            except MobilityDatabaseAuthenticationError:
                errors["base"] = "invalid_auth"
            except MobilityDatabaseConnectionError:
                errors["base"] = "cannot_connect"
            finally:
                await client.close()
            if not errors:
                entry = self._get_reauth_entry()
                new_token: str = user_input[CONF_REFRESH_TOKEN]
                # The token is account-wide: fix every other feed entry that
                # held the same expired token instead of prompting per entry.
                # Reloading them retries setup with the new token and aborts
                # their pending reauth flows.
                old_token: str = entry.data[CONF_REFRESH_TOKEN]
                for other in self.hass.config_entries.async_entries(DOMAIN):
                    if (
                        other.entry_id != entry.entry_id
                        and other.data[CONF_REFRESH_TOKEN] == old_token
                    ):
                        self.hass.config_entries.async_update_entry(
                            other,
                            data={**other.data, CONF_REFRESH_TOKEN: new_token},
                        )
                        self.hass.config_entries.async_schedule_reload(other.entry_id)
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_REFRESH_TOKEN: new_token}
                )
        return self.async_show_form(
            step_id="reauth_token", data_schema=TOKEN_SCHEMA, errors=errors
        )

    async def async_step_reauth_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt for a new producer API key, and prove it works first."""
        errors: dict[str, str] = {}
        if user_input is not None:
            entry = self._get_reauth_entry()
            if not (api_key := user_input.get(CONF_API_KEY)):
                # Giving up the key is a valid answer: drop it and run on
                # the published schedule alone.
                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        key: value
                        for key, value in entry.data.items()
                        if key != CONF_API_KEY
                    },
                )
            if error := await self._async_probe_api_key(entry, api_key):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: api_key}
                )
        assert self._auth_url is not None
        return self.async_show_form(
            step_id="reauth_api_key",
            data_schema=API_KEY_SCHEMA,
            errors=errors,
            description_placeholders={"authentication_info_url": self._auth_url},
        )

    async def _async_probe_api_key(
        self, entry: MobilityDataConfigEntry, api_key: str
    ) -> str | None:
        """Return an error key if this key cannot open the feed's realtime.

        The static index is already cached, so this costs a catalog check
        and the one producer request ``_probe_realtime`` makes.
        """
        # Reauth for the producer key starts at this step, so the flow has no
        # token of its own yet; the entry's is the one that reaches the catalog.
        self._refresh_token = entry.data[CONF_REFRESH_TOKEN]
        try:
            handle = await self._get_client().get_transit_feed(
                entry.data[CONF_FEED_ID], api_key
            )
        except MobilityDatabaseAuthenticationError:
            return "invalid_auth"
        except MobilityDatabaseError, MobilityFeedsError:
            return "cannot_connect"
        try:
            return await _probe_realtime(handle)
        finally:
            handle.close()


type Pair = tuple[str, str | None]


def _board_unique_id(group_key: str, route_ids: list[str], pairs: list[Pair]) -> str:
    """Identify a board by its station AND what it shows.

    A station can carry several boards, so the station alone cannot be the
    identity -- only an identical selection is a duplicate. Picked pairs
    define the board on their own (the routes step only narrowed the list
    they came from), so the identity is the pairs when there are any and
    the routes otherwise. JSON-encoded rather than joined, because a
    headsign legitimately contains commas ("Downtown, via Main").
    """
    if pairs:
        shown: list[Any] = ["pairs", sorted(pairs, key=_pair_sort_key)]
    else:
        shown = ["routes", sorted(route_ids)]
    return f"{group_key}{_BOARD_ID_SEPARATOR}{json.dumps(shown, separators=(',', ':'))}"


def _pair_sort_key(pair: Pair) -> tuple[str, bool, str]:
    route_id, headsign = pair
    return (route_id, headsign is not None, headsign or "")


def _route_labels(routes: list[Route]) -> dict[str, str]:
    """Label routes as briefly as stays unambiguous.

    The short name is what riders call a route ("R", "Blue", "C1_RED"), but
    two routes can share one -- Paris runs both an RER B and a bus B -- so
    any short name used more than once falls back to the full name.
    """
    shorts = Counter(route.short_name for route in routes if route.short_name)
    return {
        route.id: route.short_name
        if route.short_name and shorts[route.short_name] == 1
        else route.display_name
        for route in routes
    }


def _encode_pair(pair: Pair) -> str:
    return json.dumps(list(pair), separators=(",", ":"))


def _decode_pair(value: str) -> Pair:
    route_id, headsign = json.loads(value)
    return route_id, headsign


class StopSubentryFlowHandler(ConfigSubentryFlow):
    """Handle adding and reconfiguring a transit stop."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        self._group_key: str | None = None
        self._stop_ids: list[str] = []
        self._stop_name: str | None = None
        self._route_ids: list[str] = []
        self._pairs: list[Pair] = []
        self._route_labels: dict[str, str] = {}
        self._groups: dict[str, StationGroup] = {}

    def _get_handle(self) -> TransitFeedHandle | None:
        """Return the entry's transit feed handle, or None if not ready."""
        entry: MobilityDataConfigEntry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return None
        return entry.runtime_data.static_coordinator.data

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Pick the search area: a zone entity or a manual circle."""
        if (handle := self._get_handle()) is None:
            return self.async_abort(reason="not_ready")
        errors: dict[str, str] = {}
        if user_input is not None:
            circle: Circle | None = None
            # The map area always carries a (suggested) value, so a picked
            # zone takes precedence over it.
            if zone_entity := user_input.get(CONF_ZONE):
                if (state := self.hass.states.get(zone_entity)) is None:
                    errors["base"] = "zone_not_found"
                else:
                    circle = Circle(
                        latitude=state.attributes["latitude"],
                        longitude=state.attributes["longitude"],
                        radius_m=state.attributes["radius"],
                    )
            elif location := user_input.get(CONF_LOCATION):
                circle = Circle(
                    latitude=location["latitude"],
                    longitude=location["longitude"],
                    radius_m=location.get("radius") or 1000,
                )
            else:
                errors["base"] = "choose_one"
            if circle is not None:
                if groups := handle.stations_in(circle):
                    self._groups = {group.id: group for group in groups}
                    return await self.async_step_stop()
                errors["base"] = "no_stops_in_zone"
        schema = probatio.Schema(
            {
                probatio.Optional(CONF_ZONE): EntitySelector(
                    EntitySelectorConfig(domain="zone")
                ),
                probatio.Optional(CONF_LOCATION): LocationSelector(
                    LocationSelectorConfig(radius=True)
                ),
            }
        )
        if (center := _coverage_center(handle)) is not None:
            schema = self.add_suggested_values_to_schema(
                schema, {CONF_LOCATION: center}
            )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def _station_labels(self, handle: TransitFeedHandle) -> dict[str, str]:
        """Label stations, telling apart the ones that share a name.

        Station names repeat within one network -- NYC has an "86 St" on
        several lines and two "DeKalb Av" -- and a picker of identical
        labels cannot be chosen from. Only the duplicated names gain the
        routes serving them ("86 St (1)" against "86 St (N W)").
        """
        names = Counter(group.name for group in self._groups.values())
        labels: dict[str, str] = {}
        for group_key, group in self._groups.items():
            labels[group_key] = group.name
            if names[group.name] == 1:
                continue
            serving = {
                route.short_name or route.long_name or route.id
                for stop_id in group.stop_ids
                for route in await handle.routes_serving(stop_id)
            }
            if serving:
                listed = sorted(serving)
                shown = " ".join(listed[:_MAX_DISAMBIGUATING_ROUTES])
                if len(listed) > _MAX_DISAMBIGUATING_ROUTES:
                    shown += " …"
                labels[group_key] = f"{group.name} ({shown})"
        # Same name AND same routes (two halves of one interchange, say):
        # only an id is left to tell them apart.
        repeats = Counter(labels.values())
        for group_key, label in labels.items():
            if repeats[label] > 1:
                labels[group_key] = f"{label} [{self._groups[group_key].stop_ids[0]}]"
        return labels

    async def async_step_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Pick a stop from those inside the search area."""
        if (handle := self._get_handle()) is None:
            return self.async_abort(reason="not_ready")
        if user_input is not None:
            group_key: str = user_input[CONF_STOP]
            # Several boards at one station is the useful case ("downtown bus"
            # and "airport train" are different sensors), so the duplicate
            # check belongs at the end, once the selection is known.
            group = self._groups[group_key]
            self._group_key = group_key
            self._stop_name = group.name
            self._stop_ids = list(group.stop_ids)
            return await self.async_step_routes()
        labels = await self._station_labels(handle)
        return self.async_show_form(
            step_id="stop",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_STOP): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=group_key, label=label)
                                for group_key, label in labels.items()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_routes(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Optionally narrow to specific routes serving the stop."""
        if (handle := self._get_handle()) is None:
            return self.async_abort(reason="not_ready")
        assert self._stop_ids
        if user_input is not None:
            self._route_ids = user_input.get(CONF_ROUTE_IDS, [])
            return await self.async_step_departures()
        routes_by_id = {
            route.id: route
            for stop_id in self._stop_ids
            for route in await handle.routes_serving(stop_id)
        }
        routes = sorted(routes_by_id.values(), key=lambda route: route.display_name)
        self._route_labels = _route_labels(routes)
        if not routes:
            return await self.async_step_departures()
        return self.async_show_form(
            step_id="routes",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(CONF_ROUTE_IDS, default=self._route_ids): (
                        SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    SelectOptionDict(
                                        value=route.id, label=route.display_name
                                    )
                                    for route in routes
                                ],
                                multiple=True,
                                mode=SelectSelectorMode.DROPDOWN,
                            )
                        )
                    )
                }
            ),
        )

    async def async_step_departures(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Optionally pick exact route -> destination pairs, then finish.

        Offered for the routes chosen in the previous step, or for every
        route when none were. A route whose trips here carry no destination
        at all is offered as itself, so it can still be combined with
        specific pairs from other routes.
        """
        if (handle := self._get_handle()) is None:
            return self.async_abort(reason="not_ready")
        assert self._stop_ids
        if user_input is not None:
            return self._async_finish(
                [
                    _decode_pair(value)
                    for value in user_input.get(CONF_ROUTE_DESTINATIONS, [])
                ]
            )
        route_ids = self._route_ids or list(self._route_labels)
        named: set[Pair] = set()
        undirected: set[str] = set()
        for route_id in route_ids:
            headsigns = {
                headsign
                for stop_id in self._stop_ids
                for headsign in await handle.headsigns_serving(stop_id, route_id)
            }
            named.update((route_id, headsign) for headsign in headsigns)
            if not headsigns:
                undirected.add(route_id)
        if not named:
            # Nothing to narrow by -- some feeds (TfL, Delhi DTC) publish no
            # destinations at all -- so the routes alone are the selection.
            return self._async_finish([])
        offered = sorted(
            [*named, *((route_id, None) for route_id in undirected)],
            key=lambda pair: (self._pair_label(pair), _pair_sort_key(pair)),
        )
        # Narrowing the routes can retire a previously chosen pair; keep the
        # ones still on offer rather than silently clearing the selection.
        current = [_encode_pair(pair) for pair in self._pairs if pair in offered]
        return self.async_show_form(
            step_id="departures",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        CONF_ROUTE_DESTINATIONS, default=current
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=_encode_pair(pair),
                                    label=self._pair_label(pair),
                                )
                                for pair in offered
                            ],
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    def _pair_label(self, pair: Pair) -> str:
        route_id, headsign = pair
        route = self._route_labels.get(route_id, route_id)
        return route if headsign is None else f"{route} → {headsign}"

    def _board_title(self, pairs: list[Pair]) -> str:
        """Name the board by what it shows, so several at one station differ."""
        assert self._stop_name is not None
        if pairs:
            shown = [self._pair_label(pair) for pair in pairs]
        else:
            shown = [
                self._route_labels.get(route_id, route_id)
                for route_id in self._route_ids
            ]
        if not shown:
            return self._stop_name
        return f"{self._stop_name} ({', '.join(shown)})"

    @callback
    def _async_finish(self, pairs: list[Pair]) -> SubentryFlowResult:
        assert self._stop_name is not None
        assert self._group_key is not None
        unique_id = _board_unique_id(self._group_key, self._route_ids, pairs)
        reconfigure = self.source == SOURCE_RECONFIGURE
        current = self._get_reconfigure_subentry() if reconfigure else None
        # Home Assistant raises on a duplicate subentry unique_id, so catch
        # the collision here and report it as the flow error it is.
        for subentry in self._get_entry().subentries.values():
            if subentry.unique_id == unique_id and subentry is not current:
                return self.async_abort(reason="already_configured")
        stored_pairs = [list(pair) for pair in pairs]
        if current is not None:
            # The entry's update listener reloads; must not reload here too.
            return self.async_update_and_abort(
                self._get_entry(),
                current,
                title=self._board_title(pairs),
                unique_id=unique_id,
                data_updates={
                    CONF_ROUTE_IDS: self._route_ids,
                    CONF_ROUTE_DESTINATIONS: stored_pairs,
                },
            )
        return self.async_create_entry(
            title=self._board_title(pairs),
            data={
                CONF_STATION_ID: self._group_key,
                CONF_STOP_IDS: self._stop_ids,
                CONF_STOP_NAME: self._stop_name,
                CONF_ROUTE_IDS: self._route_ids,
                CONF_ROUTE_DESTINATIONS: stored_pairs,
            },
            unique_id=unique_id,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure the routes and departures for an existing board."""
        subentry: ConfigSubentry = self._get_reconfigure_subentry()
        self._stop_ids = list(subentry.data[CONF_STOP_IDS])
        self._stop_name = subentry.data[CONF_STOP_NAME]
        self._route_ids = list(subentry.data[CONF_ROUTE_IDS])
        self._pairs = [
            (route_id, headsign)
            for route_id, headsign in subentry.data[CONF_ROUTE_DESTINATIONS]
        ]
        self._group_key = subentry.data[CONF_STATION_ID]
        return await self.async_step_routes()
