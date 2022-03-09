"""C.M.I binary sensor platform."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_HOST,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CMIDataUpdateCoordinator
from .const import API_VERSION, DEFAULT_DEVICE_CLASS_MAP, DEVICE_TYPE, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entries."""
    coordinator: CMIDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[DeviceChannelBinary] = []

    device_registry = dr.async_get(hass)

    for ent in coordinator.data:
        inputs: dict = coordinator.data[ent]["IB"]
        outputs: dict = coordinator.data[ent]["OB"]

        for ch_id in inputs:
            channel_in: DeviceChannelBinary = DeviceChannelBinary(
                coordinator, ent, ch_id, "IB"
            )
            entities.append(channel_in)

        for ch_id in outputs:
            channel_out: DeviceChannelBinary = DeviceChannelBinary(
                coordinator, ent, ch_id, "OB"
            )
            entities.append(channel_out)

        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, ent)},
            manufacturer="Technische Alternative",
            name=coordinator.data[ent][DEVICE_TYPE],
            model=coordinator.data[ent][DEVICE_TYPE],
            sw_version=coordinator.data[ent][API_VERSION],
            configuration_url=coordinator.data[ent][CONF_HOST],
        )

    async_add_entities(entities)


class DeviceChannelBinary(CoordinatorEntity, BinarySensorEntity):
    """Representation of an C.M.I channel."""

    def __init__(
        self,
        coordinator: CMIDataUpdateCoordinator,
        node_id: str,
        channel_id: str,
        input_type: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._id = channel_id
        self._node_id = node_id
        self._input_type = input_type
        self._coordinator = coordinator

        channel_raw: dict[str, Any] = self._coordinator.data[self._node_id][
            self._input_type
        ][self._id]

        name: str = channel_raw["name"]
        mode: str = channel_raw["mode"]

        self._attr_name: str = name or f"Node: {self._node_id} - {mode} {self._id}"
        self._attr_unique_id: str = f"ta-cmi-{self._node_id}-{mode}{self._id}"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        channel_raw: dict[str, Any] = self._coordinator.data[self._node_id][
            self._input_type
        ][self._id]

        value: str = channel_raw["value"]

        return value in ("on", "yes")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""

        device_api_type: str = self._coordinator.data[self._node_id][API_VERSION]
        device_name: str = self._coordinator.data[self._node_id][DEVICE_TYPE]

        return {
            ATTR_NAME: device_name,
            ATTR_IDENTIFIERS: {(DOMAIN, self._node_id)},
            ATTR_MANUFACTURER: "Technische Alternative",
            ATTR_MODEL: device_name,
            ATTR_SW_VERSION: device_api_type,
        }

    @property
    def device_class(self) -> str:
        """Return the device class of this entity, if any."""
        channel_raw: dict[str, Any] = self._coordinator.data[self._node_id][
            self._input_type
        ][self._id]

        device_class: str = channel_raw["device_class"]

        if device_class is None:
            return DEFAULT_DEVICE_CLASS_MAP.get(channel_raw["unit"], "")  # type: ignore[unreachable]

        return device_class
