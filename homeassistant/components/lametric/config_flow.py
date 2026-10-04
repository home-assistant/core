"""Config flow to configure the LaMetric integration."""

import asyncio
from collections.abc import Mapping
from ipaddress import ip_address
import logging
from typing import TYPE_CHECKING, Any, override

from demetriek import (
    AuthChallenge,
    CloudDevice,
    LaMetricAuthenticationError,
    LaMetricCloud,
    LaMetricConnectionError,
    LaMetricDevice,
    LaMetricError,
    LaMetricLocalAuth,
    Model,
    Notification,
    NotificationIconType,
    NotificationPriority,
    NotificationSound,
    Simple,
    Sound,
)
import probatio
from yarl import URL

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_DEVICE, CONF_HOST, CONF_MAC
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)
from homeassistant.util.network import is_link_local

from .const import DOMAIN, LOGGER

DEVICES_URL = "https://developer.lametric.com/user/devices"

# How often to check whether the button on the device has been pressed.
BUTTON_POLL_INTERVAL = 1


class ButtonNotPressed(Exception):
    """The button on the device was not pressed in time."""


class LaMetricFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a LaMetric config flow."""

    DOMAIN = DOMAIN
    VERSION = 1

    devices: dict[str, CloudDevice]
    button_challenge: AuthChallenge
    button_error: str | None = None
    button_host: str
    button_task: asyncio.Task[str] | None = None
    discovered_host: str
    discovered_serial: str
    discovered: bool = False

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return LOGGER

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": "basic devices_read"}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        return await self.async_step_choice_enter_manual_or_fetch_cloud()

    @override
    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication with LaMetric."""
        return await self.async_step_choice_enter_manual_or_fetch_cloud()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the host and API key of a device."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            lametric = LaMetricDevice(
                host=user_input[CONF_HOST],
                api_key=user_input[CONF_API_KEY],
                session=async_get_clientsession(self.hass),
            )
            try:
                device = await lametric.device()
            except LaMetricAuthenticationError:
                errors["base"] = "invalid_auth"
            except LaMetricConnectionError as ex:
                LOGGER.error("Error connecting to LaMetric: %s", ex)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error occurred")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_API_KEY: user_input[CONF_API_KEY],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_HOST): TextSelector(),
                        probatio.Required(probatio.Secret(CONF_API_KEY)): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.PASSWORD)
                        ),
                    }
                ),
                {CONF_HOST: reconfigure_entry.data[CONF_HOST]},
            ),
            description_placeholders={"devices_url": DEVICES_URL},
            errors=errors,
        )

    async def async_step_choice_enter_manual_or_fetch_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user's choice.

        Either enter the manual credentials or fetch the cloud credentials.
        """
        return self.async_show_menu(
            step_id="choice_enter_manual_or_fetch_cloud",
            menu_options=["pick_implementation", "manual_entry", "press_button"],
        )

    async def async_step_manual_entry(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user's choice of entering the device manually."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if self.discovered:
                host = self.discovered_host
            elif self.source == SOURCE_REAUTH:
                host = self._get_reauth_entry().data[CONF_HOST]
            else:
                host = user_input[CONF_HOST]

            try:
                return await self._async_step_create_entry(
                    host, user_input[CONF_API_KEY]
                )
            except AbortFlow:
                raise
            except LaMetricConnectionError as ex:
                LOGGER.error("Error connecting to LaMetric: %s", ex)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error occurred")
                errors["base"] = "unknown"

        # Don't ask for a host if it was discovered
        schema = {
            probatio.Required(probatio.Secret(CONF_API_KEY)): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            )
        }
        if not self.discovered and self.source != SOURCE_REAUTH:
            schema = {probatio.Required(CONF_HOST): TextSelector()} | schema

        return self.async_show_form(
            step_id="manual_entry",
            data_schema=probatio.Schema(schema),
            description_placeholders={
                "devices_url": DEVICES_URL,
            },
            errors=errors,
        )

    async def async_step_press_button(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle getting the API key from the device, with a press on its button.

        Devices from 2022 onward hand out their API key locally, after someone
        presses the button on top of the device. No LaMetric account needed.
        """
        errors: dict[str, str] = {}
        if self.button_error:
            errors["base"] = self.button_error
            self.button_error = None

        if user_input is not None:
            self.button_host = user_input[CONF_HOST]
            auth = LaMetricLocalAuth(
                host=self.button_host, session=async_get_clientsession(self.hass)
            )
            try:
                self.button_challenge = await auth.request_challenge()
            except LaMetricConnectionError as ex:
                LOGGER.error("Error connecting to LaMetric: %s", ex)
                errors["base"] = "cannot_connect"
            except LaMetricError:
                # A device without this flow, like an LM 37X8, ends up here.
                errors["base"] = "button_not_supported"
            else:
                self.button_task = self.hass.async_create_task(
                    self._async_wait_for_button(auth)
                )
                return await self.async_step_press_button_wait()

        host = None
        if self.discovered:
            host = self.discovered_host
        elif self.source == SOURCE_REAUTH:
            host = self._get_reauth_entry().data[CONF_HOST]

        return self.async_show_form(
            step_id="press_button",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema({probatio.Required(CONF_HOST): TextSelector()}),
                {CONF_HOST: host},
            ),
            errors=errors,
        )

    async def _async_wait_for_button(self, auth: LaMetricLocalAuth) -> str:
        """Wait for the button on the device to be pressed, and get the API key."""
        challenge = self.button_challenge
        while challenge.state == "in-progress":
            await asyncio.sleep(BUTTON_POLL_INTERVAL)
            challenge = await auth.challenge(challenge_id=challenge.challenge_id)

        if not challenge.resolved:
            raise ButtonNotPressed
        return await auth.api_key(challenge_id=challenge.challenge_id)

    async def async_step_press_button_wait(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for the button on the device to be pressed."""
        if TYPE_CHECKING:
            assert self.button_task is not None

        if not self.button_task.done():
            return self.async_show_progress(
                step_id="press_button_wait",
                progress_action="press_button",
                description_placeholders={
                    "duration": str(self.button_challenge.duration)
                },
                progress_task=self.button_task,
            )

        if isinstance(exception := self.button_task.exception(), ButtonNotPressed):
            return self.async_show_progress_done(next_step_id="press_button_timeout")
        if exception is not None:
            LOGGER.error("Error getting the API key from LaMetric: %s", exception)
            self.button_error = (
                "cannot_connect"
                if isinstance(exception, LaMetricConnectionError)
                else "unknown"
            )
            return self.async_show_progress_done(next_step_id="press_button")
        return self.async_show_progress_done(next_step_id="press_button_finish")

    async def async_step_press_button_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the button not being pressed in time."""
        if user_input is None:
            return self.async_show_form(step_id="press_button_timeout")
        return await self.async_step_press_button()

    async def async_step_press_button_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the device with the API key it handed out."""
        if TYPE_CHECKING:
            assert self.button_task is not None

        try:
            return await self._async_step_create_entry(
                self.button_host, self.button_task.result()
            )
        except AbortFlow:
            raise
        except LaMetricConnectionError as ex:
            LOGGER.error("Error connecting to LaMetric: %s", ex)
            self.button_error = "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error occurred")
            self.button_error = "unknown"
        return await self.async_step_press_button()

    async def async_step_cloud_fetch_devices(
        self, data: dict[str, Any]
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Handle device selection from devices offered by the cloud."""
        if self.discovered:
            user_input = {CONF_DEVICE: self.discovered_serial}
        elif self.source == SOURCE_REAUTH:
            reauth_unique_id = self._get_reauth_entry().unique_id
            if reauth_unique_id not in self.devices:
                return self.async_abort(reason="reauth_device_not_found")
            user_input = {CONF_DEVICE: reauth_unique_id}
        elif len(self.devices) == 1:
            user_input = {CONF_DEVICE: list(self.devices.values())[0].serial_number}

        errors: dict[str, str] = {}
        if user_input is not None:
            device = self.devices[user_input[CONF_DEVICE]]
            try:
                return await self._async_step_create_entry(
                    str(device.ip), device.api_key
                )
            except AbortFlow:
                raise
            except LaMetricConnectionError as ex:
                LOGGER.error("Error connecting to LaMetric: %s", ex)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error occurred")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="cloud_select_device",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_DEVICE): SelectSelector(
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

    async def _async_step_create_entry(
        self, host: str, api_key: str
    ) -> ConfigFlowResult:
        """Create entry."""
        lametric = LaMetricDevice(
            host=host,
            api_key=api_key,
            session=async_get_clientsession(self.hass),
        )

        device = await lametric.device()

        await self.async_set_unique_id(
            device.serial_number,
            raise_on_progress=False,
        )
        if self.source == SOURCE_REAUTH:
            # The host can differ from the one set up, so make sure it is
            # still the same device before touching its entry.
            self._abort_if_unique_id_mismatch()
        else:
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: lametric.host, CONF_API_KEY: lametric.api_key}
            )

        notify_sound: Sound | None = None
        if device.model != "sa5":
            notify_sound = Sound(sound=NotificationSound.WIN)

        await lametric.notify(
            notification=Notification(
                priority=NotificationPriority.CRITICAL,
                icon_type=NotificationIconType.INFO,
                model=Model(
                    cycles=2,
                    frames=[Simple(text="Connected to Home Assistant!", icon=7956)],
                    sound=notify_sound,
                ),
            )
        )

        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates={
                    CONF_HOST: lametric.host,
                    CONF_API_KEY: lametric.api_key,
                },
            )

        return self.async_create_entry(
            title=device.name,
            data={
                CONF_API_KEY: lametric.api_key,
                CONF_HOST: lametric.host,
                CONF_MAC: device.wifi.mac,
            },
        )

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle dhcp discovery to update existing entries."""
        mac = format_mac(discovery_info.macaddress)
        for entry in self._async_current_entries():
            if (entry_mac := entry.data.get(CONF_MAC)) and format_mac(entry_mac) == mac:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data=entry.data | {CONF_HOST: discovery_info.ip},
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(entry.entry_id)
                )
                return self.async_abort(reason="already_configured")

        return self.async_abort(reason="unknown")

    # Replace OAuth create entry with a fetch devices step
    # LaMetric only use OAuth to get device information, but doesn't
    # use it later on.
    async_oauth_create_entry = async_step_cloud_fetch_devices
