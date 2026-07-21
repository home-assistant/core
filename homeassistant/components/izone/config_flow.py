"""Config flow for izone."""

from collections.abc import Iterable, Mapping
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
CONF_SETUP_METHOD = "setup_method"
SETUP_METHOD_SEARCH = "search"
SETUP_METHOD_MANUAL_HOST = "manual_host"


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
    _user_form_errors: dict[str, str]
    _user_form_defaults: dict[str, Any]

    def __init__(self) -> None:
        """Initialize flow instance state."""
        self._user_form_errors = {}
        self._user_form_defaults = {}

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

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User-started flow: search the LAN or enter a controller host manually.

        While this interactive flow is active, runtime integration discovery remains
        blocked by ``_async_blocks_runtime_integration_discovery`` to avoid UI races.
        """
        self._async_abort_other_user_flows()

        discovery_active = izone_discovery.discovery_service_active(self.hass)
        errors = dict(self._user_form_errors)
        self._user_form_errors = {}
        defaults = dict(self._user_form_defaults)
        self._user_form_defaults = {}
        form_defaults = defaults or (user_input or {})

        if user_input is not None:
            if discovery_active:
                host = str(user_input.get(CONF_HOST, "")).strip()
                if not host:
                    errors[CONF_HOST] = "required"
                else:
                    return await self._async_probe_host_and_confirm(host)
            else:
                setup_method = user_input.get(CONF_SETUP_METHOD, SETUP_METHOD_SEARCH)
                host = str(user_input.get(CONF_HOST, "")).strip()

                if setup_method == SETUP_METHOD_MANUAL_HOST:
                    if not host:
                        errors[CONF_HOST] = "required"
                    else:
                        return await self._async_probe_host_and_confirm(host)
                else:
                    return await self.async_step_discover()

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_setup_schema(
                discovery_active=discovery_active,
                defaults=form_defaults,
            ),
            errors=errors or None,
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Broadcast discovery and offer unconfigured controllers."""
        try:
            endpoints = await izone_discovery.async_discover_all_endpoints(self.hass)
        except OSError:
            _LOGGER.debug("Unable to start iZone discovery service", exc_info=True)
            return self.async_abort(reason="discovery_failed")

        if not endpoints:
            _LOGGER.debug("No controllers found")
            self._user_form_errors = {"base": "no_devices_found"}
            self._user_form_defaults = {CONF_SETUP_METHOD: SETUP_METHOD_MANUAL_HOST}
            return await self.async_step_user(None)

        self._user_discovered_endpoints = self._async_get_unconfigured_endpoints(
            endpoints
        )
        if not self._user_discovered_endpoints:
            return self.async_abort(reason="already_configured")
        if len(self._user_discovered_endpoints) > 1:
            return await self.async_step_select_controller()

        sole = self._user_discovered_endpoints[0]
        await self.async_set_unique_id(sole.uid)
        self._discovered_controller_ip = sole.host
        return await self.async_step_confirm()

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

            for endpoint in self._user_discovered_endpoints:
                if endpoint.uid == primary.uid:
                    continue
                # Using integration_discovery lets HA's deduplication guard prevent stacking
                # flows for UIDs already in progress or already configured.
                self._async_schedule_integration_discovery_flow(
                    endpoint.uid,
                    endpoint.host,
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

    def _user_setup_schema(
        self,
        *,
        discovery_active: bool,
        defaults: Mapping[str, Any],
    ) -> vol.Schema:
        """Build the user step schema for discovery-active vs idle paths."""
        if discovery_active:
            host_default: Any = defaults.get(CONF_HOST, vol.UNDEFINED)
            return vol.Schema(
                {
                    vol.Required(CONF_HOST, default=host_default): str,
                }
            )

        method_default = defaults.get(CONF_SETUP_METHOD, SETUP_METHOD_SEARCH)
        host_default = defaults.get(CONF_HOST, "")
        return vol.Schema(
            {
                vol.Required(CONF_SETUP_METHOD, default=method_default): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=SETUP_METHOD_SEARCH,
                                label="Search for devices",
                            ),
                            SelectOptionDict(
                                value=SETUP_METHOD_MANUAL_HOST,
                                label="Enter host",
                            ),
                        ],
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(CONF_HOST, default=host_default): str,
            }
        )

    async def _async_probe_host_and_confirm(self, host: str) -> ConfigFlowResult:
        """Validate *host* and continue to confirm when a controller responds."""
        self._async_abort_entries_match({CONF_HOST: host})
        discovery_active = izone_discovery.discovery_service_active(self.hass)
        try:
            endpoint = await izone_discovery.async_discover_by_host(self.hass, host)
        except OSError:
            _LOGGER.debug("Unable to start iZone discovery service", exc_info=True)
            return self.async_abort(reason="discovery_failed")
        except pizone.UnpairedBridgeError:
            return self.async_abort(reason="unpaired_bridge")
        except pizone.ControllerAlreadyClaimedError:
            return self.async_abort(reason="already_configured")

        if endpoint is None:
            self._user_form_errors = {"base": "cannot_connect"}
            if discovery_active:
                self._user_form_defaults = {CONF_HOST: host}
            else:
                self._user_form_defaults = {
                    CONF_SETUP_METHOD: SETUP_METHOD_MANUAL_HOST,
                    CONF_HOST: host,
                }
            return await self.async_step_user(None)

        await self.async_set_unique_id(endpoint.uid)
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
