"""Config flow for izone."""

import asyncio
from collections.abc import Iterable
import logging
from typing import Any, Self, override

import pizone
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.helpers.typing import DiscoveryInfoType

from . import discovery as izone_discovery
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SELECTED_CONTROLLER_UID = "selected_controller_uid"

STEP_MANUAL_HOST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): vol.All(str, vol.Length(min=1)),
    }
)


def _flow_uid_for_matching(flow: ConfigFlow) -> str | None:
    """Return a stable controller UID for deduplicating in-progress flows."""
    ctx_uid = flow.context.get("unique_id")
    if isinstance(ctx_uid, str):
        return ctx_uid
    return None


class IZoneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow: user, YAML import, HomeKit, and integration discovery."""

    VERSION = 2

    _user_discovered_endpoints: list[pizone.ControllerEndpoint] | None = None
    _discovered_controller_ip: str | None = None
    _discovery_task: asyncio.Task[None] | None = None
    _broadcast_endpoints: dict[str, pizone.ControllerEndpoint] | None = None
    _discovery_failed: bool = False
    # True when Add integration skipped Search because an entry already owns discovery.
    _manual_host_additional: bool = False

    @override
    def is_matching(self, other_flow: Self) -> bool:
        """Match in-progress flows for the same controller UID."""
        self_uid = _flow_uid_for_matching(self)
        other_uid = _flow_uid_for_matching(other_flow)
        if self_uid is None or other_uid is None:
            return False
        return self_uid == other_uid

    # -- User-visible and internal steps (roughly: import → user → discovery UI → HK → fan-out → confirm)

    async def async_step_import(
        self, _import_data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """YAML import: start discovery and let runtime discovery offer flows.

        The import step runs exactly once (Home Assistant calls it only when the YAML
        key is present at startup). We start the discovery service so every controller
        surfaced by the service's normal listener appears in discovered devices and
        still requires normal confirmation.

        No explicit rescan is issued: the service will broadcast its own discovery
        request as part of start-up, and the import step itself will not be repeated.
        """
        if self._async_in_progress(include_uninitialized=True):
            return self.async_abort(reason="already_in_progress")

        try:
            await izone_discovery.async_ensure_discovery(self.hass)
        except OSError:
            _LOGGER.debug("Unable to start iZone discovery from import", exc_info=True)
            return self.async_abort(reason="discovery_failed")

        # Discovery is now running; each controller will surface as an individual
        # integration_discovery flow.  Use a dedicated abort reason so the UI does
        # not misleadingly show "No devices found" when setup is actually in progress.
        return self.async_abort(reason="discovery_started")

    @callback
    def _async_abort_other_user_flows(self) -> None:
        """Drop stale interactive user flows (e.g. after a browser refresh)."""
        for flow in self._async_in_progress(include_uninitialized=True):
            if flow["context"].get("source") != config_entries.SOURCE_USER:
                continue
            self.hass.config_entries.flow.async_abort(flow["flow_id"])

    @callback
    def _async_user_setup_host_only(self) -> bool:
        """Return True when Add integration should skip Search.

        Host-only is for when a loaded entry already owns shared discovery.
        A failed/aborted search may leave the UDP service running briefly; still
        offer Search until an entry is loaded so the user can try again.
        """
        return bool(self.hass.config_entries.async_loaded_entries(DOMAIN))

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User-started flow: search the LAN or enter a controller host manually.

        While this interactive flow is active, runtime integration discovery remains
        blocked by ``_async_blocks_runtime_integration_discovery`` to avoid UI races.
        """
        self._async_abort_other_user_flows()

        if self._async_user_setup_host_only():
            self._manual_host_additional = True
            return await self.async_step_manual_host()

        return self.async_show_menu(
            step_id="user",
            menu_options=["discover", "manual_host"],
        )

    async def _async_run_broadcast_discovery(self) -> None:
        """Run LAN broadcast discovery for the progress step."""
        self._discovery_failed = False
        try:
            self._broadcast_endpoints = (
                await izone_discovery.async_discover_all_endpoints(self.hass)
            )
        except OSError:
            _LOGGER.debug("Unable to start iZone discovery service", exc_info=True)
            self._discovery_failed = True
            self._broadcast_endpoints = None

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Broadcast discovery with a progress UI, then offer controllers."""
        if self._discovery_task is None:
            self._discovery_task = self.hass.async_create_task(
                self._async_run_broadcast_discovery()
            )
            return self.async_show_progress(
                step_id="discover",
                progress_action="discover",
                progress_task=self._discovery_task,
            )

        if not self._discovery_task.done():
            return self.async_show_progress(
                step_id="discover",
                progress_action="discover",
                progress_task=self._discovery_task,
            )

        self._discovery_task = None
        if self._discovery_failed:
            return self.async_show_progress_done(next_step_id="discovery_failed")

        endpoints = self._broadcast_endpoints or {}
        if not endpoints:
            _LOGGER.debug("No controllers found")
            # Empty search started discovery solely for this scan; stop it when no
            # loaded entry needs the shared listener.
            if not self._async_user_setup_host_only():
                await izone_discovery.async_stop_discovery(self.hass)
            return self.async_show_progress_done(next_step_id="no_devices")

        self._user_discovered_endpoints = self._async_get_unconfigured_endpoints(
            endpoints
        )
        if not self._user_discovered_endpoints:
            return self.async_show_progress_done(next_step_id="already_configured")
        if len(self._user_discovered_endpoints) > 1:
            return self.async_show_progress_done(next_step_id="select_controller")

        sole = self._user_discovered_endpoints[0]
        await self.async_set_unique_id(sole.uid)
        self._discovered_controller_ip = sole.host
        return self.async_show_progress_done(next_step_id="confirm")

    async def async_step_discovery_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort after broadcast discovery failed to start."""
        return self.async_abort(reason="discovery_failed")

    async def async_step_already_configured(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort when broadcast discovery only found configured controllers."""
        return self.async_abort(reason="already_configured")

    async def async_step_no_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Nudge manual host entry when broadcast discovery finds nothing."""
        # Error string covers this path; keep the default host-entry description.
        self._manual_host_additional = False
        return self._async_show_manual_host_form(errors={"base": "no_devices_found"})

    async def async_step_manual_host(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter a controller IP address or hostname."""
        return await self._async_manual_host(user_input)

    async def async_step_manual_host_additional(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter another controller's address when one is already set up."""
        self._manual_host_additional = True
        return await self._async_manual_host(user_input)

    async def _async_manual_host(
        self, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Shared manual-host submit / show logic."""
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            if not host:
                return self._async_show_manual_host_form(
                    errors={CONF_HOST: "required"},
                    suggested_values=user_input,
                )
            return await self._async_probe_host_and_confirm(host)

        return self._async_show_manual_host_form()

    @callback
    def _async_show_manual_host_form(
        self,
        *,
        errors: dict[str, str] | None = None,
        suggested_values: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show the manual host entry form."""
        # Separate step_id so both descriptions stay fully translatable.
        step_id = (
            "manual_host_additional" if self._manual_host_additional else "manual_host"
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                STEP_MANUAL_HOST_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    async def async_step_select_controller(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose one unconfigured controller after broadcast discovery."""
        if not self._user_discovered_endpoints:
            return self.async_abort(reason="no_devices_found")

        by_uid = {
            endpoint.uid: endpoint for endpoint in self._user_discovered_endpoints
        }
        selection_schema = vol.Schema(
            {
                vol.Required(
                    SELECTED_CONTROLLER_UID,
                    default=self._user_discovered_endpoints[0].uid,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=endpoint.uid,
                                label=f"{endpoint.uid} ({endpoint.host})",
                            )
                            for endpoint in self._user_discovered_endpoints
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        if user_input is not None:
            selected_uid = user_input[SELECTED_CONTROLLER_UID]
            if (primary := by_uid.get(selected_uid)) is None:
                return self.async_abort(reason="no_devices_found")

            # Skip ignored UIDs (include_ignore=True); integration_discovery cannot
            # re-offer them — only SOURCE_USER can replace SOURCE_IGNORE.
            self._async_fan_out_discovered_endpoints(
                self._user_discovered_endpoints,
                selected_uid=primary.uid,
            )
            return await self._async_create_controller_entry(primary)

        controllers_lines = "\n".join(
            f"- {endpoint.uid} ({endpoint.host})"
            for endpoint in self._user_discovered_endpoints
        )
        return self.async_show_form(
            step_id="select_controller",
            data_schema=selection_schema,
            description_placeholders={"controllers": controllers_lines},
        )

    @override
    async def async_step_homekit(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Map HomeKit ``md`` to an iZone UID, discover LAN controllers, then confirm."""
        model = discovery_info.properties.get("md", "")
        if not model.startswith("iZone "):
            return self.async_abort(reason="no_devices_found")

        device_uid = model.split(" ", 1)[1]

        if device_uid in izone_discovery.yaml_excluded_uids(self.hass):
            return self.async_abort(reason="no_devices_found")

        # async_set_unique_id + _abort_if_unique_id_configured handles both existing
        # entries (including SOURCE_IGNORE) and stale in-progress flows for this UID.
        # A direct async_entry_for_domain_unique_id pre-check would miss the
        # flow-deduplication side effect of async_set_unique_id(raise_on_progress=True).
        await self.async_set_unique_id(device_uid)
        self._abort_if_unique_id_configured()

        # A HomeKit advertisement implies a specific UID is on the LAN.  Wait for it.
        try:
            endpoints = await izone_discovery.async_discover_all_endpoints(self.hass)
            endpoint = endpoints.get(device_uid)
            if endpoint is None:
                endpoint = await izone_discovery.async_discover_endpoint(
                    self.hass, device_uid
                )
                if endpoint is None:
                    return self.async_abort(reason="no_devices_found")
                endpoints = {**endpoints, endpoint.uid: endpoint}
        except OSError:
            _LOGGER.debug("Unable to start iZone discovery service", exc_info=True)
            return self.async_abort(reason="discovery_failed")

        self._discovered_controller_ip = endpoint.host

        # Re-check after awaiting discovery to catch mid-flight configuration.
        self._abort_if_unique_id_configured()

        self._async_fan_out_discovered_endpoints(
            endpoints.values(),
            selected_uid=device_uid,
        )

        return await self.async_step_confirm()

    @override
    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle fan-out, YAML import secondaries, and runtime discovery."""
        uid = self.context["unique_id"]
        host = discovery_info[CONF_HOST]
        if uid in izone_discovery.yaml_excluded_uids(self.hass):
            return self.async_abort(reason="no_devices_found")

        await self.async_set_unique_id(uid)
        self._abort_if_unique_id_configured()
        # Persist through confirm into entry data as CONF_HOST.
        self._discovered_controller_ip = host
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding a controller found via HomeKit or discovery."""
        if user_input is not None:
            return await self._async_finalize_confirm()

        controller_uid = self.unique_id
        assert isinstance(controller_uid, str)
        if self._async_is_readding_ignored_controller(controller_uid):
            return await self.async_step_confirm_ignored()
        return self._async_show_confirm_form("confirm")

    async def async_step_confirm_ignored(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-adding a controller that was previously ignored."""
        if user_input is not None:
            return await self._async_finalize_confirm()
        return self._async_show_confirm_form("confirm_ignored")

    @callback
    def _async_show_confirm_form(self, step_id: str) -> ConfigFlowResult:
        """Show the confirm-only form for the given step."""
        controller_uid = self.unique_id
        host = self._discovered_controller_ip
        assert isinstance(controller_uid, str)
        assert controller_uid
        assert host is not None
        self._set_confirm_only()
        self.context["title_placeholders"] = {
            "name": self._entry_title(controller_uid),
        }
        return self.async_show_form(
            step_id=step_id,
            description_placeholders={
                "controller_uid": controller_uid,
                "host": str(host),
            },
        )

    # -- Private helpers

    async def _async_probe_host_and_confirm(self, host: str) -> ConfigFlowResult:
        """Validate *host* and continue to confirm when a controller responds."""
        self._async_abort_entries_match({CONF_HOST: host})
        try:
            endpoint = await izone_discovery.async_discover_by_host(self.hass, host)
        except OSError:
            _LOGGER.debug("Unable to start iZone discovery service", exc_info=True)
            return self.async_abort(reason="discovery_failed")
        except pizone.UnpairedBridgeError:
            return self.async_abort(reason="unpaired_bridge")
        except pizone.ControllerAlreadyClaimedError:
            return self.async_abort(reason="already_configured")
        except Exception:  # noqa: BLE001 - content-shaped probe errors until pizone 1.3.9
            # Manual host can hit non-iZone HTTP bodies; pizone._probe still lets
            # content-shaped errors propagate (harden in 1.3.9).
            _LOGGER.debug("Unexpected error probing iZone host %s", host, exc_info=True)
            endpoint = None

        if endpoint is None:
            return self._async_show_manual_host_form(
                errors={"base": "cannot_connect"},
                suggested_values={CONF_HOST: host},
            )

        await self.async_set_unique_id(endpoint.uid)
        # Manual host can be a repair path when UDP cannot update CONF_HOST; abort with
        # an explicit reason so the side-effect is visible (not a reconfigure flow).
        if (
            existing := self.hass.config_entries.async_entry_for_domain_unique_id(
                self.handler, endpoint.uid
            )
        ) is not None and existing.data.get(CONF_HOST) != endpoint.host:
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: endpoint.host},
                error="already_configured_host_updated",
                description_placeholders={"host": endpoint.host},
            )
        self._abort_if_unique_id_configured()
        self._discovered_controller_ip = endpoint.host
        return await self.async_step_confirm()

    @callback
    def _async_schedule_integration_discovery_flow(
        self,
        uid: str,
        host: str,
    ) -> None:
        """Queue integration discovery (import fan-out or manual discovery pick)."""
        discovery_flow.async_create_flow(
            self.hass,
            DOMAIN,
            context={
                "source": config_entries.SOURCE_INTEGRATION_DISCOVERY,
                "unique_id": uid,
            },
            data={CONF_HOST: host},
        )

    @staticmethod
    def _entry_title(device_uid: str) -> str:
        """Standard config entry title for a controller UID."""
        return f"iZone {device_uid}"

    @staticmethod
    def _filter_yaml_exclude(
        hass: HomeAssistant, endpoints: dict[str, pizone.ControllerEndpoint]
    ) -> dict[str, pizone.ControllerEndpoint]:
        """Remove UIDs listed in deprecated YAML ``exclude``."""
        excluded = izone_discovery.yaml_excluded_uids(hass)
        if not excluded:
            return endpoints
        return {
            uid: endpoint
            for uid, endpoint in endpoints.items()
            if endpoint.uid not in excluded
        }

    @callback
    def _async_get_unconfigured_endpoints(
        self, endpoints: dict[str, pizone.ControllerEndpoint]
    ) -> list[pizone.ControllerEndpoint]:
        """Return sorted unconfigured endpoints for the interactive user flow."""
        endpoints = self._filter_yaml_exclude(self.hass, endpoints)
        configured_uids = self._async_current_ids(include_ignore=False)
        return sorted(
            (
                endpoint
                for endpoint in endpoints.values()
                if endpoint.uid not in configured_uids
            ),
            key=lambda endpoint: (endpoint.uid, endpoint.host),
        )

    async def _async_finalize_confirm(self) -> ConfigFlowResult:
        """Validate confirm state and create the config entry."""
        controller_uid = self.unique_id
        host = self._discovered_controller_ip
        assert isinstance(controller_uid, str)
        assert controller_uid
        assert host is not None
        return await self._async_create_controller_entry(
            pizone.ControllerEndpoint(uid=controller_uid, host=str(host))
        )

    @callback
    def _async_is_readding_ignored_controller(self, controller_uid: str) -> bool:
        """Return True when the user is explicitly re-adding an ignored controller."""
        if self.context.get("source") != config_entries.SOURCE_USER:
            return False
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            self.handler, controller_uid
        )
        return entry is not None and entry.source == config_entries.SOURCE_IGNORE

    async def _async_create_controller_entry(
        self,
        endpoint: pizone.ControllerEndpoint,
    ) -> ConfigFlowResult:
        """Create the config entry for a chosen discovered endpoint."""
        await self.async_set_unique_id(endpoint.uid)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self._entry_title(endpoint.uid),
            data={CONF_HOST: endpoint.host},
        )

    @callback
    def _async_fan_out_discovered_endpoints(
        self,
        endpoints: Iterable[pizone.ControllerEndpoint],
        *,
        selected_uid: str,
    ) -> None:
        """Start confirm flows for every other discovered UID (import uses its own path)."""
        current_ids = self._async_current_ids(include_ignore=True)
        in_progress_ids = {
            flow["context"].get("unique_id")
            for flow in self._async_in_progress(include_uninitialized=True)
        }
        for candidate in endpoints:
            if candidate.uid == selected_uid:
                continue
            if candidate.uid in current_ids or candidate.uid in in_progress_ids:
                continue
            self._async_schedule_integration_discovery_flow(
                candidate.uid,
                candidate.host,
            )
