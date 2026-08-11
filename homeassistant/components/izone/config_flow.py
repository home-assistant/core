"""Config flow for izone."""

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
import logging
from typing import Any, Self, override

import pizone
from pizone.discovery import SCAN_TIMEOUT
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, FlowType
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
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

# Wait after IASD for ASPort replies (matches pizone discover_all wait).
USER_SCAN_WAIT_SECONDS = SCAN_TIMEOUT


@dataclass(frozen=True, slots=True)
class _ShelfCandidate:
    """An in-progress discovery/HomeKit flow on the Discovered shelf."""

    uid: str
    host: str
    flow_id: str


def _flow_uid_for_matching(flow: ConfigFlow) -> str | None:
    """Return a stable controller UID for deduplicating in-progress flows."""
    ctx_uid = flow.context.get("unique_id")
    if isinstance(ctx_uid, str):
        return ctx_uid
    return None


class IZoneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow: user, YAML import, HomeKit, and integration discovery."""

    VERSION = 2

    _discovered_controller_ip: str | None = None
    _user_discovery_task: asyncio.Task[None] | None = None
    _user_discovery_failed: bool = False

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

    @override
    async def async_step_user(
        self, _user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User-started flow: search the LAN, then offer discovered controllers."""
        return await self.async_step_discover()

    async def _async_run_user_discovery(self) -> None:
        """Scan and wait for the progress step (no unique_id work here)."""
        self._user_discovery_failed = False
        try:
            await izone_discovery.async_scan(self.hass)
        except OSError:
            _LOGGER.debug("Unable to start iZone discovery service", exc_info=True)
            self._user_discovery_failed = True
            return
        # Sleep is the ASPort reply window; the event loop processes datagrams
        # and eager discovery-flow inits during it (no post-sleep drain).
        await asyncio.sleep(USER_SCAN_WAIT_SECONDS)

    async def async_step_discover(
        self, _user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Broadcast discovery with a progress UI, then continue to discovery_done."""
        if not self._user_discovery_task:
            self._user_discovery_task = self.hass.async_create_task(
                self._async_run_user_discovery()
            )
            # Always leave progress first; the task may already be done (eager).
            return self.async_show_progress(
                step_id="discover",
                progress_action="discover",
                progress_task=self._user_discovery_task,
            )

        if not self._user_discovery_task.done():
            return self.async_show_progress(
                step_id="discover",
                progress_action="discover",
                progress_task=self._user_discovery_task,
            )

        self._user_discovery_task = None
        return self.async_show_progress_done(next_step_id="discovery_done")

    async def async_step_discovery_done(
        self, _user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """After Search scan: abort, hand off the sole shelf flow, or choose."""
        if self._user_discovery_failed:
            return self.async_abort(reason="discovery_failed")

        candidates = self._async_user_candidates()
        if not candidates:
            _LOGGER.debug("No controllers found on the Discovered shelf")
            return self.async_abort(reason="no_devices_found")
        if len(candidates) == 1:
            return self.async_abort(
                reason="continue_setup",
                next_flow=(FlowType.CONFIG_FLOW, candidates[0].flow_id),
            )

        selection_schema = vol.Schema(
            {
                vol.Required(
                    SELECTED_CONTROLLER_UID,
                    default=candidates[0].uid,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=candidate.uid,
                                label=f"{candidate.uid} ({candidate.host})",
                            )
                            for candidate in candidates
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        controllers_lines = "\n".join(
            f"- {candidate.uid} ({candidate.host})" for candidate in candidates
        )
        return self.async_show_form(
            step_id="select_controller",
            data_schema=selection_schema,
            description_placeholders={"controllers": controllers_lines},
        )

    async def async_step_select_controller(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Hand off to the shelf confirm for the selected controller UID."""
        if user_input is None:
            return await self.async_step_discovery_done()
        selected_uid = user_input[SELECTED_CONTROLLER_UID]
        by_uid = {
            candidate.uid: candidate for candidate in self._async_user_candidates()
        }
        if (selected := by_uid.get(selected_uid)) is not None:
            return self.async_abort(
                reason="continue_setup",
                next_flow=(FlowType.CONFIG_FLOW, selected.flow_id),
            )
        if selected_uid in self._async_current_ids(include_ignore=True):
            return self.async_abort(reason="already_configured")
        return self.async_abort(reason="no_devices_found")

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
        controller_uid = self.unique_id
        host = self._discovered_controller_ip
        assert isinstance(controller_uid, str)
        assert controller_uid
        assert host is not None

        if user_input is None:
            self.context["title_placeholders"] = {
                "name": self._entry_title(controller_uid),
                "host": str(host),
            }
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={
                    "controller_uid": controller_uid,
                    "host": str(host),
                },
            )

        return await self._async_create_controller_entry(
            pizone.ControllerEndpoint(uid=controller_uid, host=str(host))
        )

    # -- Private helpers

    @callback
    def _async_user_candidates(self) -> list[_ShelfCandidate]:
        """Return Discovered-shelf flows (integration discovery and HomeKit)."""
        candidates: list[_ShelfCandidate] = []
        for flow in self.hass.config_entries.flow.async_progress_by_handler(
            DOMAIN, include_uninitialized=True
        ):
            if flow["flow_id"] == self.flow_id:
                continue
            context = flow["context"]
            if context.get("source") not in (
                config_entries.SOURCE_INTEGRATION_DISCOVERY,
                config_entries.SOURCE_HOMEKIT,
            ):
                continue
            uid = context.get("unique_id")
            placeholders = context.get("title_placeholders")
            host = placeholders.get("host") if placeholders is not None else None
            if not isinstance(uid, str) or not isinstance(host, str):
                continue
            candidates.append(
                _ShelfCandidate(uid=uid, host=host, flow_id=flow["flow_id"])
            )
        return sorted(candidates, key=lambda candidate: (candidate.uid, candidate.host))

    @callback
    def _async_schedule_integration_discovery_flow(
        self,
        uid: str,
        host: str,
    ) -> None:
        """Queue integration discovery (import fan-out or HomeKit sibling)."""
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
