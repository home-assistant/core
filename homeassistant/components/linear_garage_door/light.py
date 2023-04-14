"""Linear garage door light."""

from datetime import timedelta
import math
from typing import Any

from linear_garage_door import Linear

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LinearUpdateCoordinator

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 1
SUPPORTED_SUBDEVICES = ["Light"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Linear Garage Door cover."""
    coordinator: LinearUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]
    data = coordinator.data

    device_list = []

    for device_id in data:
        for subdev in data[device_id]["subdevices"]:
            if subdev in SUPPORTED_SUBDEVICES:
                device_list.append(
                    LinearLightEntity(
                        device_id=device_id,
                        device_name=data[device_id]["name"],
                        subdevice=subdev,
                        config_entry=config_entry,
                        coordinator=coordinator,
                    )
                )

    async_add_entities(device_list)


class LinearLightEntity(CoordinatorEntity[LinearUpdateCoordinator], LightEntity):
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
        super().__init__(coordinator)

        self._attr_has_entity_name = True
        self._attr_name = subdevice
        self._attr_unique_id = f"{device_id}-{subdevice}"
        self._config_entry = config_entry
        self._device_id = device_id
        self._device_name = device_name
        self._subdevice = subdevice

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info of a light."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            default_manufacturer="Linear",
            default_model="Garage Door Opener",
        )

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
        else:
            if ATTR_BRIGHTNESS in kwargs:
                brightness = str(math.floor((kwargs[ATTR_BRIGHTNESS] / 255) * 100))
                await linear.operate_device(
                    self._device_id,
                    self._subdevice,
                    "DimPercent:" + brightness,
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
