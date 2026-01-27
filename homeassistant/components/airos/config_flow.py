"""Config flow for the Ubiquiti airOS integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

from airos.discovery import airos_discover_devices
from airos.exceptions import (
    AirOSConnectionAuthenticationError,
    AirOSConnectionSetupError,
    AirOSDataMissingError,
    AirOSDeviceConnectionError,
    AirOSEndpointError,
    AirOSKeyDataMissingError,
    AirOSListenerError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
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

from .const import (
    DEFAULT_SSL,
    DEFAULT_USERNAME,
    DEFAULT_VERIFY_SSL,
    DEVICE_NAME,
    DOMAIN,
    HOSTNAME,
    IP_ADDRESS,
    MAC_ADDRESS,
    SECTION_ADVANCED_SETTINGS,
)
from .coordinator import AirOS8

_LOGGER = logging.getLogger(__name__)

# Discovery duration in seconds, airOS announces every 20 seconds
DISCOVER_INTERVAL: int = 30

STEP_DISCOVERY_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
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

STEP_MANUAL_DATA_SCHEMA = STEP_DISCOVERY_DATA_SCHEMA.extend(
    {vol.Required(CONF_HOST): str}
)


class AirOSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ubiquiti airOS."""

    VERSION = 2
    MINOR_VERSION = 1

    _discovery_task: asyncio.Task | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self.airos_device: AirOS8
        self.errors: dict[str, str] = {}
        self.discovered_devices: dict[str, dict[str, Any]] = {}
        self.discovery_abort_reason: str | None = None
        self.selected_device_info: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        self.errors = {}

        return self.async_show_menu(
            step_id="user", menu_options=["discovery", "manual"]
        )

    async def async_step_manual(
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
            step_id="manual", data_schema=STEP_MANUAL_DATA_SCHEMA, errors=self.errors
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

            if self.source in [SOURCE_REAUTH, SOURCE_RECONFIGURE]:
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

    async def async_step_reconfigure(
        self,
        user_input: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reconfiguration of airOS."""
        self.errors = {}
        entry = self._get_reconfigure_entry()
        current_data = entry.data

        if user_input is not None:
            validate_data = {**current_data, **user_input}
            if await self._validate_and_get_device_info(config_data=validate_data):
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=validate_data,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    ),
                    vol.Required(SECTION_ADVANCED_SETTINGS): section(
                        vol.Schema(
                            {
                                vol.Required(
                                    CONF_SSL,
                                    default=current_data[SECTION_ADVANCED_SETTINGS][
                                        CONF_SSL
                                    ],
                                ): bool,
                                vol.Required(
                                    CONF_VERIFY_SSL,
                                    default=current_data[SECTION_ADVANCED_SETTINGS][
                                        CONF_VERIFY_SSL
                                    ],
                                ): bool,
                            }
                        ),
                        {"collapsed": True},
                    ),
                }
            ),
            errors=self.errors,
        )

    async def async_step_discovery(
        self,
        discovery_info: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Start the discovery process."""
        if self._discovery_task and self._discovery_task.done():
            self._discovery_task = None

            # Handle appropriate 'errors' as abort through progress_done
            if self.discovery_abort_reason:
                return self.async_show_progress_done(
                    next_step_id=self.discovery_abort_reason
                )

            # Abort through progress_done if no devices were found
            if not self.discovered_devices:
                _LOGGER.debug(
                    "No (new or unconfigured) airOS devices found during discovery"
                )
                return self.async_show_progress_done(
                    next_step_id="discovery_no_devices"
                )

            # Skip selecting a device if only one new/unconfigured device was found
            if len(self.discovered_devices) == 1:
                self.selected_device_info = list(self.discovered_devices.values())[0]
                return self.async_show_progress_done(next_step_id="configure_device")

            return self.async_show_progress_done(next_step_id="select_device")

        if not self._discovery_task:
            self.discovered_devices = {}
            self._discovery_task = self.hass.async_create_task(
                self._async_run_discovery_with_progress()
            )

        # Show the progress bar and wait for discovery to complete
        return self.async_show_progress(
            step_id="discovery",
            progress_action="discovering",
            progress_task=self._discovery_task,
            description_placeholders={"seconds": str(DISCOVER_INTERVAL)},
        )

    async def async_step_select_device(
        self,
        discovery_info: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Select a discovered device."""
        if discovery_info is not None:
            selected_mac = discovery_info[MAC_ADDRESS]
            self.selected_device_info = self.discovered_devices[selected_mac]
            return await self.async_step_configure_device()

        list_options = {
            mac: f"{device.get(HOSTNAME, mac)} ({device.get(IP_ADDRESS, DEVICE_NAME)})"
            for mac, device in self.discovered_devices.items()
        }

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema({vol.Required(MAC_ADDRESS): vol.In(list_options)}),
        )

    async def async_step_configure_device(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure the selected device."""
        self.errors = {}

        if user_input is not None:
            config_data = {
                **user_input,
                CONF_HOST: self.selected_device_info[IP_ADDRESS],
            }
            validated_info = await self._validate_and_get_device_info(config_data)

            if validated_info:
                return self.async_create_entry(
                    title=validated_info["title"],
                    data=validated_info["data"],
                )

        device_name = self.selected_device_info.get(
            HOSTNAME, self.selected_device_info.get(IP_ADDRESS, DEVICE_NAME)
        )
        return self.async_show_form(
            step_id="configure_device",
            data_schema=STEP_DISCOVERY_DATA_SCHEMA,
            errors=self.errors,
            description_placeholders={"device_name": device_name},
        )

    async def _async_run_discovery_with_progress(self) -> None:
        """Run discovery with an embedded progress update loop."""
        progress_bar = self.hass.async_create_task(self._async_update_progress_bar())

        known_mac_addresses = {
            entry.unique_id.lower()
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.unique_id
        }

        try:
            devices = await airos_discover_devices(DISCOVER_INTERVAL)
        except AirOSEndpointError:
            self.discovery_abort_reason = "discovery_detect_error"
        except AirOSListenerError:
            self.discovery_abort_reason = "discovery_listen_error"
        except Exception:
            self.discovery_abort_reason = "discovery_failed"
            _LOGGER.exception("An error occurred during discovery")
        else:
            self.discovered_devices = {
                mac_addr: info
                for mac_addr, info in devices.items()
                if mac_addr.lower() not in known_mac_addresses
            }
            _LOGGER.debug(
                "Discovery task finished. Found %s new devices",
                len(self.discovered_devices),
            )
        finally:
            progress_bar.cancel()

    async def _async_update_progress_bar(self) -> None:
        """Update progress bar every second."""
        try:
            for i in range(DISCOVER_INTERVAL):
                progress = (i + 1) / DISCOVER_INTERVAL
                self.async_update_progress(progress)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def async_step_discovery_no_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort if discovery finds no (unconfigured) devices."""
        return self.async_abort(reason="no_devices_found")

    async def async_step_discovery_listen_error(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort if discovery is unable to listen on the port."""
        return self.async_abort(reason="listen_error")

    async def async_step_discovery_detect_error(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort if discovery receives incorrect broadcasts."""
        return self.async_abort(reason="detect_error")

    async def async_step_discovery_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort if discovery fails for other reasons."""
        return self.async_abort(reason="discovery_failed")
