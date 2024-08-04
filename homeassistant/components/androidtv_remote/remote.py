"""Remote control support for Android TV Remote."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_DELAY_SECS,
    ATTR_HOLD_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_HOLD_SECS,
    DEFAULT_NUM_REPEATS,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AndroidTVRemoteConfigEntry
from .const import CONF_APP_NAME
from .entity import AndroidTVRemoteBaseEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AndroidTVRemoteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Android TV remote entity based on a config entry."""
    api = config_entry.runtime_data
    async_add_entities([AndroidTVRemoteEntity(api, config_entry)])


class AndroidTVRemoteEntity(AndroidTVRemoteBaseEntity, RemoteEntity):
    """Android TV Remote Entity."""

    _attr_supported_features = RemoteEntityFeature.ACTIVITY

    def _update_current_app(self, current_app: str) -> None:
        """Update current app info."""
        self._attr_current_activity = (
            self._apps[current_app].get(CONF_APP_NAME, current_app)
            if current_app in self._apps
            else current_app
        )

    @callback
    def _current_app_updated(self, current_app: str) -> None:
        """Update the state when the current app changes."""
        self._update_current_app(current_app)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        self._attr_activity_list = [
            app.get(CONF_APP_NAME, "") for app in self._apps.values()
        ]
        self._update_current_app(self._api.current_app)
        self._api.add_current_app_updated_callback(self._current_app_updated)

    async def async_will_remove_from_hass(self) -> None:
        """Remove callbacks."""
        await super().async_will_remove_from_hass()

        self._api.remove_current_app_updated_callback(self._current_app_updated)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the Android TV on."""
        if not self.is_on:
            self._send_key_command("POWER")
        activity = kwargs.get(ATTR_ACTIVITY, "")
        if activity:
            activity = next(
                (
                    app_id
                    for app_id, app in self._apps.items()
                    if app.get(CONF_APP_NAME, "") == activity
                ),
                activity,
            )
            self._send_launch_app_command(activity)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the Android TV off."""
        if self.is_on:
            self._send_key_command("POWER")

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send commands to one device."""
        num_repeats = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        delay_secs = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        hold_secs = kwargs.get(ATTR_HOLD_SECS, DEFAULT_HOLD_SECS)

        for _ in range(num_repeats):
            for single_command in command:
                if hold_secs:
                    self._send_key_command(single_command, "START_LONG")
                    await asyncio.sleep(hold_secs)
                    self._send_key_command(single_command, "END_LONG")
                else:
                    self._send_key_command(single_command, "SHORT")
                await asyncio.sleep(delay_secs)
