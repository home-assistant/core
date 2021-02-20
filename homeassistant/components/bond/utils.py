"""Reusable utilities for the Bond component."""
import asyncio
import logging
from typing import List, Optional, Set

from aiohttp import ClientResponseError
from bond_api import Action, Bond

from .const import BRIDGE_MAKE

_LOGGER = logging.getLogger(__name__)


class BondDevice:
    """Helper device class to hold ID and attributes together."""

    def __init__(self, device_id: str, attrs: dict, props: dict):
        """Create a helper device from ID and attributes returned by API."""
        self.device_id = device_id
        self.props = props
        self._attrs = attrs

    def __repr__(self):
        """Return readable representation of a bond device."""
        return {
            "device_id": self.device_id,
            "props": self.props,
            "attrs": self._attrs,
        }.__repr__()

    @property
    def name(self) -> str:
        """Get the name of this device."""
        return self._attrs["name"]

    @property
    def type(self) -> str:
        """Get the type of this device."""
        return self._attrs["type"]

    @property
    def location(self) -> str:
        """Get the location of this device."""
        return self._attrs.get("location")

    @property
    def template(self) -> str:
        """Return this model template."""
        return self._attrs.get("template")

    @property
    def branding_profile(self) -> str:
        """Return this branding profile."""
        return self.props.get("branding_profile")

    @property
    def trust_state(self) -> bool:
        """Check if Trust State is turned on."""
        return self.props.get("trust_state", False)

    def _has_any_action(self, actions: Set[str]):
        """Check to see if the device supports any of the actions."""
        supported_actions: List[str] = self._attrs["actions"]
        for action in supported_actions:
            if action in actions:
                return True
        return False

    def supports_speed(self) -> bool:
        """Return True if this device supports any of the speed related commands."""
        return self._has_any_action({Action.SET_SPEED})

    def supports_direction(self) -> bool:
        """Return True if this device supports any of the direction related commands."""
        return self._has_any_action({Action.SET_DIRECTION})

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

    def __init__(self, bond: Bond):
        """Initialize Bond Hub."""
        self.bond: Bond = bond
        self._bridge: Optional[dict] = None
        self._version: Optional[dict] = None
        self._devices: Optional[List[BondDevice]] = None

    async def setup(self, max_devices=None):
        """Read hub version information."""
        self._version = await self.bond.version()
        _LOGGER.debug("Bond reported the following version info: %s", self._version)
        # Fetch all available devices using Bond API.
        device_ids = await self.bond.devices()
        self._devices = []
        for idx, device_id in enumerate(device_ids):
            if max_devices is not None and idx >= max_devices:
                break

            device, props = await asyncio.gather(
                self.bond.device(device_id), self.bond.device_properties(device_id)
            )

            self._devices.append(BondDevice(device_id, device, props))

        _LOGGER.debug("Discovered Bond devices: %s", self._devices)
        try:
            # Smart by bond devices do not have a bridge api call
            self._bridge = await self.bond.bridge()
        except ClientResponseError:
            self._bridge = {}
        _LOGGER.debug("Bond reported the following bridge info: %s", self._bridge)

    @property
    def bond_id(self) -> Optional[str]:
        """Return unique Bond ID for this hub."""
        # Old firmwares are missing the bondid
        return self._version.get("bondid")

    @property
    def target(self) -> str:
        """Return this hub target."""
        return self._version.get("target")

    @property
    def model(self) -> str:
        """Return this hub model."""
        return self._version.get("model")

    @property
    def make(self) -> str:
        """Return this hub make."""
        return self._version.get("make", BRIDGE_MAKE)

    @property
    def name(self) -> Optional[str]:
        """Get the name of this bridge."""
        if not self.is_bridge and self._devices:
            return self._devices[0].name
        return self._bridge.get("name")

    @property
    def location(self) -> Optional[str]:
        """Get the location of this bridge."""
        if not self.is_bridge and self._devices:
            return self._devices[0].location
        return self._bridge.get("location")

    @property
    def fw_ver(self) -> str:
        """Return this hub firmware version."""
        return self._version.get("fw_ver")

    @property
    def devices(self) -> List[BondDevice]:
        """Return a list of all devices controlled by this hub."""
        return self._devices

    @property
    def is_bridge(self) -> bool:
        """Return if the Bond is a Bond Bridge."""
        return bool(self._bridge)
