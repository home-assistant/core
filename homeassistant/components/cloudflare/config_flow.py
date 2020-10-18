"""Config flow for Cloudflare integration."""
import logging
from typing import Dict, List, Optional

from pycfdns import CloudflareUpdater
from pycfdns.exceptions import (
    CloudflareAuthenticationException,
    CloudflareConnectionException,
    CloudflareZoneException,
)
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import CONN_CLASS_CLOUD_PUSH, ConfigFlow
from homeassistant.const import CONF_API_TOKEN, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_RECORDS
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
    }
)


def _zone_schema(zones: Optional[List] = None):
    """Zone selection schema."""
    zones_list = []

    if zones is not None:
        zones_list = zones

    return vol.Schema({vol.Required(CONF_ZONE): vol.In(zones_list)})


def _records_schema(records: Optional[List] = None):
    """Zone records selection schema."""
    records_dict = {}

    if records:
        records_dict = {name: name for name in records}

    return vol.Schema({vol.Required(CONF_RECORDS): cv.multi_select(records_dict)})


async def validate_input(hass: HomeAssistant, data: Dict):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    zone = data.get(CONF_ZONE)
    records = None

    cfupdate = CloudflareUpdater(
        async_get_clientsession(hass),
        data[CONF_API_TOKEN],
        zone,
        [],
    )

    try:
        zones = await cfupdate.get_zones()
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
    CONNECTION_CLASS = CONN_CLASS_CLOUD_PUSH

    def __init__(self):
        """Initialize the Cloudflare config flow."""
        self.cloudflare_config = {}
        self.zones = None
        self.records = None

    async def async_step_user(self, user_input: Optional[Dict] = None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        assert self.hass
        persistent_notification.async_dismiss(self.hass, "cloudflare_setup")

        errors = {}

        if user_input is not None:
            info, errors = await self._async_validate_or_error(user_input)

            if not errors:
                self.cloudflare_config.update(user_input)
                self.zones = info["zones"]
                return await self.async_step_zone()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_zone(self, user_input: Optional[Dict] = None):
        """Handle the picking the zone."""
        errors = {}

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

    async def async_step_records(self, user_input: Optional[Dict] = None):
        """Handle the picking the zone records."""
        errors = {}

        if user_input is not None:
            self.cloudflare_config.update(user_input)
            title = self.cloudflare_config[CONF_ZONE]
            return self.async_create_entry(title=title, data=self.cloudflare_config)

        return self.async_show_form(
            step_id="records",
            data_schema=_records_schema(self.records),
            errors=errors,
        )

    async def _async_validate_or_error(self, config):
        errors = {}
        info = {}

        try:
            info = await validate_input(self.hass, config)
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
