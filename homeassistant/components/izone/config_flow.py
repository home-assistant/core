"""Config flow for izone."""

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


def _flow_uid_for_matching(flow: ConfigFlow) -> str | None:
    """Return a stable controller UID for deduplicating in-progress flows."""
    ctx_uid = flow.context.get("unique_id")
    if isinstance(ctx_uid, str):
        return ctx_uid
    return None


class IZoneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow: user, YAML import, HomeKit, and integration discovery."""

    VERSION = 2

    _user_discovered_controllers: list[pizone.Controller] | None = None
    _discovered_controller_ip: str | None = None

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
            await izone_discovery.async_start_discovery_service(self.hass)
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
        """User-started flow: offer configuration choices for discovered controllers.

        Discovery is started if not yet running, then a fresh discovery cycle is triggered
        and this step waits briefly for replies. The pizone library's built-in coalescing
        avoids redundant broadcasts when discovery was just started.

        While this interactive flow is active, runtime integration discovery remains
        blocked by ``_async_blocks_runtime_integration_discovery`` to avoid UI races.
        """

        if self._async_in_progress(include_uninitialized=True):
            return self.async_abort(reason="already_in_progress")

        try:
            controllers = await izone_discovery.async_discover_controllers(
                self.hass, refresh=True
            )
        except OSError:
            _LOGGER.debug("Unable to start iZone discovery service", exc_info=True)
            return self.async_abort(reason="discovery_failed")
        if not controllers:
            _LOGGER.debug("No controllers found")
            return self.async_abort(reason="no_devices_found")

        self._user_discovered_controllers = self._async_get_unconfigured_controllers(
            controllers
        )
        if not self._user_discovered_controllers:
            return self.async_abort(reason="already_configured")
        if len(self._user_discovered_controllers) > 1:
            return await self.async_step_select_controller()

        sole = self._user_discovered_controllers[0]
        await self.async_set_unique_id(sole.device_uid)
        self._discovered_controller_ip = sole.device_ip
        return await self.async_step_confirm()

    async def async_step_select_controller(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose one unconfigured controller after broadcast discovery."""
        if not self._user_discovered_controllers:
            return self.async_abort(reason="no_devices_found")

        by_uid = {
            controller.device_uid: controller
            for controller in self._user_discovered_controllers
        }
        selection_schema = vol.Schema(
            {
                vol.Required(
                    SELECTED_CONTROLLER_UID,
                    default=self._user_discovered_controllers[0].device_uid,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=controller.device_uid,
                                label=(
                                    f"{controller.device_uid} ({controller.device_ip})"
                                ),
                            )
                            for controller in self._user_discovered_controllers
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

            for ctrl in self._user_discovered_controllers:
                if ctrl.device_uid == primary.device_uid:
                    continue
                # Using integration_discovery lets HA's deduplication guard prevent stacking
                # flows for UIDs already in progress or already configured.
                self._async_schedule_integration_discovery_flow(
                    ctrl.device_uid,
                    ctrl.device_ip,
                )
            return await self._async_create_controller_entry(primary)

        controllers_lines = "\n".join(
            f"- {controller.device_uid} ({controller.device_ip})"
            for controller in self._user_discovered_controllers
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
            controllers = await izone_discovery.async_discover_controllers(
                self.hass,
                refresh=True,
                wait_for_uid=device_uid,
            )
        except OSError:
            _LOGGER.debug("Unable to start iZone discovery service", exc_info=True)
            return self.async_abort(reason="discovery_failed")
        controller = controllers.get(device_uid)
        if controller is None:
            return self.async_abort(reason="no_devices_found")

        self._discovered_controller_ip = controller.device_ip

        # Re-check after awaiting discovery to catch mid-flight configuration.
        self._abort_if_unique_id_configured()

        self._async_fan_out_discovered_controllers(
            controllers.values(),
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
        """Confirm adding a controller found via HomeKit or manual host."""
        if user_input is None:
            controller_uid = self.unique_id
            host = self._discovered_controller_ip
            assert isinstance(controller_uid, str)
            assert controller_uid
            assert host is not None
            host_str = str(host)
            self.context["title_placeholders"] = {
                "name": self._entry_title(controller_uid),
            }
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={
                    "controller_uid": controller_uid,
                    "host": host_str,
                },
            )

        try:
            controllers = await izone_discovery.async_discover_controllers(self.hass)
        except OSError:
            _LOGGER.debug("Unable to start iZone discovery service", exc_info=True)
            return self.async_abort(reason="discovery_failed")
        if not controllers:
            _LOGGER.debug("No controllers found")
            return self.async_abort(reason="no_devices_found")

        uid = self.unique_id
        assert isinstance(uid, str)

        controller = controllers.get(uid)
        if controller is None:
            _LOGGER.debug(
                "Discovered controller UID %s was not found during confirmation",
                uid,
            )
            return self.async_abort(reason="no_devices_found")
        return await self._async_create_controller_entry(
            controller,
        )

    # -- Private helpers

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
        hass: HomeAssistant, controllers: dict[str, pizone.Controller]
    ) -> dict[str, pizone.Controller]:
        """Remove UIDs listed in deprecated YAML ``exclude``."""
        excluded = izone_discovery.yaml_excluded_uids(hass)
        if not excluded:
            return controllers
        return {
            uid: ctrl
            for uid, ctrl in controllers.items()
            if ctrl.device_uid not in excluded
        }

    @callback
    def _async_get_unconfigured_controllers(
        self, controllers: dict[str, pizone.Controller]
    ) -> list[pizone.Controller]:
        """Return sorted unconfigured controllers for the interactive user flow."""
        controllers = self._filter_yaml_exclude(self.hass, controllers)
        # include_ignore=True ensures controllers whose entries have been explicitly
        # ignored by the user (SOURCE_IGNORE) are not re-offered as configurable.
        configured_uids = self._async_current_ids(include_ignore=True)
        return sorted(
            (
                controller
                for controller in controllers.values()
                if controller.device_uid not in configured_uids
            ),
            key=lambda controller: (controller.device_uid, controller.device_ip),
        )

    async def _async_create_controller_entry(
        self,
        controller: pizone.Controller,
    ) -> ConfigFlowResult:
        """Create the config entry for a chosen :class:`pizone.Controller` instance."""
        await self.async_set_unique_id(controller.device_uid)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self._entry_title(controller.device_uid),
            data={CONF_HOST: controller.device_ip},
        )

    @callback
    def _async_fan_out_discovered_controllers(
        self,
        controllers: Iterable[pizone.Controller],
        *,
        selected_uid: str,
    ) -> None:
        """Start confirm flows for every other discovered UID (import uses its own path)."""
        current_ids = self._async_current_ids(include_ignore=True)
        in_progress_ids = {
            flow["context"].get("unique_id")
            for flow in self._async_in_progress(include_uninitialized=True)
        }
        for candidate in controllers:
            if candidate.device_uid == selected_uid:
                continue
            if (
                candidate.device_uid in current_ids
                or candidate.device_uid in in_progress_ids
            ):
                continue
            self._async_schedule_integration_discovery_flow(
                candidate.device_uid,
                candidate.device_ip,
            )
