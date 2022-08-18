"""Config flow to configure the LaMetric integration."""
from __future__ import annotations

from ipaddress import ip_address
import logging
from typing import Any

from demetriek import (
    CloudDevice,
    LaMetricCloud,
    LaMetricConnectionError,
    LaMetricDevice,
    Model,
    Notification,
    NotificationIconType,
    NotificationSound,
    Simple,
    Sound,
)
import voluptuous as vol
from yarl import URL

from homeassistant.components.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)
from homeassistant.const import CONF_API_KEY, CONF_DEVICE, CONF_HOST, CONF_MAC
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util.network import is_link_local

from .const import DOMAIN, LOGGER


class LaMetricFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a LaMetric config flow."""

    DOMAIN = DOMAIN
    VERSION = 1

    devices: dict[str, CloudDevice]
    discovered_host: str
    discovered_serial: str
    discovered: bool = False

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": "basic devices_read"}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        return await self.async_step_choice_enter_manual_or_fetch_cloud()

    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> FlowResult:
        """Handle a flow initiated by SSDP discovery."""
        url = URL(discovery_info.ssdp_location or "")
        if url.host is None or not (
            serial := discovery_info.upnp.get(ATTR_UPNP_SERIAL)
        ):
            return self.async_abort(reason="invalid_discovery_info")

        if is_link_local(ip_address(url.host)):
            return self.async_abort(reason="link_local_address")

        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured(updates={CONF_HOST: url.host})

        self.context.update(
            {
                "title_placeholders": {
                    "name": discovery_info.upnp.get(
                        ATTR_UPNP_FRIENDLY_NAME, "LaMetric TIME"
                    ),
                },
                "configuration_url": "https://developer.lametric.com",
            }
        )

        self.discovered = True
        self.discovered_host = str(url.host)
        self.discovered_serial = serial
        return await self.async_step_choice_enter_manual_or_fetch_cloud()

    async def async_step_choice_enter_manual_or_fetch_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user's choice of entering the manual credentials or fetching the cloud credentials."""
        return self.async_show_menu(
            step_id="choice_enter_manual_or_fetch_cloud",
            menu_options=["pick_implementation", "manual_entry"],
        )

    async def async_step_manual_entry(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user's choice of entering the device manually."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if self.discovered:
                host = self.discovered_host
            else:
                host = user_input[CONF_HOST]

            try:
                return await self._async_step_create_entry(
                    host, user_input[CONF_API_KEY]
                )
            except AbortFlow as ex:
                raise ex
            except LaMetricConnectionError as ex:
                LOGGER.error("Error connecting to LaMetric: %s", ex)
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected error occurred")
                errors["base"] = "unknown"

        # Don't ask for a host if it was discovered
        schema = {
            vol.Required(CONF_API_KEY): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            )
        }
        if not self.discovered:
            schema = {vol.Required(CONF_HOST): TextSelector()} | schema

        return self.async_show_form(
            step_id="manual_entry",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_cloud_fetch_devices(self, data: dict[str, Any]) -> FlowResult:
        """Fetch information about devices from the cloud."""
        lametric = LaMetricCloud(
            token=data["token"]["access_token"],
            session=async_get_clientsession(self.hass),
        )
        self.devices = {
            device.serial_number: device
            for device in sorted(await lametric.devices(), key=lambda d: d.name)
        }

        if not self.devices:
            return self.async_abort(reason="no_devices")

        return await self.async_step_cloud_select_device()

    async def async_step_cloud_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device selection from devices offered by the cloud."""
        if self.discovered:
            user_input = {CONF_DEVICE: self.discovered_serial}
        elif len(self.devices) == 1:
            user_input = {CONF_DEVICE: list(self.devices.values())[0].serial_number}

        errors: dict[str, str] = {}
        if user_input is not None:
            device = self.devices[user_input[CONF_DEVICE]]
            try:
                return await self._async_step_create_entry(
                    str(device.ip), device.api_key
                )
            except AbortFlow as ex:
                raise ex
            except LaMetricConnectionError as ex:
                LOGGER.error("Error connecting to LaMetric: %s", ex)
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected error occurred")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="cloud_select_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): SelectSelector(
                        SelectSelectorConfig(
                            mode=SelectSelectorMode.DROPDOWN,
                            options=[
                                SelectOptionDict(
                                    value=device.serial_number,
                                    label=device.name,
                                )
                                for device in self.devices.values()
                            ],
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def _async_step_create_entry(self, host: str, api_key: str) -> FlowResult:
        """Create entry."""
        lametric = LaMetricDevice(
            host=host,
            api_key=api_key,
            session=async_get_clientsession(self.hass),
        )

        device = await lametric.device()

        await self.async_set_unique_id(device.serial_number)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: lametric.host, CONF_API_KEY: lametric.api_key}
        )

        await lametric.notify(
            notification=Notification(
                icon_type=NotificationIconType.INFO,
                model=Model(
                    cycles=2,
                    frames=[Simple(text="Connected to Home Assistant!", icon=7956)],
                    sound=Sound(id=NotificationSound.WIN),
                ),
            )
        )

        return self.async_create_entry(
            title=device.name,
            data={
                CONF_API_KEY: lametric.api_key,
                CONF_HOST: lametric.host,
                CONF_MAC: device.wifi.mac,
            },
        )

    # Replace OAuth create entry with a fetch devices step
    # LaMetric only use OAuth to get device information, but doesn't
    # use it later on.
    async_oauth_create_entry = async_step_cloud_fetch_devices
