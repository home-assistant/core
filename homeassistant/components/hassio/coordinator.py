"""Data for Hass.io."""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, cast

from aiohasupervisor import SupervisorError, SupervisorNotFoundError
from aiohasupervisor.models import (
    AddonsStats,
    AddonState,
    CIFSMountResponse,
    HomeAssistantInfo,
    HomeAssistantStats,
    HostInfo,
    InstalledAddon,
    InstalledAddonComplete,
    NetworkInfo,
    NFSMountResponse,
    OSInfo,
    ResponseData,
    RootInfo,
    StoreInfo,
    SupervisorInfo,
    SupervisorStats,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MANUFACTURER
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_ADDONS,
    ATTR_DATA,
    ATTR_REPOSITORIES,
    ATTR_STARTUP,
    ATTR_UPDATE_KEY,
    ATTR_WS_EVENT,
    CONTAINER_STATS,
    CORE_CONTAINER,
    DATA_ADDONS_INFO,
    DATA_ADDONS_LIST,
    DATA_ADDONS_STATS,
    DATA_CORE_INFO,
    DATA_CORE_STATS,
    DATA_HOST_INFO,
    DATA_INFO,
    DATA_KEY_SUPERVISOR_ISSUES,
    DATA_NETWORK_INFO,
    DATA_OS_INFO,
    DATA_STORE,
    DATA_SUPERVISOR_INFO,
    DATA_SUPERVISOR_STATS,
    DOMAIN,
    EVENT_SUPERVISOR_EVENT,
    EVENT_SUPERVISOR_UPDATE,
    HASSIO_ADDON_UPDATE_INTERVAL,
    HASSIO_MAIN_UPDATE_INTERVAL,
    HASSIO_STATS_UPDATE_INTERVAL,
    REQUEST_REFRESH_DELAY,
    STARTUP_COMPLETE,
    SUPERVISOR_CONTAINER,
    UPDATE_KEY_SUPERVISOR,
    SupervisorEntityModel,
)
from .exceptions import HassioNotReadyError
from .handler import get_supervisor_client
from .jobs import SupervisorJobs

if TYPE_CHECKING:
    from .issues import SupervisorIssues

_LOGGER = logging.getLogger(__name__)


@dataclass
class HassioMainData:
    """Data class for HassioMainDataUpdateCoordinator."""

    core: HomeAssistantInfo
    supervisor: SupervisorInfo
    host: HostInfo
    mounts: dict[str, CIFSMountResponse | NFSMountResponse]
    os: OSInfo | None

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the data."""
        return {
            "core": self.core.to_dict(),
            "supervisor": self.supervisor.to_dict(),
            "host": self.host.to_dict(),
            "mounts": {name: mount.to_dict() for name, mount in self.mounts.items()},
            "os": self.os.to_dict() if self.os is not None else None,
        }


@dataclass
class AddonData:
    """Data for a single installed addon."""

    addon: InstalledAddon
    auto_update: bool
    repository: str


@dataclass
class HassioAddonData:
    """Data class for HassioAddOnDataUpdateCoordinator."""

    addons: dict[str, AddonData]

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the data."""
        return {
            "addons": {
                slug: {
                    "addon": addon_data.addon.to_dict(),
                    "auto_update": addon_data.auto_update,
                    "repository": addon_data.repository,
                }
                for slug, addon_data in self.addons.items()
            },
        }


@dataclass
class HassioStatsData:
    """Data class for HassioStatsDataUpdateCoordinator."""

    core: HomeAssistantStats | None
    supervisor: SupervisorStats | None
    addons: dict[str, AddonsStats | None]

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the data."""
        return {
            "core": self.core.to_dict() if self.core is not None else None,
            "supervisor": (
                self.supervisor.to_dict() if self.supervisor is not None else None
            ),
            "addons": {
                slug: stats.to_dict() if stats is not None else None
                for slug, stats in self.addons.items()
            },
        }


def _installed_addon_from_complete(info: InstalledAddonComplete) -> InstalledAddon:
    """Build an InstalledAddon from an InstalledAddonComplete object.

    InstalledAddonComplete contains a superset of InstalledAddon fields.
    This helper extracts only the fields needed for InstalledAddon so fresh
    data from an addon_info call can be stored in AddonData.addon.
    """
    return InstalledAddon(
        advanced=info.advanced,
        available=info.available,
        build=info.build,
        description=info.description,
        homeassistant=info.homeassistant,
        icon=info.icon,
        logo=info.logo,
        name=info.name,
        repository=info.repository,
        slug=info.slug,
        stage=info.stage,
        update_available=info.update_available,
        url=info.url,
        version_latest=info.version_latest,
        version=info.version,
        detached=info.detached,
        state=info.state,
    )


@callback
def get_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return generic information from Supervisor.

    Async friendly.
    """
    info = hass.data.get(DATA_INFO)
    if info is None:
        raise HassioNotReadyError
    return info.to_dict()


@callback
def get_host_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return generic host information.

    Async friendly.
    """
    info = hass.data.get(DATA_HOST_INFO)
    if info is None:
        raise HassioNotReadyError
    return info.to_dict()


@callback
def get_store(hass: HomeAssistant) -> dict[str, Any]:
    """Return store information.

    Async friendly.
    """
    info = hass.data.get(DATA_STORE)
    if info is None:
        raise HassioNotReadyError
    return info.to_dict()


@callback
def get_supervisor_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return Supervisor information.

    Async friendly.
    """
    info = hass.data.get(DATA_SUPERVISOR_INFO)
    if info is None:
        raise HassioNotReadyError
    result = info.to_dict()
    # Deprecated 2026.4.0: Folding repositories and addons into supervisor_info
    # for backwards compatibility. Can be removed after deprecation period.
    if (store := hass.data.get(DATA_STORE)) is not None:
        result[ATTR_REPOSITORIES] = [repo.to_dict() for repo in store.repositories]
    if (addons_list := hass.data.get(DATA_ADDONS_LIST)) is not None:
        result[ATTR_ADDONS] = [addon.to_dict() for addon in addons_list]
    return result


@callback
def get_network_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return Host Network information.

    Async friendly.
    """
    info = hass.data.get(DATA_NETWORK_INFO)
    if info is None:
        raise HassioNotReadyError
    return info.to_dict()


@callback
def get_addons_info(hass: HomeAssistant) -> dict[str, dict[str, Any] | None]:
    """Return Addons info.

    Async friendly.
    """
    addons_info: dict[str, InstalledAddonComplete | None] | None = hass.data.get(
        DATA_ADDONS_INFO
    )
    if addons_info is None:
        raise HassioNotReadyError
    # Converting these fields for compatibility as that is what was returned here.
    # We'll leave it this way as long as these component APIs continue to return
    # dictionaries. If/when we switch to using the aiohasupervisor models for everything
    # internally and externally that will be dropped.
    return {
        slug: dict(
            hassio_api=info.supervisor_api,
            hassio_role=info.supervisor_role,
            **info.to_dict(),
        )
        if info is not None
        else None
        for slug, info in addons_info.items()
    }


@callback
def get_addons_list(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return list of installed addons and subset of details for each.

    Async friendly.
    """
    addons = hass.data.get(DATA_ADDONS_LIST)
    if addons is None:
        raise HassioNotReadyError
    return [addon.to_dict() for addon in addons]


@callback
def get_addons_stats(hass: HomeAssistant) -> dict[str, dict[str, Any] | None]:
    """Return Addons stats.

    Async friendly.
    """
    addons_stats: dict[str, AddonsStats | None] = hass.data.get(DATA_ADDONS_STATS) or {}
    return {
        slug: stats.to_dict() if stats is not None else None
        for slug, stats in addons_stats.items()
    }


@callback
def get_core_stats(hass: HomeAssistant) -> dict[str, Any]:
    """Return core stats.

    Async friendly.
    """
    stats = hass.data.get(DATA_CORE_STATS)
    return stats.to_dict() if stats is not None else {}


@callback
def get_supervisor_stats(hass: HomeAssistant) -> dict[str, Any]:
    """Return supervisor stats.

    Async friendly.
    """
    stats = hass.data.get(DATA_SUPERVISOR_STATS)
    return stats.to_dict() if stats is not None else {}


@callback
def get_os_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return OS information.

    Async friendly.
    """
    info = hass.data.get(DATA_OS_INFO)
    if info is None:
        raise HassioNotReadyError
    return info.to_dict()


@callback
def get_core_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return Home Assistant Core information from Supervisor.

    Async friendly.
    """
    info = hass.data.get(DATA_CORE_INFO)
    if info is None:
        raise HassioNotReadyError
    return info.to_dict()


@callback
def get_issues_info(hass: HomeAssistant) -> SupervisorIssues | None:
    """Return Supervisor issues info.

    Async friendly.
    """
    return hass.data.get(DATA_KEY_SUPERVISOR_ISSUES)


@callback
def async_register_addons_in_dev_reg(
    entry_id: str, dev_reg: dr.DeviceRegistry, addons: list[AddonData]
) -> None:
    """Register addons in the device registry."""
    for addon_data in addons:
        addon = addon_data.addon
        params = DeviceInfo(
            identifiers={(DOMAIN, addon.slug)},
            model=SupervisorEntityModel.ADDON,
            sw_version=addon.version,
            name=addon.name,
            entry_type=dr.DeviceEntryType.SERVICE,
            configuration_url=f"homeassistant://hassio/addon/{addon.slug}",
        )
        if manufacturer := addon_data.repository or addon.url:
            params[ATTR_MANUFACTURER] = manufacturer
        dev_reg.async_get_or_create(config_entry_id=entry_id, **params)


@callback
def async_register_mounts_in_dev_reg(
    entry_id: str,
    dev_reg: dr.DeviceRegistry,
    mounts: list[CIFSMountResponse | NFSMountResponse],
) -> None:
    """Register mounts in the device registry."""
    for mount in mounts:
        params = DeviceInfo(
            identifiers={(DOMAIN, f"mount_{mount.name}")},
            manufacturer="Home Assistant",
            model=SupervisorEntityModel.MOUNT,
            model_id=f"{mount.usage}/{mount.type}",
            name=mount.name,
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        dev_reg.async_get_or_create(config_entry_id=entry_id, **params)


@callback
def async_register_os_in_dev_reg(
    entry_id: str, dev_reg: dr.DeviceRegistry, os_info: OSInfo
) -> None:
    """Register OS in the device registry."""
    params = DeviceInfo(
        identifiers={(DOMAIN, "OS")},
        manufacturer="Home Assistant",
        model=SupervisorEntityModel.OS,
        sw_version=os_info.version,
        name="Home Assistant Operating System",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    dev_reg.async_get_or_create(config_entry_id=entry_id, **params)


@callback
def async_register_host_in_dev_reg(
    entry_id: str,
    dev_reg: dr.DeviceRegistry,
) -> None:
    """Register host in the device registry."""
    params = DeviceInfo(
        identifiers={(DOMAIN, "host")},
        manufacturer="Home Assistant",
        model=SupervisorEntityModel.HOST,
        name="Home Assistant Host",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    dev_reg.async_get_or_create(config_entry_id=entry_id, **params)


@callback
def async_register_core_in_dev_reg(
    entry_id: str,
    dev_reg: dr.DeviceRegistry,
    core_info: HomeAssistantInfo,
) -> None:
    """Register core in the device registry."""
    params = DeviceInfo(
        identifiers={(DOMAIN, "core")},
        manufacturer="Home Assistant",
        model=SupervisorEntityModel.CORE,
        sw_version=core_info.version,
        name="Home Assistant Core",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    dev_reg.async_get_or_create(config_entry_id=entry_id, **params)


@callback
def async_register_supervisor_in_dev_reg(
    entry_id: str,
    dev_reg: dr.DeviceRegistry,
    supervisor_info: SupervisorInfo,
) -> None:
    """Register supervisor in the device registry."""
    params = DeviceInfo(
        identifiers={(DOMAIN, "supervisor")},
        manufacturer="Home Assistant",
        model=SupervisorEntityModel.SUPERVISOR,
        sw_version=supervisor_info.version,
        name="Home Assistant Supervisor",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    dev_reg.async_get_or_create(config_entry_id=entry_id, **params)


@callback
def async_remove_devices_from_dev_reg(
    dev_reg: dr.DeviceRegistry, devices: set[str]
) -> None:
    """Remove devices from the device registry."""
    for device in devices:
        if dev := dev_reg.async_get_device(identifiers={(DOMAIN, device)}):
            dev_reg.async_remove_device(dev.id)


class HassioStatsDataUpdateCoordinator(DataUpdateCoordinator[HassioStatsData]):
    """Class to retrieve Hass.io container stats."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=HASSIO_STATS_UPDATE_INTERVAL,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )
        self.supervisor_client = get_supervisor_client(hass)
        self._container_updates: defaultdict[str, dict[str, set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )

    async def _async_update_data(self) -> HassioStatsData:
        """Update stats data via library."""
        try:
            await self._fetch_stats()
        except SupervisorError as err:
            raise UpdateFailed(f"Error on Supervisor API: {err}") from err

        return HassioStatsData(
            core=self.hass.data.get(DATA_CORE_STATS),
            supervisor=self.hass.data.get(DATA_SUPERVISOR_STATS),
            addons=self.hass.data.get(DATA_ADDONS_STATS) or {},
        )

    async def _fetch_stats(self) -> None:
        """Fetch container stats for subscribed entities."""
        container_updates = self._container_updates
        data = self.hass.data
        client = self.supervisor_client

        # Fetch core and supervisor stats
        updates: dict[str, Awaitable] = {}
        if container_updates.get(CORE_CONTAINER, {}).get(CONTAINER_STATS):
            updates[DATA_CORE_STATS] = client.homeassistant.stats()
        if container_updates.get(SUPERVISOR_CONTAINER, {}).get(CONTAINER_STATS):
            updates[DATA_SUPERVISOR_STATS] = client.supervisor.stats()

        if updates:
            api_results: list[ResponseData] = await asyncio.gather(*updates.values())
            for key, result in zip(updates, api_results, strict=True):
                data[key] = result

        # Fetch addon stats
        addons_list: list[InstalledAddon] = self.hass.data.get(DATA_ADDONS_LIST) or []
        started_addons = {
            addon.slug
            for addon in addons_list
            if addon.state in {AddonState.STARTED, AddonState.STARTUP}
        }

        addons_stats: dict[str, AddonsStats | None] = data.setdefault(
            DATA_ADDONS_STATS, {}
        )

        # Clean up cache for stopped/removed addons
        for slug in addons_stats.keys() - started_addons:
            del addons_stats[slug]

        # Fetch stats for addons with subscribed entities
        addon_stats_results = dict(
            await asyncio.gather(
                *[
                    self._update_addon_stats(slug)
                    for slug in started_addons
                    if container_updates.get(slug, {}).get(CONTAINER_STATS)
                ]
            )
        )
        addons_stats.update(addon_stats_results)

    async def _update_addon_stats(self, slug: str) -> tuple[str, AddonsStats | None]:
        """Update single addon stats."""
        try:
            stats = await self.supervisor_client.addons.addon_stats(slug)
        except SupervisorError as err:
            _LOGGER.warning("Could not fetch stats for %s: %s", slug, err)
            return (slug, None)
        return (slug, stats)

    @callback
    def async_enable_container_updates(
        self, slug: str, entity_id: str, types: set[str]
    ) -> CALLBACK_TYPE:
        """Enable stats updates for a container."""
        enabled_updates = self._container_updates[slug]
        for key in types:
            enabled_updates[key].add(entity_id)

        @callback
        def _remove() -> None:
            for key in types:
                enabled_updates[key].discard(entity_id)
                if not enabled_updates[key]:
                    del enabled_updates[key]
            if not enabled_updates:
                self._container_updates.pop(slug, None)

        return _remove


class HassioAddOnDataUpdateCoordinator(DataUpdateCoordinator[HassioAddonData]):
    """Class to retrieve Hass.io Add-on status."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        dev_reg: dr.DeviceRegistry,
        jobs: SupervisorJobs,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=HASSIO_ADDON_UPDATE_INTERVAL,
            # We don't want an immediate refresh since we want to avoid
            # hammering the Supervisor API on startup
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )
        self.entry_id = config_entry.entry_id
        self.dev_reg = dev_reg
        self._addon_info_subscriptions: defaultdict[str, set[str]] = defaultdict(set)
        self.supervisor_client = get_supervisor_client(hass)
        self.jobs = jobs

    async def _async_update_data(self) -> HassioAddonData:
        """Update data via library."""
        is_first_update = not self.data
        client = self.supervisor_client

        try:
            installed_addons: list[InstalledAddon] = await client.addons.list()
            all_addons = {addon.slug for addon in installed_addons}

            # Fetch addon info for all addons on first update, or only
            # for addons with subscribed entities on subsequent updates.
            addon_info_results: dict[str, InstalledAddonComplete | None] = dict(
                await asyncio.gather(
                    *[
                        self._update_addon_info(slug)
                        for slug in all_addons
                        if is_first_update or self._addon_info_subscriptions.get(slug)
                    ]
                )
            )
        except SupervisorError as err:
            raise UpdateFailed(f"Error on Supervisor API: {err}") from err

        # Update hass.data for legacy accessor functions
        self.hass.data[DATA_ADDONS_LIST] = installed_addons

        # Update addon info cache in hass.data
        addon_info_cache = self.hass.data.setdefault(DATA_ADDONS_INFO, {})
        for slug in addon_info_cache.keys() - all_addons:
            del addon_info_cache[slug]
        addon_info_cache.update(addon_info_results)

        # Build repository name lookup from store data
        store = self.hass.data.get(DATA_STORE)
        repositories: dict[str, str] = (
            {repo.slug: repo.name for repo in store.repositories} if store else {}
        )

        # Build clean coordinator data
        new_addons: dict[str, AddonData] = {}
        for addon in installed_addons:
            addon_info = addon_info_cache.get(addon.slug)
            auto_update = addon_info.auto_update if addon_info is not None else False
            repo_slug = addon.repository
            repository = repositories.get(repo_slug, repo_slug)
            new_addons[addon.slug] = AddonData(
                addon=addon,
                auto_update=auto_update,
                repository=repository,
            )
        new_data = HassioAddonData(addons=new_addons)

        # If this is the initial refresh, register all addons
        if is_first_update:
            async_register_addons_in_dev_reg(
                self.entry_id, self.dev_reg, list(new_data.addons.values())
            )

        # Remove add-ons that are no longer installed from device registry
        supervisor_addon_devices = {
            list(device.identifiers)[0][1]
            for device in self.dev_reg.devices.get_devices_for_config_entry_id(
                self.entry_id
            )
            if device.model == SupervisorEntityModel.ADDON
        }
        if stale_addons := supervisor_addon_devices - set(new_data.addons):
            async_remove_devices_from_dev_reg(self.dev_reg, stale_addons)

        # If there are new add-ons, we should reload the config entry so we can
        # create new devices and entities. We can return the new data because
        # coordinator will be recreated.
        if self.data and (set(new_data.addons) - set(self.data.addons)):
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.entry_id)
            )

        return new_data

    async def get_changelog(self, addon_slug: str) -> str | None:
        """Get the changelog for an add-on."""
        try:
            return await self.supervisor_client.store.addon_changelog(addon_slug)
        except SupervisorNotFoundError:
            return None

    async def _update_addon_info(
        self, slug: str
    ) -> tuple[str, InstalledAddonComplete | None]:
        """Return the info for an addon."""
        try:
            info = await self.supervisor_client.addons.addon_info(slug)
        except SupervisorError as err:
            _LOGGER.warning("Could not fetch info for %s: %s", slug, err)
            return (slug, None)
        return (slug, info)

    @callback
    def async_enable_addon_info_updates(
        self, slug: str, entity_id: str
    ) -> CALLBACK_TYPE:
        """Enable info updates for an add-on."""
        self._addon_info_subscriptions[slug].add(entity_id)

        @callback
        def _remove() -> None:
            self._addon_info_subscriptions[slug].discard(entity_id)
            if not self._addon_info_subscriptions[slug]:
                del self._addon_info_subscriptions[slug]

        return _remove

    async def _async_refresh(
        self,
        log_failures: bool = True,
        raise_on_auth_failed: bool = False,
        scheduled: bool = False,
        raise_on_entry_error: bool = False,
    ) -> None:
        """Refresh data."""
        if not scheduled and not raise_on_auth_failed:
            # Force reloading add-on updates for non-scheduled
            # updates.
            #
            # If `raise_on_auth_failed` is set, it means this is
            # the first refresh and we do not want to delay
            # startup or cause a timeout so we only refresh the
            # updates if this is not a scheduled refresh and
            # we are not doing the first refresh.
            try:
                await self.supervisor_client.store.reload()
            except SupervisorError as err:
                _LOGGER.warning("Error on Supervisor API: %s", err)

        await super()._async_refresh(
            log_failures, raise_on_auth_failed, scheduled, raise_on_entry_error
        )

    async def force_addon_info_data_refresh(self, addon_slug: str) -> None:
        """Force refresh of addon info data for a specific addon."""
        try:
            slug, info = await self._update_addon_info(addon_slug)
        except SupervisorError as err:
            _LOGGER.warning("Could not refresh info for %s: %s", addon_slug, err)
            return

        if info is not None and self.data and slug in self.data.addons:
            updated = AddonData(
                addon=_installed_addon_from_complete(info),
                auto_update=info.auto_update,
                repository=self.data.addons[slug].repository,
            )
            self.async_set_updated_data(
                HassioAddonData(addons={**self.data.addons, slug: updated})
            )

            # Update addon info cache in hass.data
            addon_info_cache = self.hass.data.setdefault(DATA_ADDONS_INFO, {})
            addon_info_cache[slug] = info


class HassioMainDataUpdateCoordinator(DataUpdateCoordinator[HassioMainData]):
    """Class to retrieve Hass.io status."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, dev_reg: dr.DeviceRegistry
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=HASSIO_MAIN_UPDATE_INTERVAL,
            # We don't want an immediate refresh since we want to avoid
            # hammering the Supervisor API on startup
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )
        self.entry_id = config_entry.entry_id
        self.dev_reg = dev_reg
        self.is_hass_os = False
        self.supervisor_client = get_supervisor_client(hass)
        self.jobs = SupervisorJobs(hass)
        self._dispatcher_disconnect = async_dispatcher_connect(
            hass, EVENT_SUPERVISOR_EVENT, self._supervisor_event
        )

    @callback
    def _supervisor_event(self, event: dict[str, Any]) -> None:
        """Refresh coordinator data when Supervisor restarts after an update."""
        if (
            event.get(ATTR_WS_EVENT) == EVENT_SUPERVISOR_UPDATE
            and event.get(ATTR_UPDATE_KEY) == UPDATE_KEY_SUPERVISOR
            and event.get(ATTR_DATA, {}).get(ATTR_STARTUP) == STARTUP_COMPLETE
        ):
            self.config_entry.async_create_task(self.hass, self.async_request_refresh())

    async def _async_update_data(self) -> HassioMainData:
        """Update data via library."""
        is_first_update = not self.data
        client = self.supervisor_client

        try:
            # Cast is required here because asyncio.gather only has overloads to
            # maintain typing for 6 arguments. It falls back to list[<common parent>]
            # after that which is what mypy sees here since we have 7 API calls.
            (
                info,
                core_info,
                supervisor_info,
                os_info,
                host_info,
                store_info,
                network_info,
            ) = cast(
                tuple[
                    RootInfo,
                    HomeAssistantInfo,
                    SupervisorInfo,
                    OSInfo,
                    HostInfo,
                    StoreInfo,
                    NetworkInfo,
                ],
                await asyncio.gather(
                    client.info(),
                    client.homeassistant.info(),
                    client.supervisor.info(),
                    client.os.info(),
                    client.host.info(),
                    client.store.info(),
                    client.network.info(),
                ),
            )
            mounts_info = await client.mounts.info()
            await self.jobs.refresh_data(is_first_update)
        except SupervisorError as err:
            raise UpdateFailed(f"Error on Supervisor API: {err}") from err

        # Build clean coordinator data
        self.is_hass_os = info.hassos is not None
        new_data = HassioMainData(
            core=core_info,
            supervisor=supervisor_info,
            host=host_info,
            mounts={mount.name: mount for mount in mounts_info.mounts},
            os=os_info if self.is_hass_os else None,
        )

        # Update hass.data for legacy accessor functions
        self.hass.data[DATA_INFO] = info
        self.hass.data[DATA_CORE_INFO] = core_info
        self.hass.data[DATA_OS_INFO] = os_info
        self.hass.data[DATA_HOST_INFO] = host_info
        self.hass.data[DATA_STORE] = store_info
        self.hass.data[DATA_NETWORK_INFO] = network_info
        self.hass.data[DATA_SUPERVISOR_INFO] = supervisor_info

        # If this is the initial refresh, register all main components
        if is_first_update:
            async_register_mounts_in_dev_reg(
                self.entry_id, self.dev_reg, list(new_data.mounts.values())
            )
            async_register_core_in_dev_reg(self.entry_id, self.dev_reg, new_data.core)
            async_register_supervisor_in_dev_reg(
                self.entry_id, self.dev_reg, new_data.supervisor
            )
            async_register_host_in_dev_reg(self.entry_id, self.dev_reg)
            if self.is_hass_os:
                async_register_os_in_dev_reg(self.entry_id, self.dev_reg, os_info)

        # Remove mounts that no longer exists from device registry
        supervisor_mount_devices = {
            device.name
            for device in self.dev_reg.devices.get_devices_for_config_entry_id(
                self.entry_id
            )
            if device.model == SupervisorEntityModel.MOUNT
        }
        if stale_mounts := supervisor_mount_devices - set(new_data.mounts):
            async_remove_devices_from_dev_reg(
                self.dev_reg, {f"mount_{stale_mount}" for stale_mount in stale_mounts}
            )

        if not self.is_hass_os and (
            dev := self.dev_reg.async_get_device(identifiers={(DOMAIN, "OS")})
        ):
            # Remove the OS device if it exists and the installation is not hassos
            self.dev_reg.async_remove_device(dev.id)

        # If there are new mounts, we should reload the config entry so we can
        # create new devices and entities. We can return the new data because
        # coordinator will be recreated.
        if self.data and (set(new_data.mounts) - set(self.data.mounts)):
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.entry_id)
            )

        return new_data

    async def _async_refresh(
        self,
        log_failures: bool = True,
        raise_on_auth_failed: bool = False,
        scheduled: bool = False,
        raise_on_entry_error: bool = False,
    ) -> None:
        """Refresh data."""
        if not scheduled and not raise_on_auth_failed:
            # Force reloading updates of main components for
            # non-scheduled updates.
            #
            # If `raise_on_auth_failed` is set, it means this is
            # the first refresh and we do not want to delay
            # startup or cause a timeout so we only refresh the
            # updates if this is not a scheduled refresh and
            # we are not doing the first refresh.
            try:
                await self.supervisor_client.reload_updates()
            except SupervisorError as err:
                _LOGGER.warning("Error on Supervisor API: %s", err)

        await super()._async_refresh(
            log_failures, raise_on_auth_failed, scheduled, raise_on_entry_error
        )

    async def async_shutdown(self) -> None:
        """Shut down and clean up when config entry unloaded."""
        await super().async_shutdown()
        self._dispatcher_disconnect()
        self.jobs.unload()
