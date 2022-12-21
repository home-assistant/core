"""Config flow for Homewizard."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, cast

from homewizard_energy import HomeWizardEnergy
from homewizard_energy.errors import DisabledError, RequestError, UnsupportedError
from voluptuous import Required, Schema

from homeassistant import config_entries
from homeassistant.components import persistent_notification, zeroconf
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.data_entry_flow import AbortFlow, FlowResult

from .const import (
    CONF_API_ENABLED,
    CONF_PATH,
    CONF_PRODUCT_NAME,
    CONF_PRODUCT_TYPE,
    CONF_SERIAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for P1 meter."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the HomeWizard config flow."""
        self.config: dict[str, str | int] = {}
        self.entry: config_entries.ConfigEntry | None = None

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Handle a flow initiated by older `homewizard_energy` component."""
        _LOGGER.debug("config_flow async_step_import")

        persistent_notification.async_create(
            self.hass,
            title="HomeWizard Energy",
            message=(
                "The custom integration of HomeWizard Energy has been migrated to core. "
                "You can safely remove the custom integration from the custom_integrations folder."
            ),
            notification_id=f"homewizard_energy_to_{DOMAIN}",
        )

        return await self.async_step_user({CONF_IP_ADDRESS: import_config["host"]})

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""

        _LOGGER.debug("config_flow async_step_user")

        data_schema = Schema(
            {
                Required(CONF_IP_ADDRESS): str,
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
                errors=None,
            )

        error = await self._async_try_connect(user_input[CONF_IP_ADDRESS])
        if error is not None:
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
                errors={"base": error},
            )

        # Fetch device information
        api = HomeWizardEnergy(user_input[CONF_IP_ADDRESS])
        device_info = await api.device()
        await api.close()

        # Sets unique ID and aborts if it is already exists
        await self._async_set_and_check_unique_id(
            {
                CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                CONF_PRODUCT_TYPE: device_info.product_type,
                CONF_SERIAL: device_info.serial,
            }
        )

        data: dict[str, str] = {CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS]}

        if self.source == config_entries.SOURCE_IMPORT:
            old_config_entry_id = self.context["old_config_entry_id"]
            assert self.hass.config_entries.async_get_entry(old_config_entry_id)
            data["old_config_entry_id"] = old_config_entry_id

        # Add entry
        return self.async_create_entry(
            title=f"{device_info.product_name} ({device_info.serial})",
            data=data,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""

        _LOGGER.debug("config_flow async_step_zeroconf")

        # Validate doscovery entry
        if (
            CONF_API_ENABLED not in discovery_info.properties
            or CONF_PATH not in discovery_info.properties
            or CONF_PRODUCT_NAME not in discovery_info.properties
            or CONF_PRODUCT_TYPE not in discovery_info.properties
            or CONF_SERIAL not in discovery_info.properties
        ):
            return self.async_abort(reason="invalid_discovery_parameters")

        if (discovery_info.properties[CONF_PATH]) != "/api/v1":
            return self.async_abort(reason="unsupported_api_version")

        # Sets unique ID and aborts if it is already exists
        await self._async_set_and_check_unique_id(
            {
                CONF_IP_ADDRESS: discovery_info.host,
                CONF_PRODUCT_TYPE: discovery_info.properties[CONF_PRODUCT_TYPE],
                CONF_SERIAL: discovery_info.properties[CONF_SERIAL],
            }
        )

        # Pass parameters
        self.config = {
            CONF_API_ENABLED: discovery_info.properties[CONF_API_ENABLED],
            CONF_IP_ADDRESS: discovery_info.host,
            CONF_PRODUCT_TYPE: discovery_info.properties[CONF_PRODUCT_TYPE],
            CONF_PRODUCT_NAME: discovery_info.properties[CONF_PRODUCT_NAME],
            CONF_SERIAL: discovery_info.properties[CONF_SERIAL],
        }
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:

            # Check connection
            error = await self._async_try_connect(str(self.config[CONF_IP_ADDRESS]))
            if error is not None:
                return self.async_show_form(
                    step_id="discovery_confirm",
                    errors={"base": error},
                )

            return self.async_create_entry(
                title=f"{self.config[CONF_PRODUCT_NAME]} ({self.config[CONF_SERIAL]})",
                data={
                    CONF_IP_ADDRESS: self.config[CONF_IP_ADDRESS],
                },
            )

        self._set_confirm_only()

        self.context["title_placeholders"] = {
            "name": f"{self.config[CONF_PRODUCT_NAME]} ({self.config[CONF_SERIAL]})"
        }

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                CONF_PRODUCT_TYPE: cast(str, self.config[CONF_PRODUCT_TYPE]),
                CONF_SERIAL: cast(str, self.config[CONF_SERIAL]),
                CONF_IP_ADDRESS: cast(str, self.config[CONF_IP_ADDRESS]),
            },
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle re-auth if API was disabled."""

        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""

        if user_input is not None:
            assert self.entry is not None

            error = await self._async_try_connect(self.entry.data[CONF_IP_ADDRESS])
            if error is not None:
                return self.async_show_form(
                    step_id="reauth_confirm",
                    errors={"base": error},
                )

            await self.hass.config_entries.async_reload(self.entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
        )

    @staticmethod
    async def _async_try_connect(ip_address: str) -> str | None:
        """Try to connect."""

        _LOGGER.debug("config_flow _async_try_connect")

        # Make connection with device
        # This is to test the connection and to get info for unique_id
        energy_api = HomeWizardEnergy(ip_address)

        try:
            await energy_api.device()

        except DisabledError:
            _LOGGER.error("API disabled, API must be enabled in the app")
            return "api_not_enabled"

        except UnsupportedError as ex:
            _LOGGER.error("API version unsuppored")
            raise AbortFlow("unsupported_api_version") from ex

        except RequestError as ex:
            _LOGGER.exception(ex)
            return "network_error"

        except Exception as ex:
            _LOGGER.exception(ex)
            raise AbortFlow("unknown_error") from ex

        finally:
            await energy_api.close()

        return None

    async def _async_set_and_check_unique_id(self, entry_info: dict[str, Any]) -> None:
        """Validate if entry exists."""

        _LOGGER.debug("config_flow _async_set_and_check_unique_id")

        await self.async_set_unique_id(
            f"{entry_info[CONF_PRODUCT_TYPE]}_{entry_info[CONF_SERIAL]}"
        )
        self._abort_if_unique_id_configured(
            updates={CONF_IP_ADDRESS: entry_info[CONF_IP_ADDRESS]}
        )
