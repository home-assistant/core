import json
import logging
import math
from typing import Any
from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.core import HomeAssistant
from websockets import WebSocketClientProtocol

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
        self._client = client
        self._data = data
        self.__id = f"{client_id}-{self._name}"
        _LOGGER.info(f"LedSC {self._name} initialized: {data}")

    def send_request(self, data: dict) -> None:
        self.hass.async_create_task(
            self._client.send(json.dumps({"dev": {self._name: data}}))
        )

    @property
    def unique_id(self) -> str | None:
        return self.__id

    @property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        return {ColorMode.RGBW}

    @property
    def color_mode(self) -> ColorMode | str | None:
        return ColorMode.RGBW

    @property
    def available(self) -> bool:
        return True if self._data["is_lost"] == 0 else False

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return max([self._data[k] for k in ["R", "G", "B", "W"]])

    @brightness.setter
    def brightness(self, value: int) -> None:
        actual = self.brightness
        if actual == 0:
            self.send_request({k: value for k in ["R", "G", "B", "W"]})
        else:
            diff = value - actual
            ratio = diff / actual
            self.send_request(
                {k: round(self._data[k] * (1 + ratio)) for k in ["R", "G", "B", "W"]}
            )

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        return (
            self._data["R"],
            self._data["G"],
            self._data["B"],
            self._data["W"],
        )

    @rgbw_color.setter
    def rgbw_color(self, value: tuple[int, int, int, int]) -> None:
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
        return (
            True
            if (
                self._data["R"] or self._data["G"] or self._data["B"] or self._data["W"]
            )
            else False
        )
        pass

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on.

        You can skip the brightness part if your light does not support
        brightness control.
        """
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
        self.send_request({"trigger": 1})

    async def data(self, value: dict):
        self._data.update(value)
        await self.async_update_ha_state(force_refresh=True)
