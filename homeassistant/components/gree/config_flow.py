"""Config flow for Gree."""

import logging
from typing import Any, Self, override

from greeclimate.device import Device, DeviceInfo
from greeclimate.exceptions import DeviceNotBoundError, DeviceTimeoutError
import probatio

from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_INTEGRATION_DISCOVERY,
    SOURCE_USER,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_IDENTIFIER, DOMAIN
from .coordinator import async_bind_device
from .discovery import async_get_discovery, device_info_to_data, normalize_identifier
from .migration import async_get_legacy_identifiers

_LOGGER = logging.getLogger(__name__)


class GreeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Enroll one explicitly selected Gree device."""

    VERSION = 2
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._devices: dict[str, dict[str, Any]] = {}
        self._selected: dict[str, Any] | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Find available devices for selection."""
        try:
            devices = await async_get_discovery(self.hass).async_scan()
        except OSError, TimeoutError:
            return self.async_abort(reason="cannot_connect")
        self._devices = self._available_devices(devices)
        if not self._devices:
            return self.async_abort(reason="no_devices_found")
        return await self.async_step_pick_device()

    def _available_devices(
        self, devices: dict[str, DeviceInfo]
    ) -> dict[str, dict[str, Any]]:
        """Exclude configured and migration-reserved identities."""
        configured = {
            entry.unique_id
            for entry in self._async_current_entries(include_ignore=False)
        } | async_get_legacy_identifiers(self.hass)
        return {
            identifier: device_info_to_data(info)
            for identifier, info in devices.items()
            if identifier not in configured
        }

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate only the explicitly selected candidate."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._selected = self._devices[user_input[CONF_DEVICE]]
            result, error = await self._async_validate_selected()
            if result:
                return result
            errors["base"] = error
        choices = {
            identifier: (
                f"{data[CONF_NAME] or data[CONF_IDENTIFIER]} "
                f"({data[CONF_HOST]}) {data[CONF_IDENTIFIER]}"
            )
            for identifier, data in self._devices.items()
        }
        return self.async_show_form(
            step_id="pick_device",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_DEVICE): probatio.In(choices)}
            ),
            errors=errors,
        )

    def _known_device(self, data: dict[str, Any]) -> ConfigFlowResult | None:
        """Update a known endpoint without replacing or enabling its entry."""
        identifier = normalize_identifier(data[CONF_IDENTIFIER])
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, identifier
        )
        if entry is not None:
            if entry.source == SOURCE_IGNORE:
                return self.async_abort(reason="already_configured")
            endpoint_changed = any(
                entry.data.get(key) != data[key] for key in (CONF_HOST, CONF_PORT)
            )
            updates = {
                **entry.data,
                **data,
                CONF_IDENTIFIER: entry.data[CONF_IDENTIFIER],
            }
            if (
                self.hass.config_entries.async_update_entry(entry, data=updates)
                and endpoint_changed
                and entry.disabled_by is None
                and (
                    entry.state.recoverable
                    or entry.state is ConfigEntryState.SETUP_IN_PROGRESS
                )
            ):
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_abort(reason="already_configured")
        if identifier in async_get_legacy_identifiers(self.hass):
            return self.async_abort(reason="already_configured")
        return None

    @override
    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Offer unknown discoveries for confirmation, including onboarding."""
        data = dict(discovery_info)
        if result := self._known_device(data):
            return result
        await self.async_set_unique_id(
            normalize_identifier(data[CONF_IDENTIFIER]), raise_on_progress=False
        )
        self._selected = data
        if self.hass.config_entries.flow.async_has_matching_flow(self):
            return self.async_abort(
                reason="already_in_progress", translation_domain=HOMEASSISTANT_DOMAIN
            )
        return await self.async_step_discovery_confirm()

    @override
    def is_matching(self, other_flow: Self) -> bool:
        """Refresh a pending discovery before rejecting its duplicate."""
        if self.unique_id != other_flow.unique_id:
            return False
        assert self._selected is not None
        if (
            other_flow.source == SOURCE_INTEGRATION_DISCOVERY
            and other_flow._selected is not None
        ):
            data = {
                **self._selected,
                CONF_IDENTIFIER: other_flow._selected[CONF_IDENTIFIER],
            }
            if data != other_flow._selected:
                other_flow._selected = data
                other_flow.context["title_placeholders"] = {
                    "name": data[CONF_NAME] or data[CONF_IDENTIFIER],
                    "identifier": data[CONF_IDENTIFIER],
                    "host": data[CONF_HOST],
                }
                other_flow.async_notify_flow_changed()
        return True

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Require consent before opening a validation connection."""
        assert self._selected is not None
        self._set_confirm_only()
        errors: dict[str, str] = {}
        if user_input is not None:
            result, error = await self._async_validate_selected()
            if result:
                return result
            errors["base"] = error
        placeholders = {
            "name": self._selected[CONF_NAME] or self._selected[CONF_IDENTIFIER],
            "identifier": self._selected[CONF_IDENTIFIER],
            "host": self._selected[CONF_HOST],
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=placeholders,
            errors=errors,
        )

    async def _async_validate_selected(self) -> tuple[ConfigFlowResult | None, str]:
        """Bind a temporary device and recheck ownership after the await."""
        assert self._selected is not None
        data = self._selected
        identifier = normalize_identifier(data[CONF_IDENTIFIER])
        if identifier in async_get_legacy_identifiers(self.hass):
            return self.async_abort(reason="already_configured"), ""
        if self.source == SOURCE_USER:
            await self.async_set_unique_id(identifier, raise_on_progress=False)
            self._abort_if_unique_id_configured()
        elif result := self._known_device(data):
            return result, ""
        device = Device(
            DeviceInfo(
                ip=data[CONF_HOST],
                port=data[CONF_PORT],
                mac=data[CONF_IDENTIFIER],
                name=data[CONF_NAME],
                brand=data["brand"],
                model=data["model"],
                version=data["version"],
                mid=data["mid"],
            )
        )
        try:
            await async_bind_device(self.hass, device)
        except DeviceNotBoundError, DeviceTimeoutError, OSError, TimeoutError:
            return None, "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception connecting to Gree device")
            return None, "unknown"
        finally:
            device.close()
        # A moved endpoint needs validation again, without rebinding on discovery.
        if any(data[key] != self._selected[key] for key in (CONF_HOST, CONF_PORT)):
            return None, "cannot_connect"
        data = self._selected
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, identifier
        )
        if entry is not None and entry.source != SOURCE_IGNORE:
            return self._known_device(data), ""
        if identifier in async_get_legacy_identifiers(self.hass):
            return self.async_abort(reason="already_configured"), ""
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=data[CONF_NAME] or data[CONF_IDENTIFIER], data=data
        ), ""
