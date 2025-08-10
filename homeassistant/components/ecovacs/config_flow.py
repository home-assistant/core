"""Config flow for Ecovacs mqtt integration."""

from __future__ import annotations

from functools import partial
import logging
import ssl
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientError
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.const import UNDEFINED, UndefinedType
from deebot_client.exceptions import InvalidAuthenticationError, MqttError
from deebot_client.mqtt_client import MqttClient, create_mqtt_config
from deebot_client.util import md5
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_COUNTRY, CONF_MODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, selector
from homeassistant.helpers.typing import VolDictType
from homeassistant.util.ssl import get_default_no_verify_context

from .const import (
    CONF_OVERRIDE_MQTT_URL,
    CONF_OVERRIDE_REST_URL,
    CONF_VERIFY_MQTT_CERTIFICATE,
    DOMAIN,
    InstanceMode,
)
from .util import get_client_device_id

_LOGGER = logging.getLogger(__name__)


def _validate_url(
    value: str,
    field_name: str,
    schema_list: set[str],
) -> dict[str, str]:
    """Validate an URL and return error dictionary."""
    if urlparse(value).scheme not in schema_list:
        return {field_name: f"invalid_url_schema_{field_name}"}
    try:
        vol.Schema(vol.Url())(value)
    except vol.Invalid:
        return {field_name: "invalid_url"}
    return {}


async def _validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str]:
    """Validate user input."""
    errors: dict[str, str] = {}

    if rest_url := user_input.get(CONF_OVERRIDE_REST_URL):
        errors.update(
            _validate_url(rest_url, CONF_OVERRIDE_REST_URL, {"http", "https"})
        )
    if mqtt_url := user_input.get(CONF_OVERRIDE_MQTT_URL):
        errors.update(
            _validate_url(mqtt_url, CONF_OVERRIDE_MQTT_URL, {"mqtt", "mqtts"})
        )

    if errors:
        return errors

    device_id = get_client_device_id(hass, rest_url is not None)
    country = user_input[CONF_COUNTRY]
    rest_config = create_rest_config(
        aiohttp_client.async_get_clientsession(hass),
        device_id=device_id,
        alpha_2_country=country,
        override_rest_url=rest_url,
    )

    authenticator = Authenticator(
        rest_config,
        user_input[CONF_USERNAME],
        md5(user_input[CONF_PASSWORD]),
    )

    try:
        await authenticator.authenticate()
    except ClientError:
        _LOGGER.debug("Cannot connect", exc_info=True)
        errors["base"] = "cannot_connect"
    except InvalidAuthenticationError:
        errors["base"] = "invalid_auth"
    except Exception:
        _LOGGER.exception("Unexpected exception during login")
        errors["base"] = "unknown"

    if errors:
        return errors

    ssl_context: UndefinedType | ssl.SSLContext = UNDEFINED
    if not user_input.get(CONF_VERIFY_MQTT_CERTIFICATE, True) and mqtt_url:
        ssl_context = get_default_no_verify_context()

    mqtt_config = await hass.async_add_executor_job(
        partial(
            create_mqtt_config,
            device_id=device_id,
            country=country,
            override_mqtt_url=mqtt_url,
            ssl_context=ssl_context,
        )
    )

    client = MqttClient(mqtt_config, authenticator)
    cannot_connect_field = CONF_OVERRIDE_MQTT_URL if mqtt_url else "base"

    try:
        await client.verify_config()
    except MqttError:
        _LOGGER.debug("Cannot connect", exc_info=True)
        errors[cannot_connect_field] = "cannot_connect"
    except InvalidAuthenticationError:
        errors["base"] = "invalid_auth"
    except Exception:
        _LOGGER.exception("Unexpected exception during mqtt connection verification")
        errors["base"] = "unknown"

    return errors


class EcovacsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ecovacs."""

    VERSION = 1

    _mode: InstanceMode = InstanceMode.CLOUD

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        if not self.show_advanced_options:
            return await self.async_step_auth()

        if user_input:
            self._mode = user_input[CONF_MODE]
            return await self.async_step_auth()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODE, default=InstanceMode.CLOUD
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(InstanceMode),
                            translation_key="installation_mode",
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            last_step=False,
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the auth step."""
        errors = {}

        if user_input:
            self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})

            errors = await _validate_input(self.hass, user_input)

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        schema: VolDictType = {
            vol.Required(CONF_USERNAME): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(CONF_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_COUNTRY): selector.CountrySelector(),
        }
        if self._mode == InstanceMode.SELF_HOSTED:
            schema.update(
                {
                    vol.Required(CONF_OVERRIDE_REST_URL): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
                    ),
                    vol.Required(CONF_OVERRIDE_MQTT_URL): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
                    ),
                }
            )
            if errors:
                schema[vol.Optional(CONF_VERIFY_MQTT_CERTIFICATE, default=True)] = bool

        if not user_input:
            user_input = {
                CONF_COUNTRY: self.hass.config.country,
            }

        return self.async_show_form(
            step_id="auth",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=vol.Schema(schema), suggested_values=user_input
            ),
            errors=errors,
            last_step=True,
        )
