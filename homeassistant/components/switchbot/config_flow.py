"""Config flow for Switchbot."""

import logging
from typing import Any, Literal, override

from aiohttp import RequestInfo
from multidict import CIMultiDict, CIMultiDictProxy
import probatio
from switchbot import (
    OAUTH_AUTHORIZE_URL,
    OAUTH_SCOPE,
    OAUTH_TOKEN_URL,
    SwitchbotAccountConnectionError,
    SwitchBotAdvertisement,
    SwitchbotApiError,
    SwitchbotAuthenticationError,
    SwitchbotModel,
    exchange_oauth_code,
    fetch_cloud_devices,
    fetch_cloud_devices_by_token,
    parse_advertisement_data,
)
from yarl import URL

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_ADDRESS,
    CONF_PASSWORD,
    CONF_SENSOR_TYPE,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import (
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers import config_entry_oauth2_flow, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import MY_AUTH_CALLBACK_PATH

from .const import (
    CONF_CURTAIN_SPEED,
    CONF_ENCRYPTION_KEY,
    CONF_KEY_ID,
    CONF_LOCK_NIGHTLATCH,
    CONF_RETRY_COUNT,
    CONNECTABLE_SUPPORTED_MODEL_TYPES,
    CURTAIN_SPEED_MAX,
    CURTAIN_SPEED_MIN,
    DEFAULT_CURTAIN_SPEED,
    DEFAULT_LOCK_NIGHTLATCH,
    DEFAULT_RETRY_COUNT,
    DOMAIN,
    ENCRYPTED_MODELS,
    ENCRYPTED_SWITCHBOT_MODEL_TO_CLASS,
    NON_CONNECTABLE_SUPPORTED_MODEL_TYPES,
    OAUTH_CLIENT_ID,
    SUPPORTED_MODEL_TYPES,
    SupportedModels,
)

_LOGGER = logging.getLogger(__name__)


def format_unique_id(address: str) -> str:
    """Format the unique ID for a switchbot."""
    return address.replace(":", "").lower()


def short_address(address: str) -> str:
    """Convert a Bluetooth address to a short address."""
    results = address.replace("-", ":").split(":")
    return f"{results[-2].upper()}{results[-1].upper()}"[-4:]


def name_from_discovery(discovery: SwitchBotAdvertisement) -> str:
    """Get the name from a discovery."""
    return f"{discovery.data['modelFriendlyName']} {short_address(discovery.address)}"


def _oauth_request_info() -> RequestInfo:
    """Return request metadata for HA OAuth exception adaptation."""
    url = URL(OAUTH_TOKEN_URL)
    return RequestInfo(url, "POST", CIMultiDictProxy(CIMultiDict()), url)


class SwitchbotOAuth2Implementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """SwitchBot OAuth implementation with its registered callback URI."""

    @property
    @override
    def redirect_uri(self) -> str:
        """Return the callback URI registered for the public client."""
        return MY_AUTH_CALLBACK_PATH

    @property
    @override
    def extra_authorize_data(self) -> dict[str, str]:
        """Return additional authorization parameters."""
        return {"scope": OAUTH_SCOPE}

    @override
    async def async_resolve_external_data(
        self, external_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Resolve the callback through pySwitchbot's OAuth implementation."""
        try:
            token = await exchange_oauth_code(
                async_get_clientsession(self.hass),
                self.client_id,
                external_data["state"]["redirect_uri"],
                external_data["code"],
            )
        except SwitchbotAuthenticationError as err:
            # OAuth2TokenRequestReauthError provides its own translation.
            # pylint: disable-next=home-assistant-exception-not-translated
            raise OAuth2TokenRequestReauthError(
                request_info=_oauth_request_info(),
                status=401,
                domain=DOMAIN,
            ) from err
        except SwitchbotAccountConnectionError as err:
            # OAuth2TokenRequestTransientError provides its own translation.
            # pylint: disable-next=home-assistant-exception-not-translated
            raise OAuth2TokenRequestTransientError(
                request_info=_oauth_request_info(),
                status=503,
                domain=DOMAIN,
            ) from err
        except SwitchbotApiError:
            return {}

        # The shared OAuth flow logs the full mapping when expires_in is missing.
        if "expires_in" not in token:
            return {}
        return token


class SwitchbotConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for Switchbot."""

    DOMAIN = DOMAIN
    VERSION = 1
    MINOR_VERSION = 2

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SwitchbotOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SwitchbotOptionsFlowHandler()

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._discovered_adv: SwitchBotAdvertisement | None = None
        self._discovered_advs: dict[str, SwitchBotAdvertisement] = {}
        self._cloud_username: str | None = None
        self._cloud_password: str | None = None
        self._encryption_method_selected = False
        self._oauth_access_token: str | None = None
        self._oauth_next_step: Literal["select_device", "encrypted_key"] | None = None

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return the logger."""
        return _LOGGER

    async def _async_start_oauth(
        self, next_step: Literal["select_device", "encrypted_key"]
    ) -> ConfigFlowResult:
        """Start OAuth and remember where to continue after authorization."""
        self._oauth_next_step = next_step
        self.async_register_implementation(
            self.hass,
            SwitchbotOAuth2Implementation(
                self.hass,
                DOMAIN,
                OAUTH_CLIENT_ID,
                "",
                OAUTH_AUTHORIZE_URL,
                OAUTH_TOKEN_URL,
            ),
        )
        return await self.async_step_pick_implementation()

    async def async_step_oauth_login(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start OAuth for cloud device discovery."""
        return await self._async_start_oauth("select_device")

    async def async_step_encrypted_oauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Use OAuth to retrieve an encrypted device key."""
        if self._oauth_access_token is None:
            return await self._async_start_oauth("encrypted_key")
        return await self._async_retrieve_encryption_key_by_token()

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Continue device setup without persisting the OAuth token."""
        access_token = data[CONF_TOKEN].get(CONF_ACCESS_TOKEN)
        if not isinstance(access_token, str) or not access_token:
            return self.async_abort(reason="oauth_error")

        self._oauth_access_token = access_token
        if self._oauth_next_step == "select_device":
            try:
                await fetch_cloud_devices_by_token(
                    async_get_clientsession(self.hass), access_token
                )
            except SwitchbotAuthenticationError:
                return self.async_abort(reason="oauth_unauthorized")
            except (SwitchbotApiError, SwitchbotAccountConnectionError) as ex:
                _LOGGER.debug(
                    "Failed to connect to SwitchBot API: %s", ex, exc_info=True
                )
                return self.async_abort(
                    reason="api_error",
                    description_placeholders={"error_detail": str(ex)},
                )
            except Exception:
                _LOGGER.exception("Unexpected error during OAuth cloud login")
                return self.async_abort(reason="unknown")
            return await self.async_step_select_device()

        if self._oauth_next_step == "encrypted_key":
            return await self._async_retrieve_encryption_key_by_token()

        return self.async_abort(reason="oauth_error")

    async def _async_retrieve_encryption_key_by_token(self) -> ConfigFlowResult:
        """Retrieve an encryption key with the current flow's OAuth token."""
        assert self._discovered_adv is not None
        assert self._oauth_access_token is not None
        model: SwitchbotModel = self._discovered_adv.data["modelName"]
        cls = ENCRYPTED_SWITCHBOT_MODEL_TO_CLASS[model]
        try:
            key_details = await cls.async_retrieve_encryption_key_by_token(
                async_get_clientsession(self.hass),
                self._discovered_adv.address,
                self._oauth_access_token,
            )
        except SwitchbotAuthenticationError as ex:
            _LOGGER.debug("Authentication failed: %s", ex, exc_info=True)
            return self.async_abort(reason="oauth_unauthorized")
        except (SwitchbotApiError, SwitchbotAccountConnectionError) as ex:
            _LOGGER.debug("Failed to connect to SwitchBot API: %s", ex, exc_info=True)
            return self.async_abort(
                reason="api_error",
                description_placeholders={"error_detail": str(ex)},
            )
        except Exception:
            _LOGGER.exception("Unexpected error retrieving encryption key with OAuth")
            return self.async_abort(reason="unknown")
        return await self.async_step_encrypted_key(key_details)

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Discovered bluetooth device: %s", discovery_info.as_dict())
        await self.async_set_unique_id(format_unique_id(discovery_info.address))
        self._abort_if_unique_id_configured()
        parsed = parse_advertisement_data(
            discovery_info.device, discovery_info.advertisement
        )
        if not parsed or parsed.data.get("modelName") not in SUPPORTED_MODEL_TYPES:
            return self.async_abort(reason="not_supported")
        model_name = parsed.data.get("modelName")
        if (
            not discovery_info.connectable
            and model_name in CONNECTABLE_SUPPORTED_MODEL_TYPES
            and model_name not in NON_CONNECTABLE_SUPPORTED_MODEL_TYPES
        ):
            # Source is not connectable but the model is connectable only
            return self.async_abort(reason="not_supported")
        self._discovered_adv = parsed
        data = parsed.data
        self.context["title_placeholders"] = {
            "name": data["modelFriendlyName"],
            "address": short_address(discovery_info.address),
        }
        if model_name in ENCRYPTED_MODELS:
            return await self.async_step_encrypted_choose_method()
        if self._discovered_adv.data["isEncrypted"]:
            return await self.async_step_password()
        return await self.async_step_confirm()

    async def _async_create_entry_from_discovery(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Create an entry from a discovery."""
        assert self._discovered_adv is not None
        discovery = self._discovered_adv
        name = name_from_discovery(discovery)
        model_name = discovery.data["modelName"]
        sensor_type = SUPPORTED_MODEL_TYPES[model_name]

        options: dict[str, Any] = {CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT}
        if sensor_type == SupportedModels.CURTAIN:
            options[CONF_CURTAIN_SPEED] = DEFAULT_CURTAIN_SPEED

        return self.async_create_entry(
            title=name,
            data={
                **user_input,
                CONF_ADDRESS: discovery.address,
                CONF_SENSOR_TYPE: str(sensor_type),
            },
            options=options,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a single device."""
        assert self._discovered_adv is not None
        if user_input is not None:
            return await self._async_create_entry_from_discovery(user_input)

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
            description_placeholders={
                "name": name_from_discovery(self._discovered_adv)
            },
        )

    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the password step."""
        assert self._discovered_adv is not None
        if user_input is not None:
            # There is currently no api to validate the password
            # that does not operate the device so we have
            # to accept it as-is
            return await self._async_create_entry_from_discovery(user_input)

        return self.async_show_form(
            step_id="password",
            data_schema=probatio.Schema({probatio.Required(CONF_PASSWORD): str}),
            description_placeholders={
                "name": name_from_discovery(self._discovered_adv)
            },
        )

    async def async_step_encrypted_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the SwitchBot API auth step."""
        errors: dict[str, str] = {}
        assert self._discovered_adv is not None
        description_placeholders: dict[str, str] = {}

        if user_input is None:
            if not self._encryption_method_selected and not (
                self._cloud_username and self._cloud_password
            ):
                return await self.async_step_encrypted_choose_method()
            self._encryption_method_selected = False

        # If we have saved credentials from cloud login, try them first
        if user_input is None and self._cloud_username and self._cloud_password:
            user_input = {
                CONF_USERNAME: self._cloud_username,
                CONF_PASSWORD: self._cloud_password,
            }

        if user_input is not None:
            model: SwitchbotModel = self._discovered_adv.data["modelName"]
            cls = ENCRYPTED_SWITCHBOT_MODEL_TO_CLASS[model]
            try:
                key_details = await cls.async_retrieve_encryption_key(
                    async_get_clientsession(self.hass),
                    self._discovered_adv.address,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except (SwitchbotApiError, SwitchbotAccountConnectionError) as ex:
                _LOGGER.debug(
                    "Failed to connect to SwitchBot API: %s", ex, exc_info=True
                )
                raise AbortFlow(
                    "api_error", description_placeholders={"error_detail": str(ex)}
                ) from ex
            except SwitchbotAuthenticationError as ex:
                _LOGGER.debug("Authentication failed: %s", ex, exc_info=True)
                errors = {"base": "auth_failed"}
                description_placeholders = {"error_detail": str(ex)}
                # Clear saved credentials if auth failed
                self._cloud_username = None
                self._cloud_password = None
            except Exception:
                _LOGGER.exception("Unexpected error retrieving encryption key")
                errors = {"base": "unknown"}
            else:
                return await self.async_step_encrypted_key(key_details)

        user_input = user_input or {}
        return self.async_show_form(
            step_id="encrypted_auth",
            errors=errors,
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME)
                    ): str,
                    probatio.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={
                "name": name_from_discovery(self._discovered_adv),
                **description_placeholders,
            },
        )

    async def async_step_encrypted_choose_method(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the SwitchBot API chose method step."""
        assert self._discovered_adv is not None

        self._encryption_method_selected = True
        return self.async_show_menu(
            step_id="encrypted_choose_method",
            menu_options=["encrypted_oauth", "encrypted_auth", "encrypted_key"],
            description_placeholders={
                "name": name_from_discovery(self._discovered_adv),
            },
        )

    async def async_step_encrypted_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the encryption key step."""
        errors: dict[str, str] = {}
        assert self._discovered_adv is not None

        if user_input is None:
            if not self._encryption_method_selected:
                return await self.async_step_encrypted_choose_method()
            self._encryption_method_selected = False

        if user_input is not None:
            model: SwitchbotModel = self._discovered_adv.data["modelName"]
            cls = ENCRYPTED_SWITCHBOT_MODEL_TO_CLASS[model]
            if not await cls.verify_encryption_key(
                self._discovered_adv.device,
                user_input[CONF_KEY_ID],
                user_input[CONF_ENCRYPTION_KEY],
                model=model,
            ):
                errors = {
                    "base": "encryption_key_invalid",
                }
            else:
                return await self._async_create_entry_from_discovery(user_input)

        return self.async_show_form(
            step_id="encrypted_key",
            errors=errors,
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_KEY_ID): str,
                    probatio.Required(CONF_ENCRYPTION_KEY): str,
                }
            ),
            description_placeholders={
                "name": name_from_discovery(self._discovered_adv),
            },
        )

    @callback
    def _async_discover_devices(self) -> None:
        current_addresses = self._async_current_ids(include_ignore=False)
        for connectable in (True, False):
            for discovery_info in async_discovered_service_info(self.hass, connectable):
                address = discovery_info.address
                if (
                    format_unique_id(address) in current_addresses
                    or address in self._discovered_advs
                ):
                    continue
                parsed = parse_advertisement_data(
                    discovery_info.device, discovery_info.advertisement
                )
                if not parsed:
                    continue
                model_name = parsed.data.get("modelName")
                if (
                    discovery_info.connectable
                    and model_name in CONNECTABLE_SUPPORTED_MODEL_TYPES
                ) or model_name in NON_CONNECTABLE_SUPPORTED_MODEL_TYPES:
                    self._discovered_advs[address] = parsed

        if not self._discovered_advs:
            raise AbortFlow("no_devices_found")

    async def _async_set_device(self, discovery: SwitchBotAdvertisement) -> None:
        """Set the device to work with."""
        self._discovered_adv = discovery
        address = discovery.address
        await self.async_set_unique_id(
            format_unique_id(address), raise_on_progress=False
        )
        self._abort_if_unique_id_configured()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to choose cloud login or direct discovery."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["oauth_login", "cloud_login", "select_device"],
        )

    async def async_step_cloud_login(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the cloud login step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            try:
                await fetch_cloud_devices(
                    async_get_clientsession(self.hass),
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except (SwitchbotApiError, SwitchbotAccountConnectionError) as ex:
                _LOGGER.debug(
                    "Failed to connect to SwitchBot API: %s", ex, exc_info=True
                )
                raise AbortFlow(
                    "api_error", description_placeholders={"error_detail": str(ex)}
                ) from ex
            except SwitchbotAuthenticationError as ex:
                _LOGGER.debug("Authentication failed: %s", ex, exc_info=True)
                errors = {"base": "auth_failed"}
                description_placeholders = {"error_detail": str(ex)}
            except Exception:
                _LOGGER.exception("Unexpected error during cloud login")
                errors = {"base": "unknown"}
            else:
                # Save credentials temporarily for the duration of this flow
                # to avoid re-prompting if encrypted device auth is needed
                # These will be discarded when the flow completes
                self._cloud_username = user_input[CONF_USERNAME]
                self._cloud_password = user_input[CONF_PASSWORD]
                return await self.async_step_select_device()

        user_input = user_input or {}
        return self.async_show_form(
            step_id="cloud_login",
            errors=errors,
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME)
                    ): str,
                    probatio.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders=description_placeholders,
        )

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to pick discovered device."""
        errors: dict[str, str] = {}
        device_adv: SwitchBotAdvertisement | None = None
        if user_input is not None:
            device_adv = self._discovered_advs[user_input[CONF_ADDRESS]]
            await self._async_set_device(device_adv)
            if device_adv.data.get("modelName") in ENCRYPTED_MODELS:
                return await self.async_step_encrypted_choose_method()
            if device_adv.data["isEncrypted"]:
                return await self.async_step_password()
            return await self._async_create_entry_from_discovery(user_input)

        await bluetooth.async_request_active_scan(self.hass)
        self._async_discover_devices()
        if len(self._discovered_advs) == 1:
            # If there is only one device we can ask for a password
            # or simply confirm it
            device_adv = list(self._discovered_advs.values())[0]
            await self._async_set_device(device_adv)
            if device_adv.data.get("modelName") in ENCRYPTED_MODELS:
                return await self.async_step_encrypted_choose_method()
            if device_adv.data["isEncrypted"]:
                return await self.async_step_password()
            return await self.async_step_confirm()

        return self.async_show_form(
            step_id="select_device",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_ADDRESS): probatio.In(
                        {
                            address: name_from_discovery(parsed)
                            for address, parsed in self._discovered_advs.items()
                        }
                    ),
                }
            ),
            errors=errors,
        )


class SwitchbotOptionsFlowHandler(OptionsFlow):
    """Handle Switchbot options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Switchbot options."""
        if user_input is not None:
            # Update common entity options for all other entities.
            return self.async_create_entry(title="", data=user_input)

        options: dict[probatio.Optional, Any] = {
            probatio.Optional(
                CONF_RETRY_COUNT,
                default=self.config_entry.options.get(
                    CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT
                ),
            ): int
        }
        if CONF_SENSOR_TYPE in self.config_entry.data and self.config_entry.data[
            CONF_SENSOR_TYPE
        ] in (
            SupportedModels.LOCK,
            SupportedModels.LOCK_PRO,
            SupportedModels.LOCK_ULTRA,
            SupportedModels.LOCK_ULTRA_MAX,
            SupportedModels.LOCK_PRO_WIFI,
            SupportedModels.LOCK_VISION,
            SupportedModels.LOCK_VISION_PRO,
        ):
            options.update(
                {
                    probatio.Optional(
                        CONF_LOCK_NIGHTLATCH,
                        default=self.config_entry.options.get(
                            CONF_LOCK_NIGHTLATCH, DEFAULT_LOCK_NIGHTLATCH
                        ),
                    ): bool
                }
            )
        if (
            CONF_SENSOR_TYPE in self.config_entry.data
            and self.config_entry.data[CONF_SENSOR_TYPE] == SupportedModels.CURTAIN
        ):
            options.update(
                {
                    probatio.Optional(
                        CONF_CURTAIN_SPEED,
                        default=self.config_entry.options.get(
                            CONF_CURTAIN_SPEED, DEFAULT_CURTAIN_SPEED
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=CURTAIN_SPEED_MIN,
                            max=CURTAIN_SPEED_MAX,
                            step=1,
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    )
                }
            )

        return self.async_show_form(
            step_id="init", data_schema=probatio.Schema(options)
        )
