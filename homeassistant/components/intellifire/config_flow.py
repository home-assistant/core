"""Config flow for IntelliFire integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientConnectionError
from intellifire4py.cloud_interface import IntelliFireCloudInterface
from intellifire4py.exceptions import LoginError
from intellifire4py.local_api import IntelliFireAPILocal
from intellifire4py.model import IntelliFireCommonFireplaceData
import voluptuous as vol

from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)

from .const import (
    API_MODE_LOCAL,
    CONF_AUTH_COOKIE,
    CONF_CONTROL_MODE,
    CONF_READ_MODE,
    CONF_SERIAL,
    CONF_USER_ID,
    CONF_WEB_CLIENT_ID,
    DOMAIN,
    LOGGER,
)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})

MANUAL_ENTRY_STRING = "IP Address"  # Simplified so it does not have to be translated


@dataclass
class DiscoveredHostInfo:
    """Host info for discovery."""

    ip: str
    serial: str | None


async def _async_poll_local_fireplace_for_serial(
    host: str, dhcp_mode: bool = False
) -> str:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    LOGGER.debug("Instantiating IntellifireAPI with host: [%s]", host)
    api = IntelliFireAPILocal(fireplace_ip=host)
    await api.poll(suppress_warnings=dhcp_mode)
    serial = api.data.serial

    LOGGER.debug("Found a fireplace: %s", serial)

    # Return the serial number which will be used to calculate a unique ID for the device/sensors
    return serial


class IntelliFireConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IntelliFire."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the Config Flow Handler."""

        # DHCP Variables
        self._dhcp_discovered_serial: str = ""  # used only in discovery mode
        self._discovered_host: DiscoveredHostInfo
        self._dhcp_mode = False

        self._not_configured_hosts: list[DiscoveredHostInfo] = []
        self._reauth_needed: DiscoveredHostInfo

        self._configured_serials: list[str] = []

        # Define a cloud api interface we can use
        self.cloud_api_interface = IntelliFireCloudInterface()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start the user flow."""

        current_entries = self._async_current_entries(include_ignore=False)
        self._configured_serials = [
            entry.data[CONF_SERIAL] for entry in current_entries
        ]

        return await self.async_step_cloud_api()

    async def async_step_cloud_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Authenticate against IFTAPI Cloud in order to see configured devices.

        Local control of IntelliFire devices requires that the user download the correct API KEY which is only available on the cloud. Cloud control of the devices requires the user has at least once authenticated against the cloud and a set of cookie variables have been stored locally.

        """
        errors: dict[str, str] = {}
        LOGGER.debug("STEP: cloud_api")

        if user_input is not None:
            try:
                async with self.cloud_api_interface as cloud_interface:
                    await cloud_interface.login_with_credentials(
                        username=user_input[CONF_USERNAME],
                        password=user_input[CONF_PASSWORD],
                    )

                # If login was successful pass username/password to next step
                return await self.async_step_pick_cloud_device()
            except LoginError:
                errors["base"] = "api_error"

        return self.async_show_form(
            step_id="cloud_api",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
        )

    async def async_step_pick_cloud_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step to select a device from the cloud.

        We can only get here if we have logged in. If there is only one device available it will be auto-configured,
        else the user will be given a choice to pick a device.
        """
        errors: dict[str, str] = {}
        LOGGER.debug(
            f"STEP: pick_cloud_device: {user_input} - DHCP_MODE[{self._dhcp_mode}"
        )

        if self._dhcp_mode or user_input is not None:
            if self._dhcp_mode:
                serial = self._dhcp_discovered_serial
                LOGGER.debug(f"DHCP Mode detected for serial [{serial}]")
            if user_input is not None:
                serial = user_input[CONF_SERIAL]

            # Run a unique ID Check prior to anything else
            await self.async_set_unique_id(serial)
            self._abort_if_unique_id_configured(updates={CONF_SERIAL: serial})

            # If Serial is Good obtain fireplace and configure
            fireplace = self.cloud_api_interface.user_data.get_data_for_serial(serial)
            if fireplace:
                return await self._async_create_config_entry_from_common_data(
                    fireplace=fireplace
                )

        # Parse User Data to see if we auto-configure or prompt for selection:
        user_data = self.cloud_api_interface.user_data

        available_fireplaces: list[IntelliFireCommonFireplaceData] = [
            fp
            for fp in user_data.fireplaces
            if fp.serial not in self._configured_serials
        ]

        # Abort if all devices have been configured
        if not available_fireplaces:
            return self.async_abort(reason="no_available_devices")

        # If there is a single fireplace configure it
        if len(available_fireplaces) == 1:
            return await self._async_create_config_entry_from_common_data(
                fireplace=available_fireplaces[0]
            )

        return self.async_show_form(
            step_id="pick_cloud_device",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERIAL): vol.In(
                        [fp.serial for fp in available_fireplaces]
                    )
                }
            ),
        )

    async def _async_create_config_entry_from_common_data(
        self, fireplace: IntelliFireCommonFireplaceData
    ) -> ConfigFlowResult:
        """Construct a config entry based on an object of IntelliFireCommonFireplaceData."""

        data = {
            CONF_IP_ADDRESS: fireplace.ip_address,
            CONF_API_KEY: fireplace.api_key,
            CONF_SERIAL: fireplace.serial,
            CONF_AUTH_COOKIE: fireplace.auth_cookie,
            CONF_WEB_CLIENT_ID: fireplace.web_client_id,
            CONF_USER_ID: fireplace.user_id,
            CONF_USERNAME: self.cloud_api_interface.user_data.username,
            CONF_PASSWORD: self.cloud_api_interface.user_data.password,
        }

        options = {CONF_READ_MODE: API_MODE_LOCAL, CONF_CONTROL_MODE: API_MODE_LOCAL}

        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data, options=options
            )
        return self.async_create_entry(
            title=f"Fireplace {fireplace.serial}", data=data, options=options
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        LOGGER.debug("STEP: reauth")

        # populate the expected vars
        self._dhcp_discovered_serial = self._get_reauth_entry().data[CONF_SERIAL]

        placeholders = {"serial": self._dhcp_discovered_serial}
        self.context["title_placeholders"] = placeholders

        return await self.async_step_cloud_api()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP Discovery."""
        self._dhcp_mode = True

        # Run validation logic on ip
        ip_address = discovery_info.ip
        LOGGER.debug("STEP: dhcp for ip_address %s", ip_address)

        self._async_abort_entries_match({CONF_IP_ADDRESS: ip_address})
        try:
            self._dhcp_discovered_serial = await _async_poll_local_fireplace_for_serial(
                ip_address, dhcp_mode=True
            )
        except (ConnectionError, ClientConnectionError):
            LOGGER.debug(
                "DHCP Discovery has determined %s is not an IntelliFire device",
                ip_address,
            )
            return self.async_abort(reason="not_intellifire_device")

        return await self.async_step_cloud_api()
