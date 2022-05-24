"""Common vera code."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import re
from typing import Any, NamedTuple

import pyvera as pv

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EXCLUDE, CONF_LIGHTS, Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import call_later

from .const import DOMAIN

_LIST_REGEX = re.compile("[^0-9]+")


class ControllerData(NamedTuple):
    """Controller data."""

    controller: pv.VeraController
    devices: defaultdict[Platform, list[pv.VeraDevice]]
    scenes: list[pv.VeraScene]
    config_entry: ConfigEntry


def get_configured_platforms(controller_data: ControllerData) -> set[Platform]:
    """Get configured platforms for a controller."""
    platforms: list[Platform] = []
    for platform in controller_data.devices:
        platforms.append(platform)

    if controller_data.scenes:
        platforms.append(Platform.SCENE)

    return set(platforms)


def get_controller_data(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> ControllerData:
    """Get controller data from hass data."""
    return hass.data[DOMAIN][config_entry.entry_id]


def set_controller_data(
    hass: HomeAssistant, config_entry: ConfigEntry, data: ControllerData
) -> None:
    """Set controller data in hass data."""
    hass.data[DOMAIN][config_entry.entry_id] = data


class SubscriptionRegistry(pv.AbstractSubscriptionRegistry):
    """Manages polling for data from vera."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the object."""
        super().__init__()
        self._hass = hass
        self._cancel_poll: CALLBACK_TYPE | None = None

    def start(self) -> None:
        """Start polling for data."""
        self.stop()
        self._schedule_poll(1)

    def stop(self) -> None:
        """Stop polling for data."""
        if self._cancel_poll:
            self._cancel_poll()
            self._cancel_poll = None

    def _schedule_poll(self, delay: float) -> None:
        self._cancel_poll = call_later(self._hass, delay, self._run_poll_server)

    def _run_poll_server(self, now: datetime) -> None:
        delay = 1

        # Long poll for changes. The downstream API instructs the endpoint to wait a
        # a minimum of 200ms before returning data and a maximum of 9s before timing out.
        if not self.poll_server_once():
            # If an error was encountered, wait a bit longer before trying again.
            delay = 60

        self._schedule_poll(delay)


def fix_device_id_list(data: list[Any]) -> list[int]:
    """Fix the id list by converting it to a supported int list."""
    return str_to_int_list(list_to_str(data))


def str_to_int_list(data: str) -> list[int]:
    """Convert a string to an int list."""
    return [int(s) for s in _LIST_REGEX.split(data) if len(s) > 0]


def list_to_str(data: list[Any]) -> str:
    """Convert an int list to a string."""
    return " ".join([str(i) for i in data])


def new_options(lights: list[int], exclude: list[int]) -> dict[str, list[int]]:
    """Create a standard options object."""
    return {CONF_LIGHTS: lights, CONF_EXCLUDE: exclude}
