"""Config flow for izone.

Module-level discovery helpers and :func:`async_note_integration_discovery` stay at
module scope so tests and ``__init__.py`` migration can patch them without depending
on :class:`IZoneConfigFlow`.
"""

from collections.abc import Iterable
import logging
from typing import Any, Self

import pizone
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EXCLUDE, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DATA_CONFIG, IZONE, TIMEOUT_DISCOVERY

_LOGGER = logging.getLogger(__name__)

# --- Flow context keys (also used in tests) ---

DISCOVERY_DATA_UID = "uid"
SELECTED_CONTROLLER_UID = "selected_controller_uid"

# ---------------------------------------------------------------------------
# On-demand discovery (module scope for migration + tests)
# ---------------------------------------------------------------------------


async def async_discover_controllers(
    hass: HomeAssistant,
    *,
    refresh: bool = False,
    wait_for_uid: str | None = None,
) -> dict[str, pizone.Controller]:
    """Return currently known controllers, optionally waiting for a UID during rescan.

    If ``refresh`` is true, waits for fresh discovery data using the pizone library's
    built-in coalescing and cool-down logic.  When ``wait_for_uid`` is provided, returns
    as soon as that specific controller appears (or after the timeout).

    If discovery is not yet running, it is started first.

    Raises:
        OSError: Discovery service failed to start or controller fetch failed.
    """
    from .discovery import async_start_discovery_service  # noqa: PLC0415

    disco = await async_start_discovery_service(hass)

    if not refresh:
        return await disco.pi_disco.fetch_controllers()

    if wait_for_uid is not None:
        await disco.pi_disco.fetch_controller(wait_for_uid, timeout=TIMEOUT_DISCOVERY)
        return await disco.pi_disco.fetch_controllers()

    return await disco.pi_disco.fetch_controllers(timeout=TIMEOUT_DISCOVERY)


def _yaml_excluded_uids(hass: HomeAssistant) -> set[str]:
    """Return controller UIDs listed in deprecated YAML ``exclude``."""
    conf: ConfigType | None = hass.data.get(DATA_CONFIG)
    if not conf:
        return set()
    return set(conf.get(CONF_EXCLUDE, ()))


@callback
def async_note_integration_discovery(
    hass: HomeAssistant, ctrl: pizone.Controller
) -> None:
    """Start a config flow when the shared discovery service reports a controller."""
    if ctrl.device_uid in _yaml_excluded_uids(hass):
        return
    if hass.config_entries.async_entry_for_domain_unique_id(IZONE, ctrl.device_uid):
        return
    if _async_blocks_runtime_integration_discovery(hass):
        return
    discovery_flow.async_create_flow(
        hass,
        IZONE,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            DISCOVERY_DATA_UID: ctrl.device_uid,
            CONF_HOST: ctrl.device_ip,
        },
    )


@callback
def _async_blocks_runtime_integration_discovery(hass: HomeAssistant) -> bool:
    """Return True when an interactive setup flow should own the UI."""
    for flw in hass.config_entries.flow.async_progress_by_handler(
        IZONE, include_uninitialized=True
    ):
        src = flw["context"].get("source")
        if src == config_entries.SOURCE_USER:
            return True
    return False


def _flow_uid_for_matching(flow: ConfigFlow) -> str | None:
    """Return a stable controller UID for deduplicating in-progress flows."""
    ctx_uid = flow.context.get("unique_id")
    if isinstance(ctx_uid, str):
        return ctx_uid
    return None


# ---------------------------------------------------------------------------
# Config flow
# ---------------------------------------------------------------------------


class IZoneConfigFlow(ConfigFlow, domain=IZONE):
    """Config flow: user, YAML import, HomeKit, and integration discovery."""

    VERSION = 2

    _user_discovered_controllers: list[pizone.Controller] | None = None
    _discovered_controller_ip: str | None = None

    @callback
    def _async_is_ignored_uid(self, uid: str) -> bool:
        """Return True when *uid* has an ignore entry."""
        return any(
            entry.unique_id == uid and entry.source == config_entries.SOURCE_IGNORE
            for entry in self.hass.config_entries.async_entries(IZONE)
        )

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

        from .discovery import async_start_discovery_service  # noqa: PLC0415

        try:
            await async_start_discovery_service(self.hass)
        except OSError:
            _LOGGER.debug("Unable to start iZone discovery from import", exc_info=True)
            return self.async_abort(reason="discovery_failed")

        return self.async_abort(reason="no_devices_found")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User-started flow: offer configuration choices for discovered controllers.

        If discovery is already running, a rescan is requested and this step waits briefly for
        replies. If discovery is not running yet, it is started and the initial discovery cycle
        is used without forcing an immediate second rescan.

        While this interactive flow is active, runtime integration discovery remains
        blocked by ``_async_blocks_runtime_integration_discovery`` to avoid UI races.
        """
        del user_input

        if self._async_in_progress(include_uninitialized=True):
            return self.async_abort(reason="already_in_progress")

        # refresh=True requests a rescan only when discovery is already running.
        try:
            controllers = await async_discover_controllers(self.hass, refresh=True)
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
            try:
                payload = selection_schema(user_input)
            except vol.Invalid:
                return self.async_abort(reason="no_devices_found")

            selected_uid = payload[SELECTED_CONTROLLER_UID]
            if (primary := by_uid.get(selected_uid)) is None:
                return self.async_abort(reason="no_devices_found")

            for ctrl in self._user_discovered_controllers:
                if ctrl.device_uid == primary.device_uid:
                    continue
                # Fan out confirm flows for all the other discovered controllers in parallel with the selected one.
                # These will appear as discovered controllers, which is really the only way to manage this without
                # it getting very messy.
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

    async def async_step_homekit(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Map HomeKit ``md`` to an iZone UID, discover LAN controllers, then confirm."""
        model = discovery_info.properties.get("md", "")
        if not model.startswith("iZone "):
            return self.async_abort(reason="no_devices_found")

        device_uid = model.split(" ", 1)[1]

        if device_uid in _yaml_excluded_uids(self.hass) or self._async_is_ignored_uid(
            device_uid
        ):
            return self.async_abort(reason="no_devices_found")

        if self.hass.config_entries.async_entry_for_domain_unique_id(IZONE, device_uid):
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(device_uid)
        self._abort_if_unique_id_configured()

        # A HomeKit advertisement implies a specific UID is on the LAN.  Wait for it.
        try:
            controllers = await async_discover_controllers(
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

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle fan-out, YAML import secondaries, and runtime discovery."""
        uid = discovery_info.get(DISCOVERY_DATA_UID)
        host = discovery_info.get(CONF_HOST)
        if not isinstance(uid, str) or not isinstance(host, str):
            return self.async_abort(reason="no_devices_found")
        if uid in _yaml_excluded_uids(self.hass) or self._async_is_ignored_uid(uid):
            return self.async_abort(reason="no_devices_found")

        await self.async_set_unique_id(uid)
        self._abort_if_unique_id_configured()
        # Discovery host is for confirm-step context only; runtime discovery owns
        # current device IP state and keeps it up to date independently of entry data.
        self._discovered_controller_ip = host
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding a controller found via HomeKit or manual host."""
        if user_input is None:
            controller_uid = self.unique_id
            host = self._discovered_controller_ip
            if (
                not isinstance(controller_uid, str)
                or not controller_uid
                or not isinstance(host, str)
                or not host
            ):
                _LOGGER.error(
                    "Config flow confirm reached with invalid data (source=%s)",
                    self.context.get("source"),
                )
                return self.async_abort(reason="invalid_flow_state")
            if "title_placeholders" not in self.context:
                self.context["title_placeholders"] = {
                    "name": self._entry_title(controller_uid),
                }
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={
                    "controller_uid": controller_uid,
                    "host": host,
                },
            )

        try:
            controllers = await async_discover_controllers(self.hass)
        except OSError:
            _LOGGER.debug("Unable to start iZone discovery service", exc_info=True)
            return self.async_abort(reason="discovery_failed")
        if not controllers:
            _LOGGER.debug("No controllers found")
            return self.async_abort(reason="no_devices_found")

        uid = self.unique_id
        if not isinstance(uid, str):
            return self.async_abort(reason="no_devices_found")

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
            IZONE,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={DISCOVERY_DATA_UID: uid, CONF_HOST: host},
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
        excluded = _yaml_excluded_uids(hass)
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
        configured_uids = self._async_current_ids(include_ignore=False)
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
            data={},
        )

    @callback
    def _async_fan_out_discovered_controllers(
        self,
        controllers: Iterable[pizone.Controller],
        *,
        selected_uid: str,
    ) -> None:
        """Start confirm flows for every other discovered UID (import uses its own path)."""
        current_ids = self._async_current_ids()
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
