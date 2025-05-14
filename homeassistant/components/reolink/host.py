"""Module which encapsulates the NVR/camera API and subscription."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Mapping
import logging
from time import time
from typing import Any, Literal

import aiohttp
from aiohttp.web import Request
from reolink_aio.api import ALLOWED_SPECIAL_CHARS, Host
from reolink_aio.baichuan import DEFAULT_BC_PORT
from reolink_aio.enums import SubType
from reolink_aio.exceptions import NotSupportedError, ReolinkError, SubscriptionError

from homeassistant.components import webhook
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.storage import Store
from homeassistant.util.ssl import SSLCipherList

from .const import CONF_BC_PORT, CONF_SUPPORTS_PRIVACY_MODE, CONF_USE_HTTPS, DOMAIN
from .exceptions import (
    PasswordIncompatible,
    ReolinkSetupException,
    ReolinkWebhookException,
    UserNotAdmin,
)
from .util import ReolinkConfigEntry, get_store

DEFAULT_TIMEOUT = 30
FIRST_TCP_PUSH_TIMEOUT = 10
FIRST_ONVIF_TIMEOUT = 10
FIRST_ONVIF_LONG_POLL_TIMEOUT = 90
SUBSCRIPTION_RENEW_THRESHOLD = 300
POLL_INTERVAL_NO_PUSH = 5
LONG_POLL_COOLDOWN = 0.75
LONG_POLL_ERROR_COOLDOWN = 30

# Conserve battery by not waking the battery cameras each minute during normal update
# Most props are cached in the Home Hub and updated, but some are skipped
BATTERY_WAKE_UPDATE_INTERVAL = 3600  # seconds

_LOGGER = logging.getLogger(__name__)


class ReolinkHost:
    """The implementation of the Reolink Host class."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: Mapping[str, Any],
        options: Mapping[str, Any],
        config_entry: ReolinkConfigEntry | None = None,
    ) -> None:
        """Initialize Reolink Host. Could be either NVR, or Camera."""
        self._hass: HomeAssistant = hass
        self._config_entry = config_entry
        self._config = config
        self._unique_id: str = ""

        def get_aiohttp_session() -> aiohttp.ClientSession:
            """Return the HA aiohttp session."""
            return async_get_clientsession(
                hass,
                verify_ssl=False,
                ssl_cipher=SSLCipherList.INSECURE,
            )

        self._api = Host(
            config[CONF_HOST],
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            port=config.get(CONF_PORT),
            use_https=config.get(CONF_USE_HTTPS),
            protocol=options[CONF_PROTOCOL],
            timeout=DEFAULT_TIMEOUT,
            aiohttp_get_session_callback=get_aiohttp_session,
            bc_port=config.get(CONF_BC_PORT, DEFAULT_BC_PORT),
        )

        self.last_wake: float = 0
        self.update_cmd: defaultdict[str, defaultdict[int | None, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self.firmware_ch_list: list[int | None] = []

        self.starting: bool = True
        self.privacy_mode: bool | None = None
        self.credential_errors: int = 0

        self.webhook_id: str | None = None
        self._onvif_push_supported: bool = True
        self._onvif_long_poll_supported: bool = True
        self._base_url: str = ""
        self._webhook_url: str = ""
        self._webhook_reachable: bool = False
        self._long_poll_received: bool = False
        self._long_poll_error: bool = False
        self._cancel_poll: CALLBACK_TYPE | None = None
        self._cancel_tcp_push_check: CALLBACK_TYPE | None = None
        self._cancel_onvif_check: CALLBACK_TYPE | None = None
        self._cancel_long_poll_check: CALLBACK_TYPE | None = None
        self._poll_job = HassJob(self._async_poll_all_motion, cancel_on_shutdown=True)
        self._fast_poll_error: bool = False
        self._long_poll_task: asyncio.Task | None = None
        self._lost_subscription_start: bool = False
        self._lost_subscription: bool = False
        self.cancel_refresh_privacy_mode: CALLBACK_TYPE | None = None

    @callback
    def async_register_update_cmd(self, cmd: str, channel: int | None = None) -> None:
        """Register the command to update the state."""
        self.update_cmd[cmd][channel] += 1

    @callback
    def async_unregister_update_cmd(self, cmd: str, channel: int | None = None) -> None:
        """Unregister the command to update the state."""
        self.update_cmd[cmd][channel] -= 1
        if not self.update_cmd[cmd][channel]:
            del self.update_cmd[cmd][channel]
        if not self.update_cmd[cmd]:
            del self.update_cmd[cmd]

    @property
    def unique_id(self) -> str:
        """Create the unique ID, base for all entities."""
        return self._unique_id

    @property
    def api(self) -> Host:
        """Return the API object."""
        return self._api

    async def async_init(self) -> None:
        """Connect to Reolink host."""
        if not self._api.valid_password():
            if (
                len(self._config[CONF_PASSWORD]) >= 32
                and self._config_entry is not None
            ):
                ir.async_create_issue(
                    self._hass,
                    DOMAIN,
                    f"password_too_long_{self._config_entry.entry_id}",
                    is_fixable=True,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="password_too_long",
                    translation_placeholders={"name": self._config_entry.title},
                )

            raise PasswordIncompatible(
                "Reolink password contains incompatible special character or "
                "is too long, please change the password to only contain characters: "
                f"a-z, A-Z, 0-9 or {ALLOWED_SPECIAL_CHARS} "
                "and not be longer than 31 characters"
            )

        store: Store[str] | None = None
        if self._config_entry is not None:
            ir.async_delete_issue(
                self._hass, DOMAIN, f"password_too_long_{self._config_entry.entry_id}"
            )
            store = get_store(self._hass, self._config_entry.entry_id)
            if self._config.get(CONF_SUPPORTS_PRIVACY_MODE) and (
                data := await store.async_load()
            ):
                self._api.set_raw_host_data(data)

        await self._api.get_host_data()

        if self._api.mac_address is None:
            raise ReolinkSetupException("Could not get mac address")

        if not self._api.is_admin:
            raise UserNotAdmin(
                f"User '{self._api.username}' has authorization level "
                f"'{self._api.user_level}', only admin users can change camera settings"
            )

        self.privacy_mode = self._api.baichuan.privacy_mode()

        if (
            store
            and self._api.supported(None, "privacy_mode")
            and not self.privacy_mode
        ):
            _LOGGER.debug(
                "Saving raw host data for next reload in case privacy mode is enabled"
            )
            data = self._api.get_raw_host_data()
            await store.async_save(data)

        onvif_supported = self._api.supported(None, "ONVIF")
        self._onvif_push_supported = onvif_supported
        self._onvif_long_poll_supported = onvif_supported

        enable_rtsp = None
        enable_onvif = None
        enable_rtmp = None

        if not self._api.rtsp_enabled:
            _LOGGER.debug(
                "RTSP is disabled on %s, trying to enable it", self._api.nvr_name
            )
            enable_rtsp = True

        if not self._api.onvif_enabled and onvif_supported:
            _LOGGER.debug(
                "ONVIF is disabled on %s, trying to enable it", self._api.nvr_name
            )
            enable_onvif = True

        if not self._api.rtmp_enabled and self._api.protocol == "rtmp":
            _LOGGER.debug(
                "RTMP is disabled on %s, trying to enable it", self._api.nvr_name
            )
            enable_rtmp = True

        if enable_onvif or enable_rtmp or enable_rtsp:
            try:
                await self._api.set_net_port(
                    enable_onvif=enable_onvif,
                    enable_rtmp=enable_rtmp,
                    enable_rtsp=enable_rtsp,
                )
            except ReolinkError:
                ports = ""
                if enable_rtsp:
                    ports += "RTSP "

                if enable_onvif:
                    ports += "ONVIF "

                if enable_rtmp:
                    ports += "RTMP "

                ir.async_create_issue(
                    self._hass,
                    DOMAIN,
                    "enable_port",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="enable_port",
                    translation_placeholders={
                        "name": self._api.nvr_name,
                        "ports": ports,
                        "info_link": "https://support.reolink.com/hc/en-us/articles/900004435763-How-to-Set-up-Reolink-Ports-Settings-via-Reolink-Client-New-Client-",
                    },
                )
        else:
            ir.async_delete_issue(self._hass, DOMAIN, "enable_port")

        if self._api.supported(None, "UID"):
            self._unique_id = self._api.uid
        else:
            self._unique_id = format_mac(self._api.mac_address)

        try:
            await self._api.baichuan.subscribe_events()
        except ReolinkError:
            await self._async_check_tcp_push()
        else:
            self._cancel_tcp_push_check = async_call_later(
                self._hass, FIRST_TCP_PUSH_TIMEOUT, self._async_check_tcp_push
            )

        ch_list: list[int | None] = [None]
        if self._api.is_nvr:
            ch_list.extend(self._api.channels)
        for ch in ch_list:
            if not self._api.supported(ch, "firmware"):
                continue

            key = ch if ch is not None else "host"
            if self._api.camera_sw_version_update_required(ch):
                ir.async_create_issue(
                    self._hass,
                    DOMAIN,
                    f"firmware_update_{key}",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="firmware_update",
                    translation_placeholders={
                        "required_firmware": self._api.camera_sw_version_required(
                            ch
                        ).version_string,
                        "current_firmware": self._api.camera_sw_version(ch),
                        "model": self._api.camera_model(ch),
                        "hw_version": self._api.camera_hardware_version(ch),
                        "name": self._api.camera_name(ch),
                        "download_link": "https://reolink.com/download-center/",
                    },
                )
            else:
                ir.async_delete_issue(self._hass, DOMAIN, f"firmware_update_{key}")

    async def _async_check_tcp_push(self, *_: Any) -> None:
        """Check the TCP push subscription."""
        if self._api.baichuan.events_active:
            ir.async_delete_issue(self._hass, DOMAIN, "webhook_url")
            self._cancel_tcp_push_check = None
            return

        _LOGGER.debug(
            "Reolink %s, did not receive initial TCP push event after %i seconds",
            self._api.nvr_name,
            FIRST_TCP_PUSH_TIMEOUT,
        )

        if self._onvif_push_supported:
            try:
                await self.subscribe()
            except ReolinkError:
                self._onvif_push_supported = False
                self.unregister_webhook()
                await self._api.unsubscribe()
            else:
                if self._api.supported(None, "initial_ONVIF_state"):
                    _LOGGER.debug(
                        "Waiting for initial ONVIF state on webhook '%s'",
                        self._webhook_url,
                    )
                else:
                    _LOGGER.debug(
                        "Camera model %s most likely does not push its initial state"
                        " upon ONVIF subscription, do not check",
                        self._api.model,
                    )
                self._cancel_onvif_check = async_call_later(
                    self._hass, FIRST_ONVIF_TIMEOUT, self._async_check_onvif
                )

        # start long polling if ONVIF push failed immediately
        if not self._onvif_push_supported and not self._api.baichuan.privacy_mode():
            _LOGGER.debug(
                "Camera model %s does not support ONVIF push, using ONVIF long polling instead",
                self._api.model,
            )
            try:
                await self._async_start_long_polling(initial=True)
            except NotSupportedError:
                _LOGGER.debug(
                    "Camera model %s does not support ONVIF long polling, using fast polling instead",
                    self._api.model,
                )
                self._onvif_long_poll_supported = False
                await self._api.unsubscribe()
                await self._async_poll_all_motion()
            else:
                self._cancel_long_poll_check = async_call_later(
                    self._hass,
                    FIRST_ONVIF_LONG_POLL_TIMEOUT,
                    self._async_check_onvif_long_poll,
                )

        self._cancel_tcp_push_check = None

    async def _async_check_onvif(self, *_: Any) -> None:
        """Check the ONVIF subscription."""
        if self._webhook_reachable:
            ir.async_delete_issue(self._hass, DOMAIN, "webhook_url")
            self._cancel_onvif_check = None
            return
        if self._api.supported(None, "initial_ONVIF_state"):
            _LOGGER.debug(
                "Did not receive initial ONVIF state on webhook '%s' after %i seconds",
                self._webhook_url,
                FIRST_ONVIF_TIMEOUT,
            )

        # ONVIF push is not received, start long polling and schedule check
        await self._async_start_long_polling()
        self._cancel_long_poll_check = async_call_later(
            self._hass, FIRST_ONVIF_LONG_POLL_TIMEOUT, self._async_check_onvif_long_poll
        )

        self._cancel_onvif_check = None

    async def _async_check_onvif_long_poll(self, *_: Any) -> None:
        """Check if ONVIF long polling is working."""
        if not self._long_poll_received:
            _LOGGER.debug(
                "Did not receive state through ONVIF long polling after %i seconds",
                FIRST_ONVIF_LONG_POLL_TIMEOUT,
            )
            ir.async_create_issue(
                self._hass,
                DOMAIN,
                "webhook_url",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="webhook_url",
                translation_placeholders={
                    "name": self._api.nvr_name,
                    "base_url": self._base_url,
                    "network_link": "https://my.home-assistant.io/redirect/network/",
                },
            )

            if self._base_url.startswith("https"):
                ir.async_create_issue(
                    self._hass,
                    DOMAIN,
                    "https_webhook",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="https_webhook",
                    translation_placeholders={
                        "base_url": self._base_url,
                        "network_link": "https://my.home-assistant.io/redirect/network/",
                    },
                )
            else:
                ir.async_delete_issue(self._hass, DOMAIN, "https_webhook")

            if self._hass.config.api is not None and self._hass.config.api.use_ssl:
                ir.async_create_issue(
                    self._hass,
                    DOMAIN,
                    "ssl",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="ssl",
                    translation_placeholders={
                        "ssl_link": "https://www.home-assistant.io/integrations/http/#ssl_certificate",
                        "base_url": self._base_url,
                        "network_link": "https://my.home-assistant.io/redirect/network/",
                        "nginx_link": "https://github.com/home-assistant/addons/tree/master/nginx_proxy",
                    },
                )
            else:
                ir.async_delete_issue(self._hass, DOMAIN, "ssl")
        else:
            ir.async_delete_issue(self._hass, DOMAIN, "webhook_url")
            ir.async_delete_issue(self._hass, DOMAIN, "https_webhook")
            ir.async_delete_issue(self._hass, DOMAIN, "ssl")

        # If no ONVIF push or long polling state is received, start fast polling
        await self._async_poll_all_motion()

        self._cancel_long_poll_check = None

    async def update_states(self) -> None:
        """Call the API of the camera device to update the internal states."""
        wake = False
        if time() - self.last_wake > BATTERY_WAKE_UPDATE_INTERVAL:
            # wake the battery cameras for a complete update
            wake = True
            self.last_wake = time()

        for channel in self._api.channels:
            if self._api.baichuan.privacy_mode(channel):
                await self._api.baichuan.get_privacy_mode(channel)
        if self._api.baichuan.privacy_mode():
            return  # API is shutdown, no need to check states

        await self._api.get_states(cmd_list=self.update_cmd, wake=wake)

    async def disconnect(self) -> None:
        """Disconnect from the API, so the connection will be released."""
        try:
            await self._api.baichuan.unsubscribe_events()
        except ReolinkError as err:
            _LOGGER.error(
                "Reolink error while unsubscribing Baichuan from host %s:%s: %s",
                self._api.host,
                self._api.port,
                err,
            )

        try:
            await self._api.unsubscribe()
        except ReolinkError as err:
            _LOGGER.error(
                "Reolink error while unsubscribing from host %s:%s: %s",
                self._api.host,
                self._api.port,
                err,
            )

        try:
            await self._api.logout()
        except ReolinkError as err:
            _LOGGER.error(
                "Reolink error while logging out for host %s:%s: %s",
                self._api.host,
                self._api.port,
                err,
            )

    async def _async_start_long_polling(self, initial: bool = False) -> None:
        """Start ONVIF long polling task."""
        if self._long_poll_task is None:
            try:
                await self._api.subscribe(sub_type=SubType.long_poll)
            except NotSupportedError as err:
                if initial:
                    raise
                # make sure the long_poll_task is always created to try again later
                if not self._lost_subscription_start:
                    self._lost_subscription_start = True
                    _LOGGER.error(
                        "Reolink %s event long polling subscription lost: %s",
                        self._api.nvr_name,
                        err,
                    )
            except ReolinkError as err:
                # make sure the long_poll_task is always created to try again later
                if not self._lost_subscription_start:
                    self._lost_subscription_start = True
                    _LOGGER.error(
                        "Reolink %s event long polling subscription lost: %s",
                        self._api.nvr_name,
                        err,
                    )
            else:
                self._lost_subscription_start = False
            self._long_poll_task = asyncio.create_task(self._async_long_polling())

    async def _async_stop_long_polling(self) -> None:
        """Stop ONVIF long polling task."""
        if self._long_poll_task is not None:
            self._long_poll_task.cancel()
            self._long_poll_task = None

        try:
            await self._api.unsubscribe(sub_type=SubType.long_poll)
        except ReolinkError as err:
            _LOGGER.error(
                "Reolink error while unsubscribing from host %s:%s: %s",
                self._api.host,
                self._api.port,
                err,
            )

    async def stop(self, *_: Any) -> None:
        """Disconnect the API."""
        if self._cancel_poll is not None:
            self._cancel_poll()
            self._cancel_poll = None
        if self._cancel_tcp_push_check is not None:
            self._cancel_tcp_push_check()
            self._cancel_tcp_push_check = None
        if self._cancel_onvif_check is not None:
            self._cancel_onvif_check()
            self._cancel_onvif_check = None
        if self._cancel_long_poll_check is not None:
            self._cancel_long_poll_check()
            self._cancel_long_poll_check = None
        await self._async_stop_long_polling()
        self.unregister_webhook()
        await self.disconnect()

    async def subscribe(self) -> None:
        """Subscribe to motion events and register the webhook as a callback."""
        if self.webhook_id is None:
            self.register_webhook()

        if self._api.subscribed(SubType.push):
            _LOGGER.debug(
                "Host %s: is already subscribed to webhook %s",
                self._api.host,
                self._webhook_url,
            )
            return

        try:
            await self._api.subscribe(self._webhook_url)
        except NotSupportedError as err:
            self._onvif_push_supported = False
            _LOGGER.debug(err)
            return

        _LOGGER.debug(
            "Host %s: subscribed successfully to webhook %s",
            self._api.host,
            self._webhook_url,
        )

    async def renew(self) -> None:
        """Renew the subscription of motion events (lease time is 15 minutes)."""
        await self._api.baichuan.check_subscribe_events()

        if self._api.baichuan.events_active and self._api.subscribed(SubType.push):
            # TCP push active, unsubscribe from ONVIF push because not needed
            self.unregister_webhook()
            await self._api.unsubscribe()

        if self._api.baichuan.privacy_mode():
            return  # API is shutdown, no need to subscribe

        try:
            if (
                self._onvif_push_supported
                and not self._api.baichuan.events_active
                and self._cancel_tcp_push_check is None
            ):
                await self._renew(SubType.push)

            if self._onvif_long_poll_supported and self._long_poll_task is not None:
                if not self._api.subscribed(SubType.long_poll):
                    _LOGGER.debug("restarting long polling task")
                    # To prevent 5 minute request timeout
                    await self._async_stop_long_polling()
                    await self._async_start_long_polling()
                else:
                    await self._renew(SubType.long_poll)
        except SubscriptionError as err:
            if not self._lost_subscription:
                self._lost_subscription = True
                _LOGGER.error(
                    "Reolink %s event subscription lost: %s",
                    self._api.nvr_name,
                    err,
                )
        else:
            self._lost_subscription = False

    async def _renew(self, sub_type: Literal[SubType.push, SubType.long_poll]) -> None:
        """Execute the renew of the subscription."""
        if not self._api.subscribed(sub_type):
            _LOGGER.debug(
                "Host %s: requested to renew a non-existing Reolink %s subscription, "
                "trying to subscribe from scratch",
                self._api.host,
                sub_type,
            )
            if sub_type == SubType.push:
                await self.subscribe()
                return

        timer = self._api.renewtimer(sub_type)
        _LOGGER.debug(
            "Host %s:%s should renew %s subscription in: %i seconds",
            self._api.host,
            self._api.port,
            sub_type,
            timer,
        )
        if timer > SUBSCRIPTION_RENEW_THRESHOLD:
            return

        if timer > 0:
            try:
                await self._api.renew(sub_type)
            except SubscriptionError as err:
                _LOGGER.debug(
                    "Host %s: error renewing Reolink %s subscription, "
                    "trying to subscribe again: %s",
                    self._api.host,
                    sub_type,
                    err,
                )
            else:
                _LOGGER.debug(
                    "Host %s successfully renewed Reolink %s subscription",
                    self._api.host,
                    sub_type,
                )
                return

        await self._api.subscribe(self._webhook_url, sub_type)

        _LOGGER.debug(
            "Host %s: Reolink %s re-subscription successful after it was expired",
            self._api.host,
            sub_type,
        )

    def register_webhook(self) -> None:
        """Register the webhook for motion events."""
        self.webhook_id = (
            f"{DOMAIN}_{self.unique_id.replace(':', '')}_{webhook.async_generate_id()}"
        )
        event_id = self.webhook_id

        webhook.async_register(
            self._hass, DOMAIN, event_id, event_id, self.handle_webhook
        )

        try:
            self._base_url = get_url(self._hass, prefer_external=False)
        except NoURLAvailableError:
            try:
                self._base_url = get_url(self._hass, prefer_external=True)
            except NoURLAvailableError as err:
                self.unregister_webhook()
                raise ReolinkWebhookException(
                    f"Error registering URL for webhook {event_id}: "
                    "HomeAssistant URL is not available"
                ) from err

        webhook_path = webhook.async_generate_path(event_id)
        self._webhook_url = f"{self._base_url}{webhook_path}"

        _LOGGER.debug("Registered webhook: %s", event_id)

    def unregister_webhook(self) -> None:
        """Unregister the webhook for motion events."""
        if self.webhook_id is None:
            return
        _LOGGER.debug("Unregistering webhook %s", self.webhook_id)
        webhook.async_unregister(self._hass, self.webhook_id)
        self.webhook_id = None

    async def _async_long_polling(self, *_: Any) -> None:
        """Use ONVIF long polling to immediately receive events."""
        # This task will be cancelled once _async_stop_long_polling is called
        while True:
            if self._api.baichuan.events_active or self._webhook_reachable:
                # TCP push or ONVIF push working, stop long polling
                self._long_poll_task = None
                await self._async_stop_long_polling()
                return

            try:
                channels = await self._api.pull_point_request()
            except ReolinkError as ex:
                if not self._long_poll_error and self._api.subscribed(
                    SubType.long_poll
                ):
                    _LOGGER.error("Error while requesting ONVIF pull point: %s", ex)
                    await self._api.unsubscribe(sub_type=SubType.long_poll)
                self._long_poll_error = True
                await asyncio.sleep(LONG_POLL_ERROR_COOLDOWN)
                continue
            except Exception:
                _LOGGER.exception(
                    "Unexpected exception while requesting ONVIF pull point"
                )
                await self._api.unsubscribe(sub_type=SubType.long_poll)
                raise

            self._long_poll_error = False

            if not self._long_poll_received:
                self._long_poll_received = True
                ir.async_delete_issue(self._hass, DOMAIN, "webhook_url")

            self._signal_write_ha_state(channels)

            # Cooldown to prevent CPU over usage on camera freezes
            await asyncio.sleep(LONG_POLL_COOLDOWN)

    async def _async_poll_all_motion(self, *_: Any) -> None:
        """Poll motion and AI states until the first ONVIF push is received."""
        if (
            self._api.baichuan.events_active
            or self._webhook_reachable
            or self._long_poll_received
        ):
            # TCP push, ONVIF push or long polling is working, stop fast polling
            self._cancel_poll = None
            return

        try:
            if self._api.session_active:
                await self._api.get_motion_state_all_ch()
        except ReolinkError as err:
            if not self._fast_poll_error:
                _LOGGER.error(
                    "Reolink error while polling motion state for host %s:%s: %s",
                    self._api.host,
                    self._api.port,
                    err,
                )
            self._fast_poll_error = True
        else:
            if self._api.session_active:
                self._fast_poll_error = False
        finally:
            # schedule next poll
            if not self._hass.is_stopping:
                self._cancel_poll = async_call_later(
                    self._hass, POLL_INTERVAL_NO_PUSH, self._poll_job
                )

        self._signal_write_ha_state()

    async def handle_webhook(
        self, hass: HomeAssistant, webhook_id: str, request: Request
    ) -> None:
        """Read the incoming webhook from Reolink for inbound messages and schedule processing."""
        _LOGGER.debug("Webhook '%s' called", webhook_id)
        data: bytes | None = None
        try:
            data = await request.read()
            if not data:
                _LOGGER.debug(
                    "Webhook '%s' triggered with unknown payload: %s", webhook_id, data
                )
        except ConnectionResetError:
            _LOGGER.debug(
                "Webhook '%s' called, but lost connection before reading message "
                "(ConnectionResetError), issuing poll",
                webhook_id,
            )
            return
        except aiohttp.ClientResponseError:
            _LOGGER.debug(
                "Webhook '%s' called, but could not read the message, issuing poll",
                webhook_id,
            )
            return
        except asyncio.CancelledError:
            _LOGGER.debug(
                "Webhook '%s' called, but lost connection before reading message "
                "(CancelledError), issuing poll",
                webhook_id,
            )
            raise
        finally:
            # We want handle_webhook to return as soon as possible
            # so we process the data in the background, this also shields from cancellation
            hass.async_create_background_task(
                self._process_webhook_data(hass, webhook_id, data),
                "Process Reolink webhook",
            )

    async def _process_webhook_data(
        self, hass: HomeAssistant, webhook_id: str, data: bytes | None
    ) -> None:
        """Process the data from the Reolink webhook."""
        # This task is executed in the background so we need to catch exceptions
        # and log them
        if not self._webhook_reachable:
            self._webhook_reachable = True
            ir.async_delete_issue(self._hass, DOMAIN, "webhook_url")

        try:
            if not data:
                if not await self._api.get_motion_state_all_ch():
                    _LOGGER.error(
                        "Could not poll motion state after losing connection during receiving ONVIF event"
                    )
                    return
                self._signal_write_ha_state()
                return

            message = data.decode("utf-8")
            channels = await self._api.ONVIF_event_callback(message)
        except Exception:
            _LOGGER.exception(
                "Error processing ONVIF event for Reolink %s", self._api.nvr_name
            )
            return

        self._signal_write_ha_state(channels)

    def _signal_write_ha_state(self, channels: list[int] | None = None) -> None:
        """Update the binary sensors with async_write_ha_state."""
        if channels is None:
            async_dispatcher_send(self._hass, f"{self.unique_id}_all", {})
            return

        for channel in channels:
            async_dispatcher_send(self._hass, f"{self.unique_id}_{channel}", {})

    @property
    def event_connection(self) -> str:
        """Type of connection to receive events."""
        if self._api.baichuan.events_active:
            return "TCP push"
        if self._webhook_reachable:
            return "ONVIF push"
        if self._long_poll_received:
            return "ONVIF long polling"
        return "Fast polling"
