"""Linear garage door light."""

from datetime import timedelta
import math
from typing import Any

from linear_garage_door import Linear

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LinearEntity
from .const import DOMAIN
from .coordinator import LinearUpdateCoordinator

SCAN_INTERVAL = timedelta(seconds=60)
PARALLEL_UPDATES = 0
SUPPORTED_SUBDEVICES = ["Light"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Linear Garage Door cover."""
    coordinator: LinearUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    data = coordinator.data

    async_add_entities(
        LinearLightEntity(
            device_id=device_id,
            device_name=data[device_id]["name"],
            subdevice=subdev,
            config_entry=config_entry,
            coordinator=coordinator,
        )
        for device_id in data
        for subdev in data[device_id]["subdevices"]
        if subdev in SUPPORTED_SUBDEVICES
    )


class LinearLightEntity(LinearEntity, LightEntity):
    """Light for Linear devices."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        device_id: str,
        device_name: str,
        subdevice: str,
        config_entry: ConfigEntry,
        coordinator: LinearUpdateCoordinator,
    ) -> None:
        """Initialize the light."""
        super().__init__(
            device_id=device_id,
            device_name=device_name,
            subdevice=subdevice,
            config_entry=config_entry,
            coordinator=coordinator,
        )

        self._attr_name = subdevice

    @property
    def is_on(self) -> bool:
        """Return if the light is on or not."""
        return bool(
            self.coordinator.data[self._device_id]["subdevices"][self._subdevice][
                "On_B"
            ]
            == "true"
        )

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        return int(
            int(
                self.coordinator.data[self._device_id]["subdevices"][self._subdevice][
                    "On_P"
                ]
            )
            / 100
            * 255
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""

        linear = Linear()
        await linear.login(
            email=self._config_entry.data["email"],
            password=self._config_entry.data["password"],
            device_id=self._config_entry.data["device_id"],
            client_session=async_get_clientsession(self.hass),
        )

        if not kwargs:
            await linear.operate_device(self._device_id, self._subdevice, "On")
        elif ATTR_BRIGHTNESS in kwargs:
            brightness = str(math.floor((kwargs[ATTR_BRIGHTNESS] / 255) * 100))
            await linear.operate_device(
                self._device_id, self._subdevice, f"DimPercent:{brightness}"
            )

        await linear.close()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""

        linear = Linear()
        await linear.login(
            email=self._config_entry.data["email"],
            password=self._config_entry.data["password"],
            device_id=self._config_entry.data["device_id"],
            client_session=async_get_clientsession(self.hass),
        )
        await linear.operate_device(self._device_id, self._subdevice, "Off")
        await linear.close()
