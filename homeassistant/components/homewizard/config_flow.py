"""Config flow for HomeWizard."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, NamedTuple

from homewizard_energy import HomeWizardEnergy
from homewizard_energy.errors import DisabledError, RequestError, UnsupportedError
from homewizard_energy.models import Device
from voluptuous import Required, Schema

from homeassistant.components import onboarding, zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_PATH
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_API_ENABLED,
    CONF_PRODUCT_NAME,
    CONF_PRODUCT_TYPE,
    CONF_SERIAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class DiscoveryData(NamedTuple):
    """User metadata."""

    ip: str
    product_name: str
    product_type: str
    serial: str


class HomeWizardConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for P1 meter."""

    VERSION = 1

    discovery: DiscoveryData

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            try:
                device_info = await self._async_try_connect(user_input[CONF_IP_ADDRESS])
            except RecoverableError as ex:
                _LOGGER.error(ex)
                errors = {"base": ex.error_code}
            else:
                await self.async_set_unique_id(
                    f"{device_info.product_type}_{device_info.serial}"
                )
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(
                    title=f"{device_info.product_name}",
                    data=user_input,
                )

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=Schema(
                {
                    Required(
                        CONF_IP_ADDRESS, default=user_input.get(CONF_IP_ADDRESS)
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
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

        self.discovery = DiscoveryData(
            ip=discovery_info.host,
            product_type=discovery_info.properties[CONF_PRODUCT_TYPE],
            product_name=discovery_info.properties[CONF_PRODUCT_NAME],
            serial=discovery_info.properties[CONF_SERIAL],
        )

        await self.async_set_unique_id(
            f"{self.discovery.product_type}_{self.discovery.serial}"
        )
        self._abort_if_unique_id_configured(
            updates={CONF_IP_ADDRESS: discovery_info.host}
        )

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        errors: dict[str, str] | None = None
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            try:
                await self._async_try_connect(self.discovery.ip)
            except RecoverableError as ex:
                _LOGGER.error(ex)
                errors = {"base": ex.error_code}
            else:
                return self.async_create_entry(
                    title=self.discovery.product_name,
                    data={CONF_IP_ADDRESS: self.discovery.ip},
                )

        self._set_confirm_only()

        # We won't be adding mac/serial to the title for devices
        # that users generally don't have multiple of.
        name = self.discovery.product_name
        if self.discovery.product_type not in ["HWE-P1", "HWE-WTR"]:
            name = f"{name} ({self.discovery.serial})"
        self.context["title_placeholders"] = {"name": name}

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                CONF_PRODUCT_TYPE: self.discovery.product_type,
                CONF_SERIAL: self.discovery.serial,
                CONF_IP_ADDRESS: self.discovery.ip,
            },
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-auth if API was disabled."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            try:
                await self._async_try_connect(reauth_entry.data[CONF_IP_ADDRESS])
            except RecoverableError as ex:
                _LOGGER.error(ex)
                errors = {"base": ex.error_code}
            else:
                await self.hass.config_entries.async_reload(reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(step_id="reauth_confirm", errors=errors)

    @staticmethod
    async def _async_try_connect(ip_address: str) -> Device:
        """Try to connect.

        Make connection with device to test the connection
        and to get info for unique_id.
        """
        energy_api = HomeWizardEnergy(ip_address)
        try:
            return await energy_api.device()

        except DisabledError as ex:
            raise RecoverableError(
                "API disabled, API must be enabled in the app", "api_not_enabled"
            ) from ex

        except UnsupportedError as ex:
            _LOGGER.error("API version unsuppored")
            raise AbortFlow("unsupported_api_version") from ex

        except RequestError as ex:
            raise RecoverableError(
                "Device unreachable or unexpected response", "network_error"
            ) from ex

        except Exception as ex:
            _LOGGER.exception("Unexpected exception")
            raise AbortFlow("unknown_error") from ex

        finally:
            await energy_api.close()


class RecoverableError(HomeAssistantError):
    """Raised when a connection has been failed but can be retried."""

    def __init__(self, message: str, error_code: str) -> None:
        """Init RecoverableError."""
        super().__init__(message)
        self.error_code = error_code
