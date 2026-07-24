"""Config flow for AirTouch 3 Air Conditioner integration."""

from dataclasses import dataclass
import logging
from typing import Any, override

from pyairtouch3 import DEFAULT_PORT, AirTouchClient, AirTouchError
import voluptuous as vol

from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


async def validate_input(_hass: HomeAssistant, data: dict[str, Any]) -> str:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    host = data[CONF_HOST]
    _LOGGER.debug("Validating AirTouch 3 controller at %s", host)
    try:
        aircon = await AirTouchClient(host, DEFAULT_PORT, logger=_LOGGER).fetch_aircon()
    except AirTouchError as err:
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
    return aircon.system_id


@dataclass(slots=True)
class AirTouch3ValidatedDevice:
    """Validated discovered AirTouch 3 controller."""

    host: str
    unique_id: str
    title: str


class AirTouch3ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AirTouch 3 Air Conditioner."""

    VERSION = 1
    _discovered_device: AirTouch3ValidatedDevice

    async def _async_set_unique_id_or_abort(
        self, unique_id: str, host: str, *, raise_on_progress: bool = True
    ) -> None:
        """Set the flow unique id and abort if this controller is configured."""
        await self.async_set_unique_id(unique_id, raise_on_progress=raise_on_progress)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

    async def _async_validate_host(self, host: str) -> AirTouch3ValidatedDevice:
        """Validate an AirTouch 3 controller host."""
        unique_id = await validate_input(self.hass, {CONF_HOST: host})
        return AirTouch3ValidatedDevice(
            host=host, unique_id=unique_id, title=DEFAULT_NAME
        )

    @override
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
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors=errors,
                )

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

    @override
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
