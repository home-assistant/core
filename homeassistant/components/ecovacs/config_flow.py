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

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_COUNTRY,
    CONF_DEVICE_ID,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client, selector
from homeassistant.helpers.typing import VolDictType
from homeassistant.util.ssl import get_default_no_verify_context

from .const import (
    CONF_OVERRIDE_MQTT_URL,
    CONF_OVERRIDE_REST_URL,
    CONF_VERIFICATION_CODE,
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
    hass: HomeAssistant,
    user_input: dict[str, Any],
    device_id: str,
    authenticator: Authenticator,
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

    try:
        await authenticator.authenticate()
    except DeviceVerificationRequiredError:
        # Handled by the caller, which starts the device verification step
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

    return await _validate_mqtt(hass, user_input, device_id, authenticator)


async def _validate_mqtt(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    device_id: str,
    authenticator: Authenticator,
) -> dict[str, str]:
    """Validate the MQTT connection."""
    errors: dict[str, str] = {}
    country = user_input[CONF_COUNTRY]
    mqtt_url = user_input.get(CONF_OVERRIDE_MQTT_URL)
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
    MINOR_VERSION = 2

    _mode: InstanceMode = InstanceMode.CLOUD
    _input: dict[str, Any]
    _authenticator: Authenticator | None = None
    _device_id: str

    async def _async_set_input(self, user_input: dict[str, Any]) -> Authenticator:
        """Set the input and create its authenticator."""
        await self._async_teardown_authenticator()
        self._input = user_input
        self_hosted = CONF_OVERRIDE_REST_URL in user_input
        self._device_id = get_client_device_id(self.hass, self_hosted, user_input)
        self._authenticator = Authenticator(
            create_rest_config(
                aiohttp_client.async_get_clientsession(self.hass),
                device_id=self._device_id,
                alpha_2_country=user_input[CONF_COUNTRY],
                override_rest_url=user_input.get(CONF_OVERRIDE_REST_URL),
            ),
            user_input[CONF_USERNAME],
            md5(user_input[CONF_PASSWORD]),
        )
        return self._authenticator

    async def _async_teardown_authenticator(self) -> None:
        """Tear down the authenticator to cancel its token refresh timer."""
        if self._authenticator is not None:
            await self._authenticator.teardown()
            self._authenticator = None

    @callback
    @override
    def async_remove(self) -> None:
        """Handle flow removal - tear down the authenticator."""
        super().async_remove()
        if self._authenticator is not None:
            self.hass.async_create_background_task(
                self._async_teardown_authenticator(),
                name="ecovacs_config_flow_authenticator_teardown",
            )

    async def _async_request_device_verification_code(
        self, authenticator: Authenticator
    ) -> dict[str, str]:
        """Request a device verification code."""
        try:
            await authenticator.request_device_verification_code()
        except ClientError:
            _LOGGER.debug("Cannot request Ecovacs verification code", exc_info=True)
            return {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected exception requesting verification code")
            return {"base": "unknown"}
        return {}

    def _finish_flow(self) -> ConfigFlowResult:
        """Create or update the config entry."""
        self._input[CONF_DEVICE_ID] = self._device_id
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=self._input
            )
        return self.async_create_entry(
            title=self._input[CONF_USERNAME],
            data=self._input,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        self._input = {}
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

    def _show_auth_form(
        self,
        user_input: dict[str, Any] | None,
        errors: dict[str, str],
    ) -> ConfigFlowResult:
        """Show the authentication form."""
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

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the auth step."""
        errors: dict[str, str] = {}

        if user_input:
            self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})
            if CONF_DEVICE_ID in self._input and CONF_DEVICE_ID not in user_input:
                user_input[CONF_DEVICE_ID] = self._input[CONF_DEVICE_ID]
            authenticator = await self._async_set_input(user_input)
            try:
                errors = await _validate_input(
                    self.hass,
                    self._input,
                    self._device_id,
                    authenticator,
                )
            except DeviceVerificationRequiredError:
                errors = await self._async_request_device_verification_code(
                    authenticator
                )
                if not errors:
                    return await self.async_step_device_verification()
            if not errors:
                return self._finish_flow()

        return self._show_auth_form(user_input, errors)

    async def async_step_device_verification(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Verify the stable Ecovacs client device ID."""
        errors: dict[str, str] = {}
        # The authenticator is created by the step asking for the credentials
        if user_input and (authenticator := self._authenticator):
            try:
                await authenticator.verify_device(user_input[CONF_VERIFICATION_CODE])
            except InvalidVerificationCodeError:
                errors["base"] = "invalid_verification_code"
            except ClientError:
                _LOGGER.debug("Cannot verify Ecovacs device", exc_info=True)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception verifying Ecovacs device")
                errors["base"] = "unknown"
            else:
                # Keep the verified device ID, so a retry needs no new code
                self._input[CONF_DEVICE_ID] = self._device_id
                errors = await _validate_mqtt(
                    self.hass,
                    self._input,
                    self._device_id,
                    authenticator,
                )
                if not errors:
                    return self._finish_flow()
                if self.source == SOURCE_REAUTH:
                    return self._show_reauth_form(user_input=None, errors=errors)
                return self._show_auth_form(self._input, errors)

        return self.async_show_form(
            step_id="device_verification",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_VERIFICATION_CODE): selector.TextSelector(
                            selector.TextSelectorConfig(
                                type=selector.TextSelectorType.TEXT
                            )
                        )
                    }
                ),
                suggested_values=user_input,
            ),
            description_placeholders={CONF_USERNAME: self._input[CONF_USERNAME]},
            errors=errors,
        )

    def _show_reauth_form(
        self,
        user_input: dict[str, Any] | None,
        errors: dict[str, str],
    ) -> ConfigFlowResult:
        """Show the reauthentication form."""
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_PASSWORD): selector.TextSelector(
                            selector.TextSelectorConfig(
                                type=selector.TextSelectorType.PASSWORD
                            )
                        )
                    }
                ),
                suggested_values=user_input,
            ),
            description_placeholders={CONF_USERNAME: self._input[CONF_USERNAME]},
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        self._input = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm credentials and verify a new device ID if required."""
        errors: dict[str, str] = {}
        if user_input:
            authenticator = await self._async_set_input(self._input | user_input)
            try:
                errors = await _validate_input(
                    self.hass,
                    self._input,
                    self._device_id,
                    authenticator,
                )
            except DeviceVerificationRequiredError:
                errors = await self._async_request_device_verification_code(
                    authenticator
                )
                if not errors:
                    return await self.async_step_device_verification()
            if not errors:
                return self._finish_flow()

        return self._show_reauth_form(user_input, errors)
