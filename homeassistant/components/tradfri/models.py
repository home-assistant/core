"""Provide a model for the Tradfri integration."""
from __future__ import annotations

from dataclasses import dataclass

from pytradfri import Gateway
from pytradfri.api.aiocoap_api import APIFactory, APIRequestProtocol

from .coordinator import TradfriDeviceDataUpdateCoordinator


@dataclass
class TradfriData:
    """Data for the Tradfri integration."""

    api: APIRequestProtocol
    coordinators: list[TradfriDeviceDataUpdateCoordinator]
    factory: APIFactory
    gateway: Gateway
