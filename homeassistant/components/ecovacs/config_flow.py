"""Config flow for Ecovacs mqtt integration."""

from collections.abc import Mapping
from functools import partial
import logging
import ssl
from typing import Any, override
from urllib.parse import urlparse

from aiohttp import ClientError
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.const import UNDEFINED, UndefinedType
from deebot_client.exceptions import (
    DeviceVerificationRequiredError,
    InvalidAuthenticationError,
    InvalidVerificationCodeError,
    MqttError,
)
from deebot_client.mqtt_client import MqttClient, create_mqtt_config
from deebot_client.util import md5
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_COUNTRY,
    CONF_DEVICE_ID,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
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
    hass: HomeAssistant, user_input: dict[str, Any], device_id: str
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
    except DeviceVerificationRequiredError:
        raise
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
    _pending_input: dict[str, Any]
    _verification_authenticator: Authenticator
    _verification_device_id: str
    _reauth = False

    def _create_authenticator(
        self, user_input: dict[str, Any], device_id: str
    ) -> Authenticator:
        """Create an authenticator for a stable client device ID."""
        return Authenticator(
            create_rest_config(
                aiohttp_client.async_get_clientsession(self.hass),
                device_id=device_id,
                alpha_2_country=user_input[CONF_COUNTRY],
                override_rest_url=user_input.get(CONF_OVERRIDE_REST_URL),
            ),
            user_input[CONF_USERNAME],
            md5(user_input[CONF_PASSWORD]),
        )

    async def _async_validate_or_verify(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, str], ConfigFlowResult | None]:
        """Validate credentials, starting device verification when required."""
        self_hosted = CONF_OVERRIDE_REST_URL in user_input
        device_id = get_client_device_id(
            self.hass, self_hosted, user_input.get(CONF_DEVICE_ID)
        )
        try:
            errors = await _validate_input(self.hass, user_input, device_id)
        except DeviceVerificationRequiredError:
            self._pending_input = user_input
            self._verification_device_id = device_id
            self._verification_authenticator = self._create_authenticator(
                user_input, device_id
            )
            try:
                await (
                    self._verification_authenticator.request_device_verification_code()
                )
            except ClientError:
                _LOGGER.debug("Cannot request Ecovacs verification code", exc_info=True)
                return {"base": "cannot_connect"}, None
            except Exception:
                _LOGGER.exception("Unexpected exception requesting verification code")
                return {"base": "unknown"}, None
            return {}, await self.async_step_device_verification()

        if not errors and not self_hosted:
            user_input[CONF_DEVICE_ID] = device_id
        return errors, None

    async def _async_finish_device_verification(self) -> ConfigFlowResult:
        """Validate the connection after device verification succeeds."""
        errors = await _validate_input(
            self.hass,
            self._pending_input,
            self._verification_device_id,
        )
        if errors:
            return self.async_show_form(
                step_id="device_validation",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        data = self._pending_input | {CONF_DEVICE_ID: self._verification_device_id}
        if self._reauth:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=data
            )
        return self.async_create_entry(
            title=data[CONF_USERNAME],
            data=data,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
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
        errors: dict[str, str] = {}

        if user_input:
            self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})

            errors, result = await self._async_validate_or_verify(user_input)
            if result is not None:
                return result

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

    async def async_step_device_verification(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Verify the stable Ecovacs client device ID."""
        errors: dict[str, str] = {}
        if user_input:
            try:
                await self._verification_authenticator.verify_device(
                    user_input["verification_code"]
                )
            except InvalidVerificationCodeError:
                errors["base"] = "invalid_verification_code"
            except ClientError:
                _LOGGER.debug("Cannot verify Ecovacs device", exc_info=True)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception verifying Ecovacs device")
                errors["base"] = "unknown"
            else:
                await self._verification_authenticator.teardown()
                return await self._async_finish_device_verification()

        return self.async_show_form(
            step_id="device_verification",
            data_schema=vol.Schema(
                {
                    vol.Required("verification_code"): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_device_validation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Retry connection validation without reusing a verification code."""
        if user_input is not None:
            return await self._async_finish_device_verification()
        return self.async_show_form(
            step_id="device_validation",
            data_schema=vol.Schema({}),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        self._reauth = True
        self._pending_input = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm credentials and verify a new device ID if required."""
        errors: dict[str, str] = {}
        if user_input:
            data = self._pending_input | {CONF_PASSWORD: user_input[CONF_PASSWORD]}
            errors, result = await self._async_validate_or_verify(data)
            if result is not None:
                return result
            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=data
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    )
                }
            ),
            errors=errors,
        )
