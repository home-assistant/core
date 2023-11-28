"""Reusable utilities for the Bond component."""
from __future__ import annotations

import logging
from typing import Any, cast

from aiohttp import ClientResponseError
from bond_async import Action, Bond, BondType

from homeassistant.util.async_ import gather_with_limited_concurrency

from .const import BRIDGE_MAKE

MAX_REQUESTS = 6

_LOGGER = logging.getLogger(__name__)


class BondDevice:
    """Helper device class to hold ID and attributes together."""

    def __init__(
        self,
        device_id: str,
        attrs: dict[str, Any],
        props: dict[str, Any],
        state: dict[str, Any],
    ) -> None:
        """Create a helper device from ID and attributes returned by API."""
        self.device_id = device_id
        self.props = props
        self.state = state
        self._attrs = attrs or {}
        self._supported_actions: set[str] = set(self._attrs.get("actions", []))

    def __repr__(self) -> str:
        """Return readable representation of a bond device."""
        return {
            "device_id": self.device_id,
            "props": self.props,
            "attrs": self._attrs,
            "state": self.state,
        }.__repr__()

    @property
    def name(self) -> str:
        """Get the name of this device."""
        return cast(str, self._attrs["name"])

    @property
    def type(self) -> str:
        """Get the type of this device."""
        return cast(str, self._attrs["type"])

    @property
    def location(self) -> str | None:
        """Get the location of this device."""
        return self._attrs.get("location")

    @property
    def template(self) -> str | None:
        """Return this model template."""
        return self._attrs.get("template")

    @property
    def branding_profile(self) -> str | None:
        """Return this branding profile."""
        return self.props.get("branding_profile")

    @property
    def trust_state(self) -> bool:
        """Check if Trust State is turned on."""
        return self.props.get("trust_state", False)  # type: ignore[no-any-return]

    def has_action(self, action: str) -> bool:
        """Check to see if the device supports an actions."""
        return action in self._supported_actions

    def _has_any_action(self, actions: set[str]) -> bool:
        """Check to see if the device supports any of the actions."""
        return bool(self._supported_actions.intersection(actions))

    def supports_speed(self) -> bool:
        """Return True if this device supports any of the speed related commands."""
        return self._has_any_action({Action.SET_SPEED})

    def supports_direction(self) -> bool:
        """Return True if this device supports any of the direction related commands."""
        return self._has_any_action({Action.SET_DIRECTION})

    def supports_set_position(self) -> bool:
        """Return True if this device supports setting the position."""
        return self._has_any_action({Action.SET_POSITION})

    def supports_open(self) -> bool:
        """Return True if this device supports opening."""
        return self._has_any_action({Action.OPEN})

    def supports_close(self) -> bool:
        """Return True if this device supports closing."""
        return self._has_any_action({Action.CLOSE})

    def supports_tilt_open(self) -> bool:
        """Return True if this device supports tilt opening."""
        return self._has_any_action({Action.TILT_OPEN})

    def supports_tilt_close(self) -> bool:
        """Return True if this device supports tilt closing."""
        return self._has_any_action({Action.TILT_CLOSE})

    def supports_hold(self) -> bool:
        """Return True if this device supports hold aka stop."""
        return self._has_any_action({Action.HOLD})

    def supports_light(self) -> bool:
        """Return True if this device supports any of the light related commands."""
        return self._has_any_action({Action.TURN_LIGHT_ON, Action.TURN_LIGHT_OFF})

    def supports_up_light(self) -> bool:
        """Return true if the device has an up light."""
        return self._has_any_action({Action.TURN_UP_LIGHT_ON, Action.TURN_UP_LIGHT_OFF})

    def supports_down_light(self) -> bool:
        """Return true if the device has a down light."""
        return self._has_any_action(
            {Action.TURN_DOWN_LIGHT_ON, Action.TURN_DOWN_LIGHT_OFF}
        )

    def supports_set_brightness(self) -> bool:
        """Return True if this device supports setting a light brightness."""
        return self._has_any_action({Action.SET_BRIGHTNESS})


class BondHub:
    """Hub device representing Bond Bridge."""

    def __init__(self, bond: Bond, host: str) -> None:
        """Initialize Bond Hub."""
        self.bond: Bond = bond
        self.host = host
        self._bridge: dict[str, Any] = {}
        self._version: dict[str, Any] = {}
        self._devices: list[BondDevice] = []

    async def setup(self, max_devices: int | None = None) -> None:
        """Read hub version information."""
        self._version = await self.bond.version()
        _LOGGER.debug("Bond reported the following version info: %s", self._version)
        # Fetch all available devices using Bond API.
        device_ids = await self.bond.devices()
        self._devices = []
        setup_device_ids = []
        tasks = []
        for idx, device_id in enumerate(device_ids):
            if max_devices is not None and idx >= max_devices:
                break
            setup_device_ids.append(device_id)
            tasks.extend(
                [
                    self.bond.device(device_id),
                    self.bond.device_properties(device_id),
                    self.bond.device_state(device_id),
                ]
            )

        responses = await gather_with_limited_concurrency(MAX_REQUESTS, *tasks)
        response_idx = 0
        for device_id in setup_device_ids:
            self._devices.append(
                BondDevice(
                    device_id,
                    responses[response_idx],
                    responses[response_idx + 1],
                    responses[response_idx + 2],
                )
            )
            response_idx += 3

        _LOGGER.debug("Discovered Bond devices: %s", self._devices)
        try:
            # Smart by bond devices do not have a bridge api call
            self._bridge = await self.bond.bridge()
        except ClientResponseError:
            self._bridge = {}
        _LOGGER.debug("Bond reported the following bridge info: %s", self._bridge)

    @property
    def bond_id(self) -> str | None:
        """Return unique Bond ID for this hub."""
        # Old firmwares are missing the bondid
        return self._version.get("bondid")

    @property
    def target(self) -> str | None:
        """Return this hub target."""
        return self._version.get("target")

    @property
    def model(self) -> str | None:
        """Return this hub model."""
        return self._version.get("model")

    @property
    def make(self) -> str:
        """Return this hub make."""
        return self._version.get("make", BRIDGE_MAKE)  # type: ignore[no-any-return]

    @property
    def name(self) -> str:
        """Get the name of this bridge."""
        if not self.is_bridge and self._devices:
            return self._devices[0].name
        return cast(str, self._bridge["name"])

    @property
    def location(self) -> str | None:
        """Get the location of this bridge."""
        if not self.is_bridge and self._devices:
            return self._devices[0].location
        return self._bridge.get("location")

    @property
    def fw_ver(self) -> str | None:
        """Return this hub firmware version."""
        return self._version.get("fw_ver")

    @property
    def mcu_ver(self) -> str | None:
        """Return this hub hardware version."""
        return self._version.get("mcu_ver")

    @property
    def devices(self) -> list[BondDevice]:
        """Return a list of all devices controlled by this hub."""
        return self._devices

    @property
    def is_bridge(self) -> bool:
        """Return if the Bond is a Bond Bridge."""
        bondid = self._version["bondid"]
        return bool(BondType.is_bridge_from_serial(bondid))
