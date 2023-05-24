"""Config flow for the Bang & Olufsen integration."""
from __future__ import annotations

import ipaddress
from typing import Any, TypedDict, cast

from mozart_api.exceptions import ApiException
from mozart_api.mozart_client import MozartClient
from urllib3.exceptions import MaxRetryError, NewConnectionError
import voluptuous as vol

from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    API_EXCEPTION,
    ATTR_FRIENDLY_NAME,
    ATTR_ITEM_NUMBER,
    ATTR_SERIAL_NUMBER,
    ATTR_TYPE_NUMBER,
    COMPATIBLE_MODELS,
    CONF_BEOLINK_JID,
    CONF_DEFAULT_VOLUME,
    CONF_MAX_VOLUME,
    CONF_SERIAL_NUMBER,
    CONF_VOLUME_STEP,
    DEFAULT_DEFAULT_VOLUME,
    DEFAULT_HOST,
    DEFAULT_MAX_VOLUME,
    DEFAULT_MODEL,
    DEFAULT_VOLUME_RANGE,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
    MAX_RETRY_ERROR,
    MAX_VOLUME_RANGE,
    NEW_CONNECTION_ERROR,
    NOT_MOZART_DEVICE,
    VALUE_ERROR,
    VOLUME_STEP_RANGE,
)


def _config_schema(
    volume_step: int = DEFAULT_VOLUME_STEP,
    default_volume: int = DEFAULT_DEFAULT_VOLUME,
    max_volume: int = DEFAULT_MAX_VOLUME,
) -> dict:
    """Create a schema for configuring the device with adjustable default values."""
    return {
        vol.Required(CONF_VOLUME_STEP, default=volume_step): vol.All(
            vol.Coerce(int),
            vol.Range(
                min=VOLUME_STEP_RANGE.start,
                max=(VOLUME_STEP_RANGE.stop - 1),
            ),
        ),
        vol.Required(CONF_DEFAULT_VOLUME, default=default_volume): vol.All(
            vol.Coerce(int),
            vol.Range(
                min=DEFAULT_VOLUME_RANGE.start,
                max=(DEFAULT_VOLUME_RANGE.stop - 1),
            ),
        ),
        vol.Required(CONF_MAX_VOLUME, default=max_volume): vol.All(
            vol.Coerce(int),
            vol.Range(
                min=MAX_VOLUME_RANGE.start,
                max=(MAX_VOLUME_RANGE.stop - 1),
            ),
        ),
    }


class UserInput(TypedDict):
    """TypedDict for user_input."""

    name: str
    volume_step: int
    default_volume: int
    max_volume: int
    host: str
    model: str
    jid: str


class BangOlufsenConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    def __init__(self) -> None:
        """Init the config flow."""
        self._host: str = ""
        self._name: str = ""
        self._model: str = ""
        self._serial_number: str = ""
        self._beolink_jid: str = ""

        self._client: MozartClient | None = None

    VERSION = 1

    async def _validate_host(self) -> None:
        """Validate that a connection can be made to the device and set jid and serial number."""
        try:
            # Check if the IP address is a valid address.
            ipaddress.ip_address(self._host)

            self._client = MozartClient(self._host)

            # Get information from Beolink self method.
            beolink_self = self._client.get_beolink_self(
                async_req=True, _request_timeout=3
            ).get()

            self._beolink_jid = beolink_self.jid
            self._serial_number = beolink_self.jid.split(".")[2].split("@")[0]

        except ApiException as error:
            raise AbortFlow(reason=API_EXCEPTION) from error

        except NewConnectionError as error:
            raise AbortFlow(reason=NEW_CONNECTION_ERROR) from error

        except MaxRetryError as error:
            raise AbortFlow(reason=MAX_RETRY_ERROR) from error

        except ValueError as error:
            raise AbortFlow(reason=VALUE_ERROR) from error

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._model = user_input[CONF_MODEL]
            await self._validate_host()

            self._name = f"{self._model}-{self._serial_number}"

            await self.async_set_unique_id(self._serial_number)
            self._abort_if_unique_id_configured()

            return await self.async_step_confirm()

        data_schema = {
            vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
            vol.Required(CONF_MODEL, default=DEFAULT_MODEL): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=COMPATIBLE_MODELS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle discovery using Zeroconf."""

        # Check if the discovered device is a Mozart device
        if ATTR_FRIENDLY_NAME not in discovery_info.properties:
            return self.async_abort(reason=NOT_MOZART_DEVICE)

        self._host = discovery_info.host
        self._model = discovery_info.hostname[:-16].replace("-", " ")
        self._serial_number = discovery_info.properties[ATTR_SERIAL_NUMBER]
        self._beolink_jid = f"{discovery_info.properties[ATTR_TYPE_NUMBER]}.{discovery_info.properties[ATTR_ITEM_NUMBER]}.{self._serial_number}@products.bang-olufsen.com"
        self._name = f"{self._model}-{self._serial_number}"

        self._client = MozartClient(self._host)

        self.context["title_placeholders"] = {
            "name": discovery_info.properties[ATTR_FRIENDLY_NAME]
        }

        await self.async_set_unique_id(self._serial_number)
        self._abort_if_unique_id_configured()

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: UserInput | None = None
    ) -> FlowResult:
        """Confirm the configuration of the device."""
        if user_input is not None:
            # Make sure that all information is included
            data = user_input
            data[CONF_HOST] = self._host
            data[CONF_MODEL] = self._model
            data[CONF_BEOLINK_JID] = self._beolink_jid
            data[CONF_NAME] = self._name

            return self.async_create_entry(
                title=self._name,
                data=data,
            )

        volume_settings = (
            cast(MozartClient, self._client).get_volume_settings(async_req=True).get()
        )

        data_schema = _config_schema(
            default_volume=volume_settings.default.level,
            max_volume=volume_settings.maximum.level,
        )

        self._set_confirm_only()

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(data_schema),
            description_placeholders={
                CONF_HOST: self._host,
                CONF_MODEL: self._model,
                CONF_SERIAL_NUMBER: self._serial_number,
            },
            last_step=True,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow handler."""
        return BangOlufsenOptionsFlowHandler(config_entry)


class BangOlufsenOptionsFlowHandler(OptionsFlow):
    """Handle an options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow handler."""
        self._client: MozartClient = MozartClient(host=config_entry.data[CONF_HOST])
        self._config_entry: ConfigEntry = config_entry

    async def async_step_init(self, user_input: UserInput | None = None) -> FlowResult:
        """Manage the options menu."""
        if user_input is not None:
            # Make sure that everything get included in the data.
            data = user_input
            data[CONF_MODEL] = self._config_entry.data[CONF_MODEL]
            data[CONF_BEOLINK_JID] = self._config_entry.data[CONF_BEOLINK_JID]
            data[CONF_HOST] = self._config_entry.data[CONF_HOST]

            # Check connection
            return self.async_create_entry(title=data[CONF_NAME], data=data)

        # Create data schema with the current volume options, not necessarily the ones set in Home Assistant.
        # Also add the ability to change the friendly name in Home Assistant
        volume_settings = self._client.get_volume_settings(async_req=True).get()

        data_schema = {
            vol.Optional(
                CONF_NAME, default=self._config_entry.data[CONF_NAME]
            ): cv.string,
        }
        data_schema.update(
            _config_schema(
                volume_step=self._config_entry.data[CONF_VOLUME_STEP],
                default_volume=volume_settings.default.level,
                max_volume=volume_settings.maximum.level,
            )
        )

        # Create options form with selected options.
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(data_schema),
            last_step=True,
        )
