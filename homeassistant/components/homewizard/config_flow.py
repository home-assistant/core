"""Config flow for HomeWizard."""

from __future__ import annotations

from collections.abc import Mapping
import contextlib
from typing import Any

from homewizard_energy import (
    HomeWizardEnergy,
    HomeWizardEnergyV1,
    HomeWizardEnergyV2,
    has_v2_api,
)
from homewizard_energy.errors import (
    DisabledError,
    RequestError,
    UnauthorizedError,
    UnsupportedError,
)
from homewizard_energy.models import Device
import voluptuous as vol

from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_PATH, CONF_TOKEN
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import TextSelector
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_API_ENABLED,
    CONF_PRODUCT_NAME,
    CONF_PRODUCT_TYPE,
    CONF_SERIAL,
    DOMAIN,
    LOGGER,
)


class HomeWizardConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for P1 meter."""

    VERSION = 1

    ip_address: str | None = None
    product_name: str | None = None
    product_type: str | None = None
    serial: str | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.ip_address: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""

        errors: dict[str, str] | None = None
        if user_input is not None:
            try:
                device_info = await self._async_try_connect(user_input[CONF_IP_ADDRESS])
            except RecoverableError as ex:
                LOGGER.error(ex)
                errors = {"base": ex.error_code}
            except UnauthorizedError:
                # Device responded, so IP is correct. But we have to authorize
                self.ip_address = user_input[CONF_IP_ADDRESS]
                return await self.async_step_authorize()
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
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_IP_ADDRESS, default=user_input.get(CONF_IP_ADDRESS)
                    ): TextSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step where we attempt to get a token."""

        # We can assume that the IP address is set by the previous step, of not something is terribly wrong
        assert self.ip_address is not None

        api = HomeWizardEnergyV2(self.ip_address)
        token = None

        # Tell device we want a token, user must now press the button within 30 seconds
        with contextlib.suppress(DisabledError):
            token = await api.get_token("home-assistant")

        if user_input is None:
            return self.async_show_form(
                step_id="authorize",
            )

        if token is None:
            errors = {"base": "authorization_failed"}
            return self.async_show_form(step_id="authorize", errors=errors)

        # Now we got a token, we can ask for some more info
        device_info = await api.device()

        data = {
            CONF_IP_ADDRESS: self.ip_address,
            CONF_TOKEN: token,
        }

        await self.async_set_unique_id(
            f"{device_info.product_type}_{device_info.serial}"
        )
        self._abort_if_unique_id_configured(updates=data)
        return self.async_create_entry(
            title=f"{device_info.product_name}",
            data=data,
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step where we attempt to get a token."""
        assert self.ip_address

        api = HomeWizardEnergyV2(self.ip_address)
        token: str | None = None
        errors: dict[str, str] | None = None

        # Tell device we want a token, user must now press the button within 30 seconds
        # The first attempt will always fail and raise DisabledError but this opens the window to press the button
        with contextlib.suppress(DisabledError):
            token = await api.get_token("home-assistant")

        if token is None:
            errors = {"base": "authorization_failed"}

        if user_input is None or token is None:
            await api.close()
            return self.async_show_form(step_id="authorize", errors=errors)

        # Now we got a token, we can ask for some more info
        device_info = await api.device()
        await api.close()

        data = {
            CONF_IP_ADDRESS: self.ip_address,
            CONF_TOKEN: token,
        }

        await self.async_set_unique_id(
            f"{device_info.product_type}_{device_info.serial}"
        )
        self._abort_if_unique_id_configured(updates=data)
        return self.async_create_entry(
            title=f"{device_info.product_name}",
            data=data,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
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

        self.ip_address = discovery_info.host
        self.product_type = discovery_info.properties[CONF_PRODUCT_TYPE]
        self.product_name = discovery_info.properties[CONF_PRODUCT_NAME]
        self.serial = discovery_info.properties[CONF_SERIAL]

        await self.async_set_unique_id(f"{self.product_type}_{self.serial}")
        self._abort_if_unique_id_configured(
            updates={CONF_IP_ADDRESS: discovery_info.host}
        )

        return await self.async_step_discovery_confirm()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle dhcp discovery to update existing entries.

        This flow is triggered only by DHCP discovery of known devices.
        """
        try:
            device = await self._async_try_connect(discovery_info.ip)
        except RecoverableError as ex:
            LOGGER.error(ex)
            return self.async_abort(reason="unknown")
        except UnauthorizedError:
            return self.async_abort(reason="unsupported_api_version")
<<<<<<< HEAD
        except UnauthorizedError as ex:
            # Device responded, so IP is correct
            pass
=======
>>>>>>> fd945ced06f (Update quality_scale)

        await self.async_set_unique_id(
            f"{device.product_type}_{discovery_info.macaddress}"
        )

        self._abort_if_unique_id_configured(
            updates={CONF_IP_ADDRESS: discovery_info.ip}
        )

        # This situation should never happen, as Home Assistant will only
        # send updates for existing entries. In case it does, we'll just
        # abort the flow with an unknown error.
        return self.async_abort(reason="unknown")

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self.ip_address
        assert self.product_name
        assert self.product_type
        assert self.serial

        errors: dict[str, str] | None = None
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            try:
                await self._async_try_connect(self.ip_address)
            except RecoverableError as ex:
                LOGGER.error(ex)
                errors = {"base": ex.error_code}
            else:
                return self.async_create_entry(
                    title=self.product_name,
                    data={CONF_IP_ADDRESS: self.ip_address},
                )

        self._set_confirm_only()

        # We won't be adding mac/serial to the title for devices
        # that users generally don't have multiple of.
        name = self.product_name
        if self.product_type not in ["HWE-P1", "HWE-WTR"]:
            name = f"{name} ({self.serial})"
        self.context["title_placeholders"] = {"name": name}

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                CONF_PRODUCT_TYPE: self.product_type,
                CONF_SERIAL: self.serial,
                CONF_IP_ADDRESS: self.ip_address,
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
                LOGGER.error(ex)
                errors = {"base": ex.error_code}
            else:
                await self.hass.config_entries.async_reload(reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(step_id="reauth_confirm", errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        if user_input:
            try:
                device_info = await self._async_try_connect(user_input[CONF_IP_ADDRESS])

            except RecoverableError as ex:
                LOGGER.error(ex)
                errors = {"base": ex.error_code}
            else:
                await self.async_set_unique_id(
                    f"{device_info.product_type}_{device_info.serial}"
                )
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )
        reconfigure_entry = self._get_reconfigure_entry()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_IP_ADDRESS,
                        default=reconfigure_entry.data.get(CONF_IP_ADDRESS),
                    ): TextSelector(),
                }
            ),
            description_placeholders={
                "title": reconfigure_entry.title,
            },
            errors=errors,
        )

    @staticmethod
    async def _async_try_connect(ip_address: str) -> Device:
        """Try to connect.

        Make connection with device to test the connection
        and to get info for unique_id.
        """
<<<<<<< HEAD
        api: HomeWizardEnergy
        
=======

        api: HomeWizardEnergy

>>>>>>> fd945ced06f (Update quality_scale)
        # Determine if device is v1 or v2 capable
        if await has_v2_api(ip_address):
            api = HomeWizardEnergyV2(ip_address)
        else:
            api = HomeWizardEnergyV1(ip_address)

        try:
            return await api.device()

        except DisabledError as ex:
            raise RecoverableError(
                "API disabled, API must be enabled in the app", "api_not_enabled"
            ) from ex

        except UnsupportedError as ex:
            LOGGER.error("API version unsuppored")
            raise AbortFlow("unsupported_api_version") from ex

        except RequestError as ex:
            raise RecoverableError(
                "Device unreachable or unexpected response", "network_error"
            ) from ex

        except UnauthorizedError as ex:
            raise UnauthorizedError("Unauthorized") from ex

        except UnauthorizedError as ex:
            raise UnauthorizedError("Unauthorized") from ex

        except Exception as ex:
            LOGGER.exception("Unexpected exception")
            raise AbortFlow("unknown_error") from ex

        finally:
            await api.close()


class RecoverableError(HomeAssistantError):
    """Raised when a connection has been failed but can be retried."""

    def __init__(self, message: str, error_code: str) -> None:
        """Init RecoverableError."""
        super().__init__(message)
        self.error_code = error_code
