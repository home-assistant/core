"""Data for Hass.io."""

from __future__ import annotations

import asyncio
from collections import defaultdict
import logging
from typing import TYPE_CHECKING, Any

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import StoreInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MANUFACTURER, ATTR_NAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.loader import bind_hass

from .const import (
    ATTR_AUTO_UPDATE,
    ATTR_CHANGELOG,
    ATTR_REPOSITORY,
    ATTR_SLUG,
    ATTR_STARTED,
    ATTR_STATE,
    ATTR_URL,
    ATTR_VERSION,
    CONTAINER_CHANGELOG,
    CONTAINER_INFO,
    CONTAINER_STATS,
    CORE_CONTAINER,
    DATA_ADDONS_CHANGELOGS,
    DATA_ADDONS_INFO,
    DATA_ADDONS_STATS,
    DATA_CORE_INFO,
    DATA_CORE_STATS,
    DATA_HOST_INFO,
    DATA_INFO,
    DATA_KEY_ADDONS,
    DATA_KEY_CORE,
    DATA_KEY_HOST,
    DATA_KEY_OS,
    DATA_KEY_SUPERVISOR,
    DATA_KEY_SUPERVISOR_ISSUES,
    DATA_NETWORK_INFO,
    DATA_OS_INFO,
    DATA_STORE,
    DATA_SUPERVISOR_INFO,
    DATA_SUPERVISOR_STATS,
    DOMAIN,
    HASSIO_UPDATE_INTERVAL,
    REQUEST_REFRESH_DELAY,
    SUPERVISOR_CONTAINER,
    SupervisorEntityModel,
)
from .handler import HassIO, HassioAPIError, get_supervisor_client

if TYPE_CHECKING:
    from .issues import SupervisorIssues

_LOGGER = logging.getLogger(__name__)


@callback
@bind_hass
def get_info(hass: HomeAssistant) -> dict[str, Any] | None:
    """Return generic information from Supervisor.

    Async friendly.
    """
    return hass.data.get(DATA_INFO)


@callback
@bind_hass
def get_host_info(hass: HomeAssistant) -> dict[str, Any] | None:
    """Return generic host information.

    Async friendly.
    """
    return hass.data.get(DATA_HOST_INFO)


@callback
@bind_hass
def get_store(hass: HomeAssistant) -> dict[str, Any] | None:
    """Return store information.

    Async friendly.
    """
    return hass.data.get(DATA_STORE)


@callback
@bind_hass
def get_supervisor_info(hass: HomeAssistant) -> dict[str, Any] | None:
    """Return Supervisor information.

    Async friendly.
    """
    return hass.data.get(DATA_SUPERVISOR_INFO)


@callback
@bind_hass
def get_network_info(hass: HomeAssistant) -> dict[str, Any] | None:
    """Return Host Network information.

    Async friendly.
    """
    return hass.data.get(DATA_NETWORK_INFO)


@callback
@bind_hass
def get_addons_info(hass: HomeAssistant) -> dict[str, dict[str, Any]] | None:
    """Return Addons info.

    Async friendly.
    """
    return hass.data.get(DATA_ADDONS_INFO)


@callback
@bind_hass
def get_addons_stats(hass: HomeAssistant) -> dict[str, Any]:
    """Return Addons stats.

    Async friendly.
    """
    return hass.data.get(DATA_ADDONS_STATS) or {}


@callback
@bind_hass
def get_core_stats(hass: HomeAssistant) -> dict[str, Any]:
    """Return core stats.

    Async friendly.
    """
    return hass.data.get(DATA_CORE_STATS) or {}


@callback
@bind_hass
def get_supervisor_stats(hass: HomeAssistant) -> dict[str, Any]:
    """Return supervisor stats.

    Async friendly.
    """
    return hass.data.get(DATA_SUPERVISOR_STATS) or {}


@callback
@bind_hass
def get_addons_changelogs(hass: HomeAssistant):
    """Return Addons changelogs.

    Async friendly.
    """
    return hass.data.get(DATA_ADDONS_CHANGELOGS)


@callback
@bind_hass
def get_os_info(hass: HomeAssistant) -> dict[str, Any] | None:
    """Return OS information.

    Async friendly.
    """
    return hass.data.get(DATA_OS_INFO)


@callback
@bind_hass
def get_core_info(hass: HomeAssistant) -> dict[str, Any] | None:
    """Return Home Assistant Core information from Supervisor.

    Async friendly.
    """
    return hass.data.get(DATA_CORE_INFO)


@callback
@bind_hass
def get_issues_info(hass: HomeAssistant) -> SupervisorIssues | None:
    """Return Supervisor issues info.

    Async friendly.
    """
    return hass.data.get(DATA_KEY_SUPERVISOR_ISSUES)


@callback
def async_register_addons_in_dev_reg(
    entry_id: str, dev_reg: dr.DeviceRegistry, addons: list[dict[str, Any]]
) -> None:
    """Register addons in the device registry."""
    for addon in addons:
        params = DeviceInfo(
            identifiers={(DOMAIN, addon[ATTR_SLUG])},
            model=SupervisorEntityModel.ADDON,
            sw_version=addon[ATTR_VERSION],
            name=addon[ATTR_NAME],
            entry_type=dr.DeviceEntryType.SERVICE,
            configuration_url=f"homeassistant://hassio/addon/{addon[ATTR_SLUG]}",
        )
        if manufacturer := addon.get(ATTR_REPOSITORY) or addon.get(ATTR_URL):
            params[ATTR_MANUFACTURER] = manufacturer
        dev_reg.async_get_or_create(config_entry_id=entry_id, **params)


@callback
def async_register_os_in_dev_reg(
    entry_id: str, dev_reg: dr.DeviceRegistry, os_dict: dict[str, Any]
) -> None:
    """Register OS in the device registry."""
    params = DeviceInfo(
        identifiers={(DOMAIN, "OS")},
        manufacturer="Home Assistant",
        model=SupervisorEntityModel.OS,
        sw_version=os_dict[ATTR_VERSION],
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
    core_dict: dict[str, Any],
) -> None:
    """Register OS in the device registry."""
    params = DeviceInfo(
        identifiers={(DOMAIN, "core")},
        manufacturer="Home Assistant",
        model=SupervisorEntityModel.CORE,
        sw_version=core_dict[ATTR_VERSION],
        name="Home Assistant Core",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    dev_reg.async_get_or_create(config_entry_id=entry_id, **params)


@callback
def async_register_supervisor_in_dev_reg(
    entry_id: str,
    dev_reg: dr.DeviceRegistry,
    supervisor_dict: dict[str, Any],
) -> None:
    """Register OS in the device registry."""
    params = DeviceInfo(
        identifiers={(DOMAIN, "supervisor")},
        manufacturer="Home Assistant",
        model=SupervisorEntityModel.SUPERVIOSR,
        sw_version=supervisor_dict[ATTR_VERSION],
        name="Home Assistant Supervisor",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    dev_reg.async_get_or_create(config_entry_id=entry_id, **params)


@callback
def async_remove_addons_from_dev_reg(
    dev_reg: dr.DeviceRegistry, addons: set[str]
) -> None:
    """Remove addons from the device registry."""
    for addon_slug in addons:
        if dev := dev_reg.async_get_device(identifiers={(DOMAIN, addon_slug)}):
            dev_reg.async_remove_device(dev.id)


class HassioDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to retrieve Hass.io status."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, dev_reg: dr.DeviceRegistry
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=HASSIO_UPDATE_INTERVAL,
            # We don't want an immediate refresh since we want to avoid
            # fetching the container stats right away and avoid hammering
            # the Supervisor API on startup
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )
        self.hassio: HassIO = hass.data[DOMAIN]
        self.data = {}
        self.entry_id = config_entry.entry_id
        self.dev_reg = dev_reg
        self.is_hass_os = (get_info(self.hass) or {}).get("hassos") is not None
        self._container_updates: defaultdict[str, dict[str, set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )
        self.supervisor_client = get_supervisor_client(hass)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        is_first_update = not self.data

        try:
            await self.force_data_refresh(is_first_update)
        except HassioAPIError as err:
            raise UpdateFailed(f"Error on Supervisor API: {err}") from err

        new_data: dict[str, Any] = {}
        supervisor_info = get_supervisor_info(self.hass) or {}
        addons_info = get_addons_info(self.hass) or {}
        addons_stats = get_addons_stats(self.hass)
        addons_changelogs = get_addons_changelogs(self.hass)
        store_data = get_store(self.hass)

        if store_data:
            repositories = {
                repo.slug: repo.name
                for repo in StoreInfo.from_dict(store_data).repositories
            }
        else:
            repositories = {}

        new_data[DATA_KEY_ADDONS] = {
            addon[ATTR_SLUG]: {
                **addon,
                **((addons_stats or {}).get(addon[ATTR_SLUG]) or {}),
                ATTR_AUTO_UPDATE: (addons_info.get(addon[ATTR_SLUG]) or {}).get(
                    ATTR_AUTO_UPDATE, False
                ),
                ATTR_CHANGELOG: (addons_changelogs or {}).get(addon[ATTR_SLUG]),
                ATTR_REPOSITORY: repositories.get(
                    addon.get(ATTR_REPOSITORY), addon.get(ATTR_REPOSITORY, "")
                ),
            }
            for addon in supervisor_info.get("addons", [])
        }
        if self.is_hass_os:
            new_data[DATA_KEY_OS] = get_os_info(self.hass)

        new_data[DATA_KEY_CORE] = {
            **(get_core_info(self.hass) or {}),
            **get_core_stats(self.hass),
        }
        new_data[DATA_KEY_SUPERVISOR] = {
            **supervisor_info,
            **get_supervisor_stats(self.hass),
        }
        new_data[DATA_KEY_HOST] = get_host_info(self.hass) or {}

        # If this is the initial refresh, register all addons and return the dict
        if is_first_update:
            async_register_addons_in_dev_reg(
                self.entry_id, self.dev_reg, new_data[DATA_KEY_ADDONS].values()
            )
            async_register_core_in_dev_reg(
                self.entry_id, self.dev_reg, new_data[DATA_KEY_CORE]
            )
            async_register_supervisor_in_dev_reg(
                self.entry_id, self.dev_reg, new_data[DATA_KEY_SUPERVISOR]
            )
            async_register_host_in_dev_reg(self.entry_id, self.dev_reg)
            if self.is_hass_os:
                async_register_os_in_dev_reg(
                    self.entry_id, self.dev_reg, new_data[DATA_KEY_OS]
                )

        # Remove add-ons that are no longer installed from device registry
        supervisor_addon_devices = {
            list(device.identifiers)[0][1]
            for device in self.dev_reg.devices.get_devices_for_config_entry_id(
                self.entry_id
            )
            if device.model == SupervisorEntityModel.ADDON
        }
        if stale_addons := supervisor_addon_devices - set(new_data[DATA_KEY_ADDONS]):
            async_remove_addons_from_dev_reg(self.dev_reg, stale_addons)

        if not self.is_hass_os and (
            dev := self.dev_reg.async_get_device(identifiers={(DOMAIN, "OS")})
        ):
            # Remove the OS device if it exists and the installation is not hassos
            self.dev_reg.async_remove_device(dev.id)

        # If there are new add-ons, we should reload the config entry so we can
        # create new devices and entities. We can return an empty dict because
        # coordinator will be recreated.
        if self.data and set(new_data[DATA_KEY_ADDONS]) - set(
            self.data[DATA_KEY_ADDONS]
        ):
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.entry_id)
            )
            return {}

        return new_data

    async def force_info_update_supervisor(self) -> None:
        """Force update of the supervisor info."""
        self.hass.data[DATA_SUPERVISOR_INFO] = await self.hassio.get_supervisor_info()
        await self.async_refresh()

    async def force_data_refresh(self, first_update: bool) -> None:
        """Force update of the addon info."""
        container_updates = self._container_updates

        data = self.hass.data
        hassio = self.hassio
        updates = {
            DATA_INFO: hassio.get_info(),
            DATA_CORE_INFO: hassio.get_core_info(),
            DATA_SUPERVISOR_INFO: hassio.get_supervisor_info(),
            DATA_OS_INFO: hassio.get_os_info(),
        }
        if CONTAINER_STATS in container_updates[CORE_CONTAINER]:
            updates[DATA_CORE_STATS] = hassio.get_core_stats()
        if CONTAINER_STATS in container_updates[SUPERVISOR_CONTAINER]:
            updates[DATA_SUPERVISOR_STATS] = hassio.get_supervisor_stats()

        results = await asyncio.gather(*updates.values())
        for key, result in zip(updates, results, strict=False):
            data[key] = result

        _addon_data = data[DATA_SUPERVISOR_INFO].get("addons", [])
        all_addons: list[str] = []
        started_addons: list[str] = []
        for addon in _addon_data:
            slug = addon[ATTR_SLUG]
            all_addons.append(slug)
            if addon[ATTR_STATE] == ATTR_STARTED:
                started_addons.append(slug)
        #
        # Update add-on info if its the first update or
        # there is at least one entity that needs the data.
        #
        # When entities are added they call async_enable_container_updates
        # to enable updates for the endpoints they need via
        # async_added_to_hass. This ensures that we only update
        # the data for the endpoints that are needed to avoid unnecessary
        # API calls since otherwise we would fetch stats for all containers
        # and throw them away.
        #
        for data_key, update_func, enabled_key, wanted_addons, needs_first_update in (
            (
                DATA_ADDONS_STATS,
                self._update_addon_stats,
                CONTAINER_STATS,
                started_addons,
                False,
            ),
            (
                DATA_ADDONS_CHANGELOGS,
                self._update_addon_changelog,
                CONTAINER_CHANGELOG,
                all_addons,
                True,
            ),
            (
                DATA_ADDONS_INFO,
                self._update_addon_info,
                CONTAINER_INFO,
                all_addons,
                True,
            ),
        ):
            container_data: dict[str, Any] = data.setdefault(data_key, {})
            container_data.update(
                dict(
                    await asyncio.gather(
                        *[
                            update_func(slug)
                            for slug in wanted_addons
                            if (first_update and needs_first_update)
                            or enabled_key in container_updates[slug]
                        ]
                    )
                )
            )

    async def _update_addon_stats(self, slug: str) -> tuple[str, dict[str, Any] | None]:
        """Update single addon stats."""
        try:
            stats = await self.supervisor_client.addons.addon_stats(slug)
        except SupervisorError as err:
            _LOGGER.warning("Could not fetch stats for %s: %s", slug, err)
            return (slug, None)
        return (slug, stats.to_dict())

    async def _update_addon_changelog(self, slug: str) -> tuple[str, str | None]:
        """Return the changelog for an add-on."""
        try:
            changelog = await self.supervisor_client.store.addon_changelog(slug)
        except SupervisorError as err:
            _LOGGER.warning("Could not fetch changelog for %s: %s", slug, err)
            return (slug, None)
        return (slug, changelog)

    async def _update_addon_info(self, slug: str) -> tuple[str, dict[str, Any] | None]:
        """Return the info for an add-on."""
        try:
            info = await self.supervisor_client.addons.addon_info(slug)
        except SupervisorError as err:
            _LOGGER.warning("Could not fetch info for %s: %s", slug, err)
            return (slug, None)
        # Translate to legacy hassio names for compatibility
        info_dict = info.to_dict()
        info_dict["hassio_api"] = info_dict.pop("supervisor_api")
        info_dict["hassio_role"] = info_dict.pop("supervisor_role")
        return (slug, info_dict)

    @callback
    def async_enable_container_updates(
        self, slug: str, entity_id: str, types: set[str]
    ) -> CALLBACK_TYPE:
        """Enable updates for an add-on."""
        enabled_updates = self._container_updates[slug]
        for key in types:
            enabled_updates[key].add(entity_id)

        @callback
        def _remove() -> None:
            for key in types:
                enabled_updates[key].remove(entity_id)

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
            # Force refreshing updates for non-scheduled updates
            # If `raise_on_auth_failed` is set, it means this is
            # the first refresh and we do not want to delay
            # startup or cause a timeout so we only refresh the
            # updates if this is not a scheduled refresh and
            # we are not doing the first refresh.
            try:
                await self.hassio.refresh_updates()
            except HassioAPIError as err:
                _LOGGER.warning("Error on Supervisor API: %s", err)

        await super()._async_refresh(
            log_failures, raise_on_auth_failed, scheduled, raise_on_entry_error
        )
