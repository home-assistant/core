"""AVE hub to connect to dp server."""

from __future__ import annotations

import aiohttp

# In a real implementation, this would be in an external library that's on PyPI.
# The PyPI package needs to be included in the `requirements` section of manifest.json
# See https://developers.home-assistant.io/docs/creating_integration_manifest
# for more information.
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import Callable


class AveHub:
    """AVE WebServer hub."""

    def __init__(self, hass: HomeAssistant, host: str, apiKey: str) -> None:
        """Init AVE hub."""
        self._hass = hass
        self._name = "AVE WebServer"
        self._id = f"avebus_{host.lower()}"
        self._devices: list[RollerShutter] = []
        self._session = aiohttp.ClientSession(
            base_url=host,
            timeout=aiohttp.ClientTimeout(10),
            headers={"x-api-key": apiKey},
        )
        self._host = host

    @property
    def hub_id(self) -> str:
        """ID for hub."""
        return self._id

    @property
    def devices(self) -> list[RollerShutter]:
        """List of rollers."""
        return self._devices

    @property
    def session(self) -> aiohttp.ClientSession:
        """Http session."""
        return self._session

    @property
    def host(self) -> str:
        """Host."""
        return self._host

    async def async_load_entities(self):
        """Load AVE entities."""
        r = await self._session.get("/avebus/rollershutters")
        data = await r.json()

        self.devices.extend(
            [
                RollerShutter(
                    self,
                    item["Name"],
                    item["Channel"],
                    item["Percentage"],
                    item["TotalUpTime"],
                    item["TotalDownTime"],
                )
                for item in data
            ]
        )


class RollerShutter:
    """AVE roller shutter."""

    def __init__(
        self, hub: AveHub, name, channel, percentage, total_up_time, total_down_time
    ) -> None:
        """Init ave roller shutter."""
        self._name = name
        self._channel = channel
        self._hub = hub
        self._callbacks = set()
        self._position = percentage
        self._total_up_time = total_up_time
        self._total_down_time = total_down_time

    @property
    def name(self) -> str:
        """Return name for roller."""
        return self._name

    @property
    def channel(self) -> str:
        """Return ID for roller."""
        return self._channel

    @property
    def position(self) -> float:
        """Return position for roller."""
        return self._position

    @property
    def total_up_time(self) -> float:
        """Return total up time."""
        return self._total_up_time

    @property
    def total_down_time(self) -> float:
        """Return total down time."""
        return self._total_down_time

    async def async_request_position(self, position) -> None:
        """Set posiiton."""
        await self._hub.session.post(f"/avebus/{self._channel}?percentage={position}")

    async def async_stop(self) -> None:
        """Stop roller."""
        r = await self._hub.session.post(f"/avebus/{self._channel}?command=stop")
        data = await r.json()

        entities = [
            {
                "percent": item["previousPerc"],
            }
            for item in data
        ]
        self._position = entities[0]["percent"]

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    # In a real implementation, this library would call it's call backs when it was
    # notified of any state changeds for the relevant device.
    async def async_publish_updates(self) -> None:
        """Schedule call all registered callbacks."""
        for callback in self._callbacks:
            callback()
