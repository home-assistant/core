"""LedSC light entity."""

import json
import logging
from typing import Any

from websockets import WebSocketClientProtocol

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class LedSC(LightEntity):
    """Representation of an Awesome Light."""

    def __init__(
        self,
        client_id: str,
        name: str,
        data: dict,
        client: WebSocketClientProtocol,
        hass: HomeAssistant,
    ) -> None:
        """Initialize an AwesomeLight."""
        self._hass: HomeAssistant = hass
        self._name = name
        self.client = client
        self._data = data
        self.__id = f"{client_id}-{self._name}"
        _LOGGER.info(f"LedSC '%s' initialized: %s", self.name, data)

    def send_request(self, data: dict) -> None:
        """Sync operation for send data to WebSC."""
        self.hass.async_create_task(
            self.client.send(json.dumps({"dev": {self._name: data}}))
        )

    @property
    def unique_id(self) -> str | None:
        """Return id unique for client and entity name combination."""
        return self.__id

    @property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        """List of supported color modes."""
        return {ColorMode.RGBW}

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the current color mode (static)."""
        return ColorMode.RGBW

    @property
    def available(self) -> bool:
        """
        Check if light is available.

        The information is from WebSC.
        """
        return self._data["is_lost"] == 0

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        return max([self._data[k] for k in ["R", "G", "B", "W"]])

    @brightness.setter
    def brightness(self, value: int) -> None:
        """Set brightness of the light."""
        actual = self.brightness
        if actual is None or actual == 0:
            self.send_request({k: value for k in ["R", "G", "B", "W"]})
        else:
            diff = value - actual
            ratio = diff / actual
            self.send_request(
                {k: round(self._data[k] * (1 + ratio)) for k in ["R", "G", "B", "W"]}
            )

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Get color."""
        return (
            self._data["R"],
            self._data["G"],
            self._data["B"],
            self._data["W"],
        )

    @rgbw_color.setter
    def rgbw_color(self, value: tuple[int, int, int, int]) -> None:
        """Set color to WebSC."""
        self.send_request(
            {
                "R": value[0],
                "G": value[1],
                "B": value[2],
                "W": value[3],
            }
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return bool(
            self._data["R"] or self._data["G"] or self._data["B"] or self._data["W"]
        )

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        if "brightness" in kwargs:
            self.brightness = kwargs["brightness"]
        elif "rgbw_color" in kwargs:
            self.rgbw_color = kwargs["rgbw_color"]
        elif not self.is_on:
            self.switch()

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        if self.is_on:
            self.switch()

    def switch(self) -> None:
        """Send switch event to WebSC."""
        self.send_request({"trigger": 1})

    async def data(self, value: dict):
        """For update data. This data must be received from WebSC."""
        self._data.update(value)
        await self.async_update_ha_state(force_refresh=True)
