"""Models for the Netio switch component."""

from __future__ import annotations

from typing import NamedTuple

from pynetio import Netio

from homeassistant.components.switch import SwitchEntity


class Device(NamedTuple):
    """Named tuple to represent a Netio device."""

    netio: Netio
    entities: list[SwitchEntity]
