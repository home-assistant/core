"""Cover entity for Linear Garage Doors."""

from datetime import timedelta
from typing import Any

from linear_garage_door import Linear

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LinearUpdateCoordinator

SUPPORTED_SUBDEVICES = ["GDO"]
PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Linear Garage Door cover."""
    coordinator: LinearUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    data = coordinator.data

    device_list: list[LinearCoverEntity] = []

    for device_id in data:
        device_list.extend(
            LinearCoverEntity(
                device_id=device_id,
                device_name=data[device_id]["name"],
                subdevice=subdev,
                config_entry=config_entry,
                coordinator=coordinator,
            )
            for subdev in data[device_id]["subdevices"]
            if subdev in SUPPORTED_SUBDEVICES
        )
    async_add_entities(device_list)


class LinearCoverEntity(CoordinatorEntity[LinearUpdateCoordinator], CoverEntity):
    """Representation of a Linear cover."""

    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(
        self,
        device_id: str,
        device_name: str,
        subdevice: str,
        config_entry: ConfigEntry,
        coordinator: LinearUpdateCoordinator,
    ) -> None:
        """Init with device ID and name."""
        super().__init__(coordinator)

        self._attr_has_entity_name = True
        self._device_id = device_id
        self._device_name = device_name
        self._subdevice = subdevice
        self._attr_device_class = CoverDeviceClass.GARAGE
        self._attr_unique_id = f"{device_id}-{subdevice}"
        self._config_entry = config_entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info of a garage door."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            default_manufacturer="Linear",
            default_model="Garage Door Opener",
        )

    @property
    def is_closed(self) -> bool:
        """Return if cover is closed."""
        return bool(
            self.coordinator.data[self._device_id]["subdevices"][self._subdevice][
                "Open_B"
            ]
            == "false"
        )

    @property
    def is_opened(self) -> bool:
        """Return if cover is open."""
        return bool(
            self.coordinator.data[self._device_id]["subdevices"][self._subdevice][
                "Open_B"
            ]
            == "true"
        )

    @property
    def is_opening(self) -> bool:
        """Return if cover is opening."""
        return bool(
            self.coordinator.data[self._device_id]["subdevices"][self._subdevice].get(
                "Opening_P"
            )
            == "0"
        )

    @property
    def is_closing(self) -> bool:
        """Return if cover is closing."""
        return bool(
            self.coordinator.data[self._device_id]["subdevices"][self._subdevice].get(
                "Closing_P"
            )
            == "100"
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the garage door."""
        if self.is_closed:
            return

        linear = Linear()

        await linear.login(
            email=self._config_entry.data["email"],
            password=self._config_entry.data["password"],
            device_id=self._config_entry.data["device_id"],
            client_session=async_get_clientsession(self.hass),
        )

        await linear.operate_device(self._device_id, self._subdevice, "Close")
        await linear.close()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the garage door."""
        if self.is_opened:
            return

        linear = Linear()

        await linear.login(
            email=self._config_entry.data["email"],
            password=self._config_entry.data["password"],
            device_id=self._config_entry.data["device_id"],
            client_session=async_get_clientsession(self.hass),
        )

        await linear.operate_device(self._device_id, self._subdevice, "Open")
        await linear.close()
