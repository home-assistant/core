"""Config flow for Airgradient."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, override

from airgradient import (
    AirGradientClient,
    AirGradientError,
    AirGradientParseError,
    ApiVersion,
    ConfigurationControl,
)
from awesomeversion import AwesomeVersion, AwesomeVersionException
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

MIN_VERSION = AwesomeVersion("3.1.1")


class AirGradientConfigFlow(ConfigFlow, domain=DOMAIN):
    """AirGradient config flow."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self.client: AirGradientClient | None = None

    async def set_configuration_source(self) -> None:
        """Set configuration source to local if it hasn't been set yet."""
        if TYPE_CHECKING:
            assert self.client is not None
        config = await self.client.get_config()
        if config.configuration_control is ConfigurationControl.NOT_INITIALIZED:
            await self.client.set_configuration_control(ConfigurationControl.LOCAL)

    def _has_supported_firmware(self, firmware_version: str) -> bool:
        """Return whether the detected device has supported firmware."""
        if TYPE_CHECKING:
            assert self.client is not None
        if self.client.api_version is not ApiVersion.LEGACY:
            return True
        try:
            return AwesomeVersion(firmware_version) >= MIN_VERSION
        except AwesomeVersionException:
            return False

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        properties = discovery_info.properties
        self.data[CONF_HOST] = host = discovery_info.host
        model = properties["model"]
        serial_number = properties["serialno"]
        firmware_version = properties["fw_ver"]

        self.data[CONF_MODEL] = model
        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        session = async_get_clientsession(self.hass)
        self.client = AirGradientClient(
            host,
            session=session,
            api_version=ApiVersion.V1 if properties.get("api") == "1" else None,
        )
        try:
            await self.client.get_current_measures()
        except AirGradientParseError:
            return self.async_abort(reason="invalid_version")
        except AirGradientError:
            return self.async_abort(reason="cannot_connect")

        if not self._has_supported_firmware(firmware_version):
            return self.async_abort(reason="invalid_version")

        self.context["title_placeholders"] = {
            "model": self.data[CONF_MODEL],
        }
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self.set_configuration_source()
            except AirGradientError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=self.data[CONF_MODEL],
                    data={CONF_HOST: self.data[CONF_HOST]},
                )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "model": self.data[CONF_MODEL],
            },
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input:
            session = async_get_clientsession(self.hass)
            self.client = AirGradientClient(user_input[CONF_HOST], session=session)
            try:
                current_measures = await self.client.get_current_measures()
            except AirGradientParseError:
                return self.async_abort(reason="invalid_version")
            except AirGradientError:
                errors["base"] = "cannot_connect"
            else:
                if not self._has_supported_firmware(current_measures.firmware_version):
                    return self.async_abort(reason="invalid_version")
                await self.async_set_unique_id(
                    current_measures.serial_number, raise_on_progress=False
                )
                if self.source == SOURCE_USER:
                    self._abort_if_unique_id_configured()
                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch()
                try:
                    await self.set_configuration_source()
                except AirGradientError:
                    errors["base"] = "cannot_connect"
                else:
                    if self.source == SOURCE_USER:
                        return self.async_create_entry(
                            title=current_measures.model,
                            data={CONF_HOST: user_input[CONF_HOST]},
                        )
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data={CONF_HOST: user_input[CONF_HOST]},
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        return await self.async_step_user()
