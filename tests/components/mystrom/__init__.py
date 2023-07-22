"""Tests for the myStrom integration."""
from typing import Any, Optional


def get_default_device_response(device_type: int | None) -> dict[str, Any]:
    """Return default device response."""
    response = {
        "version": "2.59.32",
        "mac": "6001940376EB",
        "ssid": "personal",
        "ip": "192.168.0.23",
        "mask": "255.255.255.0",
        "gw": "192.168.0.1",
        "dns": "192.168.0.1",
        "static": False,
        "connected": True,
        "signal": 94,
    }
    if device_type is not None:
        response["type"] = device_type
    return response


def get_default_bulb_state() -> dict[str, Any]:
    """Get default bulb state."""
    return {
        "type": "rgblamp",
        "battery": False,
        "reachable": True,
        "meshroot": True,
        "on": False,
        "color": "46;18;100",
        "mode": "hsv",
        "ramp": 10,
        "power": 0.45,
        "fw_version": "2.58.0",
    }


def get_default_switch_state() -> dict[str, Any]:
    """Get default switch state."""
    return {
        "power": 1.69,
        "Ws": 0.81,
        "relay": True,
        "temperature": 24.87,
        "version": "2.59.32",
        "mac": "6001940376EB",
        "ssid": "personal",
        "ip": "192.168.0.23",
        "mask": "255.255.255.0",
        "gw": "192.168.0.1",
        "dns": "192.168.0.1",
        "static": False,
        "connected": True,
        "signal": 94,
    }


class MyStromDeviceMock:
    """Base device mock."""

    def __init__(self, state: dict[str, Any]) -> None:
        """Initialize device mock."""
        self._requested_state = False
        self._state = state

    async def get_state(self) -> None:
        """Set if state is requested."""
        self._requested_state = True


class MyStromBulbMock(MyStromDeviceMock):
    """MyStrom Bulb mock."""

    def __init__(self, mac: str, state: dict[str, Any]) -> None:
        """Initialize bulb mock."""
        super().__init__(state)
        self.mac = mac

    @property
    def firmware(self) -> Optional[str]:
        """Return current firmware."""
        if not self._requested_state:
            return None
        return self._state["fw_version"]

    @property
    def consumption(self) -> Optional[float]:
        """Return current firmware."""
        if not self._requested_state:
            return None
        return self._state["power"]

    @property
    def color(self) -> Optional[str]:
        """Return current color settings."""
        if not self._requested_state:
            return None
        return self._state["color"]

    @property
    def mode(self) -> Optional[str]:
        """Return current mode."""
        if not self._requested_state:
            return None
        return self._state["mode"]

    @property
    def transition_time(self) -> Optional[int]:
        """Return current transition time (ramp)."""
        if not self._requested_state:
            return None
        return self._state["ramp"]

    @property
    def bulb_type(self) -> Optional[str]:
        """Return the type of the bulb."""
        if not self._requested_state:
            return None
        return self._state["type"]

    @property
    def state(self) -> Optional[bool]:
        """Return the current state of the bulb."""
        if not self._requested_state:
            return None
        return self._state["on"]


class MyStromSwitchMock(MyStromDeviceMock):
    """MyStrom Switch mock."""

    @property
    def relay(self) -> Optional[bool]:
        """Return the relay state."""
        if not self._requested_state:
            return None
        return self._state["on"]

    @property
    def consumption(self) -> Optional[float]:
        """Return the current power consumption in mWh."""
        if not self._requested_state:
            return None
        return self._state["power"]

    @property
    def consumedWs(self) -> Optional[float]:
        """The average of energy consumed per second since last report call."""
        if not self._requested_state:
            return None
        return self._state["Ws"]

    @property
    def firmware(self) -> Optional[str]:
        """Return the current firmware."""
        if not self._requested_state:
            return None
        return self._state["version"]

    @property
    def mac(self) -> Optional[str]:
        """Return the MAC address."""
        if not self._requested_state:
            return None
        return self._state["mac"]

    @property
    def temperature(self) -> Optional[float]:
        """Return the current temperature in celsius."""
        if not self._requested_state:
            return None
        return self._state["temperature"]
