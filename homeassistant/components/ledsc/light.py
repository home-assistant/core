"""LedSC light."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant

from websc_client import WebSClientAsync as WebSClient
from websc_client import WebSCAsync

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant, config, add_entities: AddEntitiesCallback, discovery_info=None
):
    """Redirects to '__setup'."""
    hass.async_create_task(__setup(hass, dict(config), add_entities))


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, add_entities: AddEntitiesCallback
):
    """Redirects to '__setup'."""
    await __setup(hass, dict(config.data), add_entities)


async def __setup(hass: HomeAssistant, config: dict, add_entities: AddEntitiesCallback):
    """
    Connect to WebSC.

    load the configured devices and add them to hass.
    """
    host = config["host"]
    port = config["port"]

    client = WebSClient(host=host, port=port)
    await client.connect()
    hass.async_create_background_task(client.observer(), name="ledsc-observer")

    devices: list[LedSC] = list()
    for websc in client.devices.values():
        ledsc = LedSC(
            client_id=f"{host}:{port}",
            websc=websc,
            hass=hass,
        )
        websc.set_callback(__generate_callback(ledsc))
        devices.append(ledsc)
    add_entities(devices, True)


class LedSC(LightEntity):
    """Representation of an Awesome Light."""

    def __init__(
        self,
        client_id: str,
        websc: WebSCAsync,
        hass: HomeAssistant,
    ) -> None:
        """Initialize an AwesomeLight."""
        self._hass: HomeAssistant = hass
        self._websc: WebSCAsync = websc
        self.__id = f"{client_id}-{websc.name}"
        _LOGGER.info(f"LedSC '%s' initialized!", self.name)

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
        return not self._websc.is_lost

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._websc.name

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        return max(self._websc.rgbw)

    @brightness.setter
    def brightness(self, value: int) -> None:
        """Set brightness of the light."""
        actual = self.brightness
        if actual is None or actual == 0:
            self.hass.async_create_task(
                self._websc.set_rgbw(red=value, green=value, blue=value, white=value)
            )
        else:
            diff = value - actual
            ratio = diff / actual
            self.hass.async_create_task(
                self._websc.set_rgbw(
                    red=round(self._websc.red * (1 + ratio)),
                    green=round(self._websc.green * (1 + ratio)),
                    blue=round(self._websc.blue * (1 + ratio)),
                    white=round(self._websc.white * (1 + ratio)),
                )
            )

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Get color."""
        return self._websc.rgbw

    @rgbw_color.setter
    def rgbw_color(self, value: tuple[int, int, int, int]) -> None:
        """Set color to WebSC."""
        self.hass.async_create_task(
            self._websc.set_rgbw(
                red=value[0],
                green=value[1],
                blue=value[2],
                white=value[3],
            )
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return bool(
            self._websc.red
            or self._websc.green
            or self._websc.blue
            or self._websc.white
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        if "brightness" in kwargs:
            self.brightness = kwargs["brightness"]
        elif "rgbw_color" in kwargs:
            self.rgbw_color = kwargs["rgbw_color"]
        elif not self.is_on:
            await self.switch()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        if self.is_on:
            await self.switch()

    async def switch(self) -> None:
        """Send switch event to WebSC."""
        await self._websc.do_px_trigger()


def __generate_callback(ledsc: LedSC):
    async def on_device_change(data: dict[str, int]):
        await ledsc.async_update_ha_state(force_refresh=True)

    return on_device_change
