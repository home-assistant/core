"""Harmony data object which contains the Harmony Client."""

import asyncio
import logging
from typing import Any, Callable, Iterable, NamedTuple, Optional

from aioharmony.const import ClientCallbackType, ClientConfigType, SendCommandDevice
import aioharmony.exceptions as aioexc
from aioharmony.harmonyapi import HarmonyAPI as HarmonyClient

from homeassistant.core import callback

from .const import ACTIVITY_POWER_OFF

_LOGGER = logging.getLogger(__name__)

NoParamCallback = Optional[Callable[[object], Any]]
ActivityCallback = Optional[Callable[[object, tuple], Any]]
ConfigCallback = Optional[Callable[[object, ClientConfigType], Any]]


class HarmonyCallback(NamedTuple):
    """Callback type for Harmony Hub notifications."""

    connected: NoParamCallback
    disconnected: NoParamCallback
    config_updated: ConfigCallback
    activity_starting: ActivityCallback
    activity_started: ActivityCallback


class HarmonyData:
    """HarmonyData registers for Harmony hub updates."""

    def __init__(self, address: str, name: str, unique_id: str):
        """Initialize a subscriber."""
        self._name = name
        self._unique_id = unique_id
        self._subscriptions = []
        self._available = False

        callbacks = {
            "config_updated": self._config_updated,
            "connect": self._connected,
            "disconnect": self._disconnected,
            "new_activity_starting": self._activity_starting,
            "new_activity": self._activity_started,
        }
        self._client = HarmonyClient(
            ip_address=address, callbacks=ClientCallbackType(**callbacks)
        )

    @property
    def activity_names(self):
        """Names of all the remotes activities."""
        activity_infos = self._client.config.get("activity", [])
        activities = [activity["label"] for activity in activity_infos]

        # Remove both ways of representing PowerOff
        if None in activities:
            activities.remove(None)
        if ACTIVITY_POWER_OFF in activities:
            activities.remove(ACTIVITY_POWER_OFF)

        return activities

    @property
    def device_names(self):
        """Names of all of the devices connected to the hub."""
        device_infos = self._client.config.get("device", [])
        devices = [device["label"] for device in device_infos]

        return devices

    @property
    def name(self):
        """Return the Harmony device's name."""
        return self._name

    @property
    def unique_id(self):
        """Return the Harmony device's unique_id."""
        return self._unique_id

    @property
    def available(self) -> bool:
        """Return if connected to the hub."""
        return self._available

    @property
    def current_activity(self) -> tuple:
        """Return the current activity tuple."""
        return self._client.current_activity

    @property
    def json_config(self) -> dict:
        """Return the hub config as json."""
        if self._client.config is None:
            return None
        return self._client.json_config

    def device_info(self, domain: str):
        """Return hub device info."""
        model = "Harmony Hub"
        if "ethernetStatus" in self._client.hub_config.info:
            model = "Harmony Hub Pro 2400"
        return {
            "identifiers": {(domain, self.unique_id)},
            "manufacturer": "Logitech",
            "sw_version": self._client.hub_config.info.get(
                "hubSwVersion", self._client.fw_version
            ),
            "name": self.name,
            "model": model,
        }

    async def connect(self) -> bool:
        """Connect to the Harmony Hub."""
        _LOGGER.debug("%s: Connecting", self._name)
        try:
            if not await self._client.connect():
                _LOGGER.warning("%s: Unable to connect to HUB", self._name)
                await self._client.close()
                return False
        except aioexc.TimeOut:
            _LOGGER.warning("%s: Connection timed-out", self._name)
            return False
        return True

    async def shutdown(self):
        """Close connection on shutdown."""
        _LOGGER.debug("%s: Closing Harmony Hub", self._name)
        try:
            await self._client.close()
        except aioexc.TimeOut:
            _LOGGER.warning("%s: Disconnect timed-out", self._name)

    async def async_start_activity(self, activity: str):
        """Start an activity from the Harmony device."""

        if activity:
            activity_id = None
            activity_name = None

            if activity.isdigit() or activity == "-1":
                _LOGGER.debug("%s: Activity is numeric", self.name)
                activity_name = self._client.get_activity_name(int(activity))
                if activity_name:
                    activity_id = activity

            if activity_id is None:
                _LOGGER.debug("%s: Find activity ID based on name", self.name)
                activity_name = str(activity)
                activity_id = self._client.get_activity_id(activity_name)

            if activity_id is None:
                _LOGGER.error("%s: Activity %s is invalid", self.name, activity)
                return

            current_activity_id, current_activity_name = self.current_activity
            if current_activity_name == activity_name:
                # Automations or HomeKit may turn the device on multiple times
                # when the current activity is already active which will cause
                # harmony to loose state.  This behavior is unexpected as turning
                # the device on when its already on isn't expected to reset state.
                _LOGGER.debug(
                    "%s: Current activity is already %s", self.name, activity_name
                )
                return

            try:
                await self._client.start_activity(activity_id)
            except aioexc.TimeOut:
                _LOGGER.error("%s: Starting activity %s timed-out", self.name, activity)
        else:
            _LOGGER.error("%s: No activity specified with turn_on service", self.name)

    async def async_power_off(self):
        """Start the PowerOff activity."""
        _LOGGER.debug("%s: Turn Off", self.name)
        try:
            await self._client.power_off()
        except aioexc.TimeOut:
            _LOGGER.error("%s: Powering off timed-out", self.name)

    async def async_send_command(
        self,
        commands: Iterable[str],
        device: str,
        num_repeats: int,
        delay_secs: float,
        hold_secs: float,
    ):
        """Send a list of commands to one device."""
        device_id = None
        if device.isdigit():
            _LOGGER.debug("%s: Device %s is numeric", self.name, device)
            if self._client.get_device_name(int(device)):
                device_id = device

        if device_id is None:
            _LOGGER.debug(
                "%s: Find device ID %s based on device name", self.name, device
            )
            device_id = self._client.get_device_id(str(device).strip())

        if device_id is None:
            _LOGGER.error("%s: Device %s is invalid", self.name, device)
            return

        _LOGGER.debug(
            "Sending commands to device %s holding for %s seconds "
            "with a delay of %s seconds",
            device,
            hold_secs,
            delay_secs,
        )

        # Creating list of commands to send.
        snd_cmnd_list = []
        for _ in range(num_repeats):
            for single_command in commands:
                send_command = SendCommandDevice(
                    device=device_id, command=single_command, delay=hold_secs
                )
                snd_cmnd_list.append(send_command)
                if delay_secs > 0:
                    snd_cmnd_list.append(float(delay_secs))

        _LOGGER.debug("%s: Sending commands", self.name)
        try:
            result_list = await self._client.send_commands(snd_cmnd_list)
        except aioexc.TimeOut:
            _LOGGER.error("%s: Sending commands timed-out", self.name)
            return

        for result in result_list:
            _LOGGER.error(
                "Sending command %s to device %s failed with code %s: %s",
                result.command.command,
                result.command.device,
                result.code,
                result.msg,
            )

    async def change_channel(self, channel: int):
        """Change the channel using Harmony remote."""
        _LOGGER.debug("%s: Changing channel to %s", self.name, channel)
        try:
            await self._client.change_channel(channel)
        except aioexc.TimeOut:
            _LOGGER.error("%s: Changing channel to %s timed-out", self.name, channel)

    async def sync(self) -> bool:
        """Sync the Harmony device with the web service.

        Returns True if the sync was successful.
        """
        _LOGGER.debug("%s: Syncing hub with Harmony cloud", self.name)
        try:
            await self._client.sync()
        except aioexc.TimeOut:
            _LOGGER.error("%s: Syncing hub with Harmony cloud timed-out", self.name)
            return False
        else:
            return True

    @callback
    def async_subscribe(self, update_callback: HarmonyCallback) -> Callable:
        """Add a callback subscriber."""
        self._subscriptions.append(update_callback)

        def _unsubscribe():
            self.async_unsubscribe(update_callback)

        return _unsubscribe

    @callback
    def async_unsubscribe(self, update_callback: HarmonyCallback):
        """Remove a callback subscriber."""
        self._subscriptions.remove(update_callback)

    def _config_updated(self, _=None) -> None:
        _LOGGER.debug("config_updated")
        for subscription in self._subscriptions:
            current_callback = subscription.config_updated
            if current_callback:
                current_callback(self._client.hub_config)

    def _connected(self, _=None) -> None:
        _LOGGER.debug("connected")
        self._available = True
        for subscription in self._subscriptions:
            current_callback = subscription.connected
            if current_callback:
                if asyncio.iscoroutinefunction(current_callback):
                    asyncio.create_task(current_callback())
                else:
                    current_callback()

    def _disconnected(self, _=None) -> None:
        _LOGGER.debug("disconnected")
        self._available = False
        for subscription in self._subscriptions:
            current_callback = subscription.disconnected
            if current_callback:
                if asyncio.iscoroutinefunction(current_callback):
                    asyncio.create_task(current_callback())
                else:
                    current_callback()

    def _activity_starting(self, activity_info: tuple) -> None:
        _LOGGER.debug("activity %s starting", activity_info)
        for subscription in self._subscriptions:
            current_callback = subscription.activity_starting
            if current_callback:
                current_callback(activity_info)

    def _activity_started(self, activity_info: tuple) -> None:
        _LOGGER.debug("activity %s started", activity_info)
        for subscription in self._subscriptions:
            current_callback = subscription.activity_started
            if current_callback:
                current_callback(activity_info)
