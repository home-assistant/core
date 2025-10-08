"""Config flow for the Ubiquiti airOS integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from airos.exceptions import (
    AirOSConnectionAuthenticationError,
    AirOSConnectionSetupError,
    AirOSDataMissingError,
    AirOSDeviceConnectionError,
    AirOSKeyDataMissingError,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DEFAULT_SSL, DEFAULT_VERIFY_SSL, DOMAIN, SECTION_ADVANCED_SETTINGS
from .coordinator import AirOS8

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default="ubnt"): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(SECTION_ADVANCED_SETTINGS): section(
            vol.Schema(
                {
                    vol.Required(CONF_SSL, default=DEFAULT_SSL): bool,
                    vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
                }
            ),
            {"collapsed": True},
        ),
    }
)


class AirOSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ubiquiti airOS."""

    VERSION = 2
    MINOR_VERSION = 0

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self.airos_device: AirOS8
        self.errors: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the manual input of host and credentials."""
        self.errors = {}
        if user_input is not None:
            validated_info = await self._validate_and_get_device_info(user_input)
            if validated_info:
                return self.async_create_entry(
                    title=validated_info["title"],
                    data=validated_info["data"],
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=self.errors
        )

    async def _validate_and_get_device_info(
        self, config_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Validate user input with the device API."""
        # By default airOS 8 comes with self-signed SSL certificates,
        # with no option in the web UI to change or upload a custom certificate.
        session = async_get_clientsession(
            self.hass,
            verify_ssl=config_data[SECTION_ADVANCED_SETTINGS][CONF_VERIFY_SSL],
        )

        airos_device = AirOS8(
            host=config_data[CONF_HOST],
            username=config_data[CONF_USERNAME],
            password=config_data[CONF_PASSWORD],
            session=session,
            use_ssl=config_data[SECTION_ADVANCED_SETTINGS][CONF_SSL],
        )
        try:
            await airos_device.login()
            airos_data = await airos_device.status()

        except (
            AirOSConnectionSetupError,
            AirOSDeviceConnectionError,
        ):
            self.errors["base"] = "cannot_connect"
        except (AirOSConnectionAuthenticationError, AirOSDataMissingError):
            self.errors["base"] = "invalid_auth"
        except AirOSKeyDataMissingError:
            self.errors["base"] = "key_data_missing"
        except Exception:
            _LOGGER.exception("Unexpected exception during credential validation")
            self.errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(airos_data.derived.mac)

            if self.source == SOURCE_REAUTH:
                self._abort_if_unique_id_mismatch()
            else:
                self._abort_if_unique_id_configured()

            return {"title": airos_data.host.hostname, "data": config_data}

        return None

    async def async_step_reauth(
        self,
        user_input: Mapping[str, Any],
    ) -> ConfigFlowResult:
        """Perform reauthentication upon an API authentication error."""
        return await self.async_step_reauth_confirm(user_input)

    async def async_step_reauth_confirm(
        self,
        user_input: Mapping[str, Any],
    ) -> ConfigFlowResult:
        """Perform reauthentication upon an API authentication error."""
        self.errors = {}

        if user_input:
            validate_data = {**self._get_reauth_entry().data, **user_input}
            if await self._validate_and_get_device_info(config_data=validate_data):
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates=validate_data,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    ),
                }
            ),
            errors=self.errors,
        )
