"""Config flow for AirTouch 3 Air Conditioner integration."""

from dataclasses import dataclass
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DEFAULT_NAME, DISCOVERY_TIMEOUT, DOMAIN
from .coordinator import async_fetch_airtouch_data
from .discovery import AirTouch3Discovery, async_discover_devices

_LOGGER = logging.getLogger(__name__)


def _host_schema(
    default_host: Any = vol.UNDEFINED, *, required: bool = True
) -> vol.Schema:
    """Return the host form schema."""
    marker = vol.Required if required else vol.Optional
    return vol.Schema({marker(CONF_HOST, default=default_host): str})


STEP_USER_DATA_SCHEMA = _host_schema("", required=False)


async def validate_input(_hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    host = data[CONF_HOST]
    _LOGGER.debug("Validating AirTouch 3 controller at %s", host)
    try:
        aircon = await async_fetch_airtouch_data(host)
    except UpdateFailed as err:
        _LOGGER.debug("Unable to validate AirTouch 3 controller at %s: %s", host, err)
        raise CannotConnect from err

    if not aircon.system_id:
        _LOGGER.debug("AirTouch 3 controller at %s did not return a system id", host)
        raise CannotConnect

    _LOGGER.debug(
        "Validated AirTouch 3 controller at %s with system id %s",
        host,
        aircon.system_id,
    )
    return {"title": DEFAULT_NAME, "unique_id": aircon.system_id}


@dataclass(slots=True)
class AirTouch3ValidatedDevice:
    """Validated discovered AirTouch 3 controller."""

    host: str
    unique_id: str
    title: str
    mac: str | None = None


class AirTouch3ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AirTouch 3 Air Conditioner."""

    VERSION = 1
    _discovered_device: AirTouch3ValidatedDevice

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, AirTouch3ValidatedDevice] = {}

    def _async_configured_entry(
        self, unique_id: str, host: str
    ) -> config_entries.ConfigEntry | None:
        """Return an existing config entry matching a controller id or host."""
        for entry in self._async_current_entries(include_ignore=True):
            if entry.unique_id == unique_id or entry.data.get(CONF_HOST) == host:
                return entry
        return None

    async def _async_set_unique_id_or_abort(
        self, unique_id: str, host: str, *, raise_on_progress: bool = True
    ) -> None:
        """Set the flow unique id and abort if this controller is configured."""
        if entry := self._async_configured_entry(unique_id, host):
            updates: dict[str, Any] = {}
            if not entry.unique_id:
                updates["unique_id"] = unique_id
            if entry.unique_id == unique_id and entry.data.get(CONF_HOST) != host:
                updates["data"] = {**entry.data, CONF_HOST: host}
            if updates:
                self.hass.config_entries.async_update_entry(entry, **updates)
            raise AbortFlow("already_configured")

        await self.async_set_unique_id(unique_id, raise_on_progress=raise_on_progress)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

    async def _async_validate_host(self, host: str) -> AirTouch3ValidatedDevice:
        """Validate an AirTouch 3 controller host."""
        info = await validate_input(self.hass, {CONF_HOST: host})
        return AirTouch3ValidatedDevice(
            host=host, unique_id=info["unique_id"], title=info["title"]
        )

    async def _async_validate_discovery(
        self, discovery: AirTouch3Discovery
    ) -> AirTouch3ValidatedDevice | None:
        """Validate a discovery result and return a flow device."""
        _LOGGER.debug(
            "Validating discovered AirTouch 3 controller at %s (mac=%s, model=%s)",
            discovery.host,
            discovery.mac,
            discovery.model,
        )
        try:
            device = await self._async_validate_host(discovery.host)
        except CannotConnect as err:
            _LOGGER.debug(
                "Discovered AirTouch 3 controller at %s failed validation: %s",
                discovery.host,
                err,
            )
            return None
        device.mac = discovery.mac
        _LOGGER.debug(
            "Discovered AirTouch 3 controller at %s validated as system id %s",
            discovery.host,
            device.unique_id,
        )
        return device

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = {
                **user_input,
                CONF_HOST: user_input.get(CONF_HOST, "").strip(),
            }
            if not user_input[CONF_HOST]:
                _LOGGER.debug(
                    "AirTouch 3 host was left empty; starting local discovery"
                )
                return await self.async_step_pick_device()

            try:
                device = await self._async_validate_host(user_input[CONF_HOST])
                await self._async_set_unique_id_or_abort(
                    device.unique_id, device.host, raise_on_progress=False
                )
            except AbortFlow:
                raise
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=device.title, data={CONF_HOST: device.host}
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to pick a discovered controller."""
        if user_input is not None:
            selected_device = self._discovered_devices[user_input[CONF_DEVICE]]
            _LOGGER.debug(
                "User selected discovered AirTouch 3 controller %s at %s",
                selected_device.unique_id,
                selected_device.host,
            )
            await self._async_set_unique_id_or_abort(
                selected_device.unique_id,
                selected_device.host,
                raise_on_progress=False,
            )
            return self.async_create_entry(
                title=selected_device.title, data={CONF_HOST: selected_device.host}
            )

        discovered_devices = await async_discover_devices(self.hass, DISCOVERY_TIMEOUT)
        _LOGGER.debug(
            "AirTouch 3 discovery returned %s raw controller(s)",
            len(discovered_devices),
        )
        self._discovered_devices = {}
        for discovery in discovered_devices:
            discovered_device = await self._async_validate_discovery(discovery)
            if discovered_device is None:
                continue
            if self._async_configured_entry(
                discovered_device.unique_id, discovered_device.host
            ):
                _LOGGER.debug(
                    "Skipping discovered AirTouch 3 controller %s at %s because it "
                    "is already configured",
                    discovered_device.unique_id,
                    discovered_device.host,
                )
                continue
            self._discovered_devices[discovered_device.unique_id] = discovered_device

        if not self._discovered_devices:
            _LOGGER.debug("No unconfigured AirTouch 3 controllers were discovered")
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "no_devices_found"},
            )

        _LOGGER.debug(
            "Presenting %s discovered AirTouch 3 controller(s) for selection",
            len(self._discovered_devices),
        )
        devices_name = {
            unique_id: f"{device.title} {unique_id} ({device.host})"
            for unique_id, device in self._discovered_devices.items()
        }
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_name)}),
        )

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, str]
    ) -> ConfigFlowResult:
        """Handle discovery from the AirTouch 3 local discovery scan."""
        discovery = AirTouch3Discovery(**discovery_info)
        _LOGGER.debug(
            "Handling AirTouch 3 integration discovery for %s (mac=%s, model=%s)",
            discovery.host,
            discovery.mac,
            discovery.model,
        )
        try:
            device = await self._async_validate_discovery(discovery)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")

        if device is None:
            return self.async_abort(reason="cannot_connect")

        self._discovered_device = device
        await self._async_set_unique_id_or_abort(
            self._discovered_device.unique_id, self._discovered_device.host
        )

        return await self.async_step_discovery_confirm()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle AirTouch 3 DHCP discovery."""
        _LOGGER.debug(
            "Handling AirTouch 3 DHCP discovery for %s (hostname=%s, mac=%s)",
            discovery_info.ip,
            discovery_info.hostname,
            discovery_info.macaddress,
        )

        try:
            device = await self._async_validate_host(discovery_info.ip)
        except CannotConnect:
            _LOGGER.debug(
                "DHCP-discovered host %s did not validate as AirTouch 3",
                discovery_info.ip,
            )
            return self.async_abort(reason="cannot_connect")

        device.mac = discovery_info.macaddress
        self._discovered_device = device
        await self._async_set_unique_id_or_abort(device.unique_id, device.host)

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered controller."""
        device = self._discovered_device
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            _LOGGER.debug(
                "Creating AirTouch 3 entry for discovered controller %s at %s",
                device.unique_id,
                device.host,
            )
            return self.async_create_entry(
                title=device.title, data={CONF_HOST: device.host}
            )

        self._set_confirm_only()
        placeholders = {"host": device.host, "system_id": device.unique_id}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
