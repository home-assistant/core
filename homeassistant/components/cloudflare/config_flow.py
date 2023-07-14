"""Config flow for Cloudflare integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pycfdns import CloudflareUpdater
from pycfdns.exceptions import (
    CloudflareAuthenticationException,
    CloudflareConnectionException,
    CloudflareZoneException,
)
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_API_TOKEN, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_RECORDS, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
    }
)


def _zone_schema(zones: list[str] | None = None) -> vol.Schema:
    """Zone selection schema."""
    zones_list = []

    if zones is not None:
        zones_list = zones

    return vol.Schema({vol.Required(CONF_ZONE): vol.In(zones_list)})


def _records_schema(records: list[str] | None = None) -> vol.Schema:
    """Zone records selection schema."""
    records_dict = {}

    if records:
        records_dict = {name: name for name in records}

    return vol.Schema({vol.Required(CONF_RECORDS): cv.multi_select(records_dict)})


async def _validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, list[str] | None]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    zone = data.get(CONF_ZONE)
    records: list[str] | None = None

    cfupdate = CloudflareUpdater(
        async_get_clientsession(hass),
        data[CONF_API_TOKEN],
        zone,
        [],
    )

    try:
        zones: list[str] | None = await cfupdate.get_zones()
        if zone:
            zone_id = await cfupdate.get_zone_id()
            records = await cfupdate.get_zone_records(zone_id, "A")
    except CloudflareConnectionException as error:
        raise CannotConnect from error
    except CloudflareAuthenticationException as error:
        raise InvalidAuth from error
    except CloudflareZoneException as error:
        raise InvalidZone from error

    return {"zones": zones, "records": records}


class CloudflareConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cloudflare."""

    VERSION = 1

    entry: ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize the Cloudflare config flow."""
        self.cloudflare_config: dict[str, Any] = {}
        self.zones: list[str] | None = None
        self.records: list[str] | None = None

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle initiation of re-authentication with Cloudflare."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication with Cloudflare."""
        errors: dict[str, str] = {}

        if user_input is not None and self.entry:
            _, errors = await self._async_validate_or_error(user_input)

            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={
                        **self.entry.data,
                        CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                    },
                )

                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.entry.entry_id)
                )

                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        persistent_notification.async_dismiss(self.hass, "cloudflare_setup")

        errors: dict[str, str] = {}

        if user_input is not None:
            info, errors = await self._async_validate_or_error(user_input)

            if not errors:
                self.cloudflare_config.update(user_input)
                self.zones = info["zones"]
                return await self.async_step_zone()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the picking the zone."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.cloudflare_config.update(user_input)
            info, errors = await self._async_validate_or_error(self.cloudflare_config)

            if not errors:
                await self.async_set_unique_id(user_input[CONF_ZONE])
                self.records = info["records"]

                return await self.async_step_records()

        return self.async_show_form(
            step_id="zone",
            data_schema=_zone_schema(self.zones),
            errors=errors,
        )

    async def async_step_records(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the picking the zone records."""

        if user_input is not None:
            self.cloudflare_config.update(user_input)
            title = self.cloudflare_config[CONF_ZONE]
            return self.async_create_entry(title=title, data=self.cloudflare_config)

        return self.async_show_form(
            step_id="records",
            data_schema=_records_schema(self.records),
        )

    async def _async_validate_or_error(
        self, config: dict[str, Any]
    ) -> tuple[dict[str, list[str] | None], dict[str, str]]:
        errors: dict[str, str] = {}
        info = {}

        try:
            info = await _validate_input(self.hass, config)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except InvalidZone:
            errors["base"] = "invalid_zone"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return info, errors


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidZone(HomeAssistantError):
    """Error to indicate we cannot validate zone exists in account."""
