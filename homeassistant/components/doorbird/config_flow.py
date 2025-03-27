"""Config flow for DoorBird integration."""

from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientResponseError
from doorbirdpy import DoorBird
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.helpers.typing import VolDictType

from .const import (
    CONF_EVENTS,
    DEFAULT_DOORBELL_EVENT,
    DEFAULT_MOTION_EVENT,
    DOMAIN,
    DOORBIRD_OUI,
)
from .util import get_mac_address_from_door_station_info

_LOGGER = logging.getLogger(__name__)

DEFAULT_OPTIONS = {CONF_EVENTS: [DEFAULT_DOORBELL_EVENT, DEFAULT_MOTION_EVENT]}


AUTH_VOL_DICT: VolDictType = {
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
}
AUTH_SCHEMA = vol.Schema(AUTH_VOL_DICT)


def _schema_with_defaults(
    host: str | None = None, name: str | None = None
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            **AUTH_VOL_DICT,
            vol.Optional(CONF_NAME, default=name): str,
        }
    )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    device = DoorBird(
        data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD], http_session=session
    )
    try:
        info = await device.info()
    except ClientResponseError as err:
        if err.status == HTTPStatus.UNAUTHORIZED:
            raise InvalidAuth from err
        raise CannotConnect from err
    except OSError as err:
        raise CannotConnect from err

    mac_addr = get_mac_address_from_door_station_info(info)

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_HOST], "mac_addr": mac_addr}


async def async_verify_supported_device(hass: HomeAssistant, host: str) -> bool:
    """Verify the doorbell state endpoint returns a 401."""
    session = async_get_clientsession(hass)
    device = DoorBird(host, "", "", http_session=session)
    try:
        await device.doorbell_state()
    except ClientResponseError as err:
        if err.status == HTTPStatus.UNAUTHORIZED:
            return True
    except OSError:
        return False
    return False


class DoorBirdConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DoorBird."""

    VERSION = 1

    reauth_entry: ConfigEntry

    def __init__(self) -> None:
        """Initialize the DoorBird config flow."""
        self.discovery_schema: vol.Schema | None = None

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth."""
        self.reauth_entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth input."""
        errors: dict[str, str] = {}
        existing_data = self.reauth_entry.data
        placeholders: dict[str, str] = {
            CONF_NAME: existing_data[CONF_NAME],
            CONF_HOST: existing_data[CONF_HOST],
        }
        self.context["title_placeholders"] = placeholders
        if user_input is not None:
            new_config = {
                **existing_data,
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            _, errors = await self._async_validate_or_error(new_config)
            if not errors:
                return self.async_update_reload_and_abort(
                    self.reauth_entry, data=new_config
                )

        return self.async_show_form(
            description_placeholders=placeholders,
            step_id="reauth_confirm",
            data_schema=AUTH_SCHEMA,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            info, errors = await self._async_validate_or_error(user_input)
            if not errors:
                await self.async_set_unique_id(info["mac_addr"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["title"], data=user_input, options=DEFAULT_OPTIONS
                )

        data = self.discovery_schema or _schema_with_defaults()
        return self.async_show_form(step_id="user", data_schema=data, errors=errors)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a discovered doorbird device."""
        macaddress = discovery_info.properties["macaddress"]

        if macaddress[:6] != DOORBIRD_OUI:
            return self.async_abort(reason="not_doorbird_device")
        if discovery_info.ip_address.is_link_local:
            return self.async_abort(reason="link_local_address")
        if discovery_info.ip_address.version != 4:
            return self.async_abort(reason="not_ipv4_address")

        await self.async_set_unique_id(macaddress)
        host = discovery_info.host
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._async_abort_entries_match({CONF_HOST: host})

        if not await async_verify_supported_device(self.hass, host):
            return self.async_abort(reason="not_doorbird_device")

        chop_ending = "._axis-video._tcp.local."
        friendly_hostname = discovery_info.name.removesuffix(chop_ending)

        self.context["title_placeholders"] = {
            CONF_NAME: friendly_hostname,
            CONF_HOST: host,
        }
        self.discovery_schema = _schema_with_defaults(host=host, name=friendly_hostname)

        return await self.async_step_user()

    async def _async_validate_or_error(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Validate doorbird or error."""
        errors = {}
        info = {}
        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return info, errors

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handle a option flow for doorbird."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            events = [event.strip() for event in user_input[CONF_EVENTS].split(",")]
            return self.async_create_entry(title="", data={CONF_EVENTS: events})

        current_events = self.config_entry.options.get(CONF_EVENTS, [])

        # We convert to a comma separated list for the UI
        # since there really isn't anything better
        options_schema = vol.Schema(
            {vol.Optional(CONF_EVENTS, default=", ".join(current_events)): str}
        )
        return self.async_show_form(step_id="init", data_schema=options_schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
