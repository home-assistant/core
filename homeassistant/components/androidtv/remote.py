"""Support for the AndroidTV remote."""

from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

from androidtv.constants import KEYS
from androidtvremote2 import AndroidTVRemote

from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_DELAY_SECS,
    ATTR_HOLD_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AndroidTVADBRuntimeData, AndroidTVConfigEntry, AndroidTVRemoteRuntimeData
from .const import (
    CONF_CONNECTION_TYPE,
    CONF_TURN_OFF_COMMAND,
    CONF_TURN_ON_COMMAND,
    CONNECTION_TYPE_REMOTE,
    DOMAIN,
)
from .entity import AndroidTVADBEntity, AndroidTVRemoteEntity, adb_decorator

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AndroidTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AndroidTV remote from a config entry."""
    connection_type = entry.data.get(CONF_CONNECTION_TYPE)

    if connection_type == CONNECTION_TYPE_REMOTE:
        # Remote protocol connection
        runtime_data = entry.runtime_data
        assert isinstance(runtime_data, AndroidTVRemoteRuntimeData)
        async_add_entities([AndroidTVRemoteProtocolRemote(runtime_data.api, entry)])
    else:
        # ADB connection
        async_add_entities([AndroidTVADBRemote(entry)])


# =============================================================================
# Remote Protocol Remote Entity
# =============================================================================


class AndroidTVRemoteProtocolRemote(AndroidTVRemoteEntity, RemoteEntity):
    """Android TV Remote Entity using Remote Protocol."""

    _attr_supported_features = RemoteEntityFeature.ACTIVITY

    def __init__(
        self, api: AndroidTVRemote, config_entry: AndroidTVConfigEntry
    ) -> None:
        """Initialize the entity."""
        super().__init__(api, config_entry)

    @property
    def is_on(self) -> bool:
        """Return true if the device is on."""
        return self._attr_is_on or False

    @property
    def current_activity(self) -> str | None:
        """Return current activity."""
        return self._api.current_app

    async def async_turn_on(self, activity: str | None = None, **kwargs: Any) -> None:
        """Turn on the device. Launch an app if activity is provided."""
        if not self._attr_is_on:
            self._send_key_command("POWER")
        if activity:
            self._send_launch_app_command(activity)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        if self._attr_is_on:
            self._send_key_command("POWER")

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send commands to device."""
        num_repeats = kwargs.get(ATTR_NUM_REPEATS, 1)
        delay_secs = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        hold_secs = kwargs.get(ATTR_HOLD_SECS, 0)
        activity = kwargs.get(ATTR_ACTIVITY)

        if activity:
            self._send_launch_app_command(activity)
        else:
            for _ in range(num_repeats):
                for single_command in command:
                    if hold_secs:
                        self._send_key_command(single_command, "START_LONG")
                        await self.hass.async_add_executor_job(
                            __import__("time").sleep, hold_secs
                        )
                        self._send_key_command(single_command, "END_LONG")
                    else:
                        self._send_key_command(single_command)
                    if delay_secs:
                        await self.hass.async_add_executor_job(
                            __import__("time").sleep, delay_secs
                        )


# =============================================================================
# ADB Remote Entity
# =============================================================================


class AndroidTVADBRemote(AndroidTVADBEntity, RemoteEntity):
    """Device that sends commands to an AndroidTV via ADB."""

    _attr_name = None
    _attr_should_poll = False

    @adb_decorator()
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        options = self._entry_runtime_data.dev_opt
        if turn_on_cmd := options.get(CONF_TURN_ON_COMMAND):
            await self.aftv.adb_shell(turn_on_cmd)
        else:
            await self.aftv.turn_on()

    @adb_decorator()
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        options = self._entry_runtime_data.dev_opt
        if turn_off_cmd := options.get(CONF_TURN_OFF_COMMAND):
            await self.aftv.adb_shell(turn_off_cmd)
        else:
            await self.aftv.turn_off()

    @adb_decorator()
    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to a device."""

        num_repeats = kwargs[ATTR_NUM_REPEATS]
        command_list = []
        for cmd in command:
            if key := KEYS.get(cmd):
                command_list.append(f"input keyevent {key}")
            else:
                command_list.append(cmd)

        for _ in range(num_repeats):
            for cmd in command_list:
                try:
                    await self.aftv.adb_shell(cmd)
                except UnicodeDecodeError as ex:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="failed_send",
                        translation_placeholders={"cmd": cmd},
                    ) from ex
