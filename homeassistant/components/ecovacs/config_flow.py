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

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_COUNTRY, CONF_MODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, selector
from homeassistant.helpers.typing import VolDictType
from homeassistant.util.ssl import get_default_no_verify_context

from .const import (
    CONF_CAMERA_PINS,
    CONF_OVERRIDE_MQTT_URL,
    CONF_OVERRIDE_REST_URL,
    CONF_VERIFY_MQTT_CERTIFICATE,
    DOMAIN,
    InstanceMode,
)
from .kvs_api import encode_pin
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

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return EcovacsOptionsFlowHandler()

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


def _device_pin_field_key(device_info: dict) -> str:
    """Return a unique schema field key for a device PIN input.

    Format: "Name [full-did] (PIN camera)" — the full DID guarantees
    uniqueness even when two devices share the same display name.
    """
    label = (
        device_info.get("nick")
        or device_info.get("deviceName")
        or device_info.get("name")
        or ""
    )
    did = device_info["did"]
    base = f"{label} [{did}]" if label else did
    return f"{base} (PIN camera)"


class EcovacsOptionsFlowHandler(OptionsFlow):
    """Handle Ecovacs options — camera PIN per device."""

    # Sentinel shown in the PIN field when a PIN is already configured.
    # If the user submits this value unchanged, the existing PIN is preserved.
    _PIN_ALREADY_SET = "••••••••"

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Entry point: delegate to the camera_pins step."""
        return await self.async_step_camera_pins(user_input)

    async def async_step_camera_pins(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage camera PIN options."""
        controller = self.config_entry.runtime_data
        devices = controller.devices
        current_pins: dict[str, str] = self.config_entry.options.get(
            CONF_CAMERA_PINS, {}
        )

        # Build a stable mapping: display_key → did.
        key_to_did: dict[str, str] = {
            _device_pin_field_key(d.device_info): d.device_info["did"] for d in devices
        }

        if user_input is not None:
            errors: dict[str, str] = {}
            new_pins: dict[str, str] = {}
            for field_key, did in key_to_did.items():
                raw_pin = (user_input.get(field_key) or "").strip()
                if raw_pin and raw_pin != self._PIN_ALREADY_SET:
                    if not raw_pin.isdigit():
                        errors[field_key] = "invalid_camera_pin"
                        continue
                    new_pins[did] = encode_pin(raw_pin)
                elif did in current_pins:
                    new_pins[did] = current_pins[did]

            if errors:
                pass  # fall through to schema building below
            else:
                return self.async_create_entry(
                    data={CONF_CAMERA_PINS: new_pins},
                )

        schema: dict[Any, Any] = {}
        for field_key, did in key_to_did.items():
            # Pre-fill with sentinel when a PIN is already configured so the
            # user can see that a PIN is set and does not accidentally clear it.
            suggested = self._PIN_ALREADY_SET if did in current_pins else ""
            schema[
                vol.Optional(
                    field_key,
                    description={"suggested_value": suggested},
                )
            ] = selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.PASSWORD,
                )
            )

        return self.async_show_form(
            step_id="camera_pins",
            data_schema=vol.Schema(schema),
            errors=errors if user_input is not None else {},
        )
