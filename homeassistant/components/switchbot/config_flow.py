"""Config flow for Switchbot."""

from __future__ import annotations

import logging
from typing import Any

from switchbot import (
    SwitchbotAccountConnectionError,
    SwitchBotAdvertisement,
    SwitchbotApiError,
    SwitchbotAuthenticationError,
    SwitchbotLock,
    parse_advertisement_data,
)
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_PASSWORD,
    CONF_SENSOR_TYPE,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ENCRYPTION_KEY,
    CONF_KEY_ID,
    CONF_LOCK_NIGHTLATCH,
    CONF_RETRY_COUNT,
    CONNECTABLE_SUPPORTED_MODEL_TYPES,
    DEFAULT_LOCK_NIGHTLATCH,
    DEFAULT_RETRY_COUNT,
    DOMAIN,
    NON_CONNECTABLE_SUPPORTED_MODEL_TYPES,
    SUPPORTED_LOCK_MODELS,
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
    return f'{discovery.data["modelFriendlyName"]} {short_address(discovery.address)}'


class SwitchbotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Switchbot."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SwitchbotOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SwitchbotOptionsFlowHandler(config_entry)

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_adv: SwitchBotAdvertisement | None = None
        self._discovered_advs: dict[str, SwitchBotAdvertisement] = {}

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
        ):
            # Source is not connectable but the model is connectable
            return self.async_abort(reason="not_supported")
        self._discovered_adv = parsed
        data = parsed.data
        self.context["title_placeholders"] = {
            "name": data["modelFriendlyName"],
            "address": short_address(discovery_info.address),
        }
        if model_name in SUPPORTED_LOCK_MODELS:
            return await self.async_step_lock_choose_method()
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
        return self.async_create_entry(
            title=name,
            data={
                **user_input,
                CONF_ADDRESS: discovery.address,
                CONF_SENSOR_TYPE: str(SUPPORTED_MODEL_TYPES[model_name]),
            },
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
            data_schema=vol.Schema({}),
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
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={
                "name": name_from_discovery(self._discovered_adv)
            },
        )

    async def async_step_lock_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the SwitchBot API auth step."""
        errors = {}
        assert self._discovered_adv is not None
        description_placeholders = {}
        if user_input is not None:
            try:
                key_details = await SwitchbotLock.async_retrieve_encryption_key(
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
            else:
                return await self.async_step_lock_key(key_details)

        user_input = user_input or {}
        return self.async_show_form(
            step_id="lock_auth",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME)
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={
                "name": name_from_discovery(self._discovered_adv),
                **description_placeholders,
            },
        )

    async def async_step_lock_choose_method(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the SwitchBot API chose method step."""
        assert self._discovered_adv is not None

        return self.async_show_menu(
            step_id="lock_choose_method",
            menu_options=["lock_auth", "lock_key"],
            description_placeholders={
                "name": name_from_discovery(self._discovered_adv),
            },
        )

    async def async_step_lock_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the encryption key step."""
        errors = {}
        assert self._discovered_adv is not None
        if user_input is not None:
            if not await SwitchbotLock.verify_encryption_key(
                self._discovered_adv.device,
                user_input[CONF_KEY_ID],
                user_input[CONF_ENCRYPTION_KEY],
                model=self._discovered_adv.data["modelName"],
            ):
                errors = {
                    "base": "encryption_key_invalid",
                }
            else:
                return await self._async_create_entry_from_discovery(user_input)

        return self.async_show_form(
            step_id="lock_key",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_KEY_ID): str,
                    vol.Required(CONF_ENCRYPTION_KEY): str,
                }
            ),
            description_placeholders={
                "name": name_from_discovery(self._discovered_adv),
            },
        )

    @callback
    def _async_discover_devices(self) -> None:
        current_addresses = self._async_current_ids()
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}
        device_adv: SwitchBotAdvertisement | None = None
        if user_input is not None:
            device_adv = self._discovered_advs[user_input[CONF_ADDRESS]]
            await self._async_set_device(device_adv)
            if device_adv.data.get("modelName") in SUPPORTED_LOCK_MODELS:
                return await self.async_step_lock_choose_method()
            if device_adv.data["isEncrypted"]:
                return await self.async_step_password()
            return await self._async_create_entry_from_discovery(user_input)

        self._async_discover_devices()
        if len(self._discovered_advs) == 1:
            # If there is only one device we can ask for a password
            # or simply confirm it
            device_adv = list(self._discovered_advs.values())[0]
            await self._async_set_device(device_adv)
            if device_adv.data.get("modelName") in SUPPORTED_LOCK_MODELS:
                return await self.async_step_lock_choose_method()
            if device_adv.data["isEncrypted"]:
                return await self.async_step_password()
            return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
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

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Switchbot options."""
        if user_input is not None:
            # Update common entity options for all other entities.
            return self.async_create_entry(title="", data=user_input)

        options: dict[vol.Optional, Any] = {
            vol.Optional(
                CONF_RETRY_COUNT,
                default=self.config_entry.options.get(
                    CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT
                ),
            ): int
        }
        if self.config_entry.data.get(CONF_SENSOR_TYPE) == SupportedModels.LOCK_PRO:
            options.update(
                {
                    vol.Optional(
                        CONF_LOCK_NIGHTLATCH,
                        default=self.config_entry.options.get(
                            CONF_LOCK_NIGHTLATCH, DEFAULT_LOCK_NIGHTLATCH
                        ),
                    ): bool
                }
            )

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
