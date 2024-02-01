"""Representation of Z-Wave humidifiers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.humidity_control import (
    HUMIDITY_CONTROL_SETPOINT_PROPERTY,
    HumidityControlMode,
    HumidityControlSetpointType,
)
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.value import Value as ZwaveValue

from homeassistant.components.humidifier import (
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CLIENT, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class ZwaveHumidifierEntityDescriptionRequiredKeys:
    """A class for humidifier entity description required keys."""

    # The "on" control mode for this entity, e.g. HUMIDIFY for humidifier
    on_mode: HumidityControlMode

    # The "on" control mode for the inverse entity, e.g. DEHUMIDIFY for humidifier
    inverse_mode: HumidityControlMode

    # The setpoint type controlled by this entity
    setpoint_type: HumidityControlSetpointType


@dataclass(frozen=True)
class ZwaveHumidifierEntityDescription(
    HumidifierEntityDescription, ZwaveHumidifierEntityDescriptionRequiredKeys
):
    """A class that describes the humidifier or dehumidifier entity."""


HUMIDIFIER_ENTITY_DESCRIPTION = ZwaveHumidifierEntityDescription(
    key="humidifier",
    device_class=HumidifierDeviceClass.HUMIDIFIER,
    on_mode=HumidityControlMode.HUMIDIFY,
    inverse_mode=HumidityControlMode.DEHUMIDIFY,
    setpoint_type=HumidityControlSetpointType.HUMIDIFIER,
)


DEHUMIDIFIER_ENTITY_DESCRIPTION = ZwaveHumidifierEntityDescription(
    key="dehumidifier",
    device_class=HumidifierDeviceClass.DEHUMIDIFIER,
    on_mode=HumidityControlMode.DEHUMIDIFY,
    inverse_mode=HumidityControlMode.HUMIDIFY,
    setpoint_type=HumidityControlSetpointType.DEHUMIDIFIER,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave humidifier from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_humidifier(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Humidifier."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        entities: list[ZWaveBaseEntity] = []

        if (
            str(HumidityControlMode.HUMIDIFY.value)
            in info.primary_value.metadata.states
        ):
            entities.append(
                ZWaveHumidifier(
                    config_entry, driver, info, HUMIDIFIER_ENTITY_DESCRIPTION
                )
            )

        if (
            str(HumidityControlMode.DEHUMIDIFY.value)
            in info.primary_value.metadata.states
        ):
            entities.append(
                ZWaveHumidifier(
                    config_entry, driver, info, DEHUMIDIFIER_ENTITY_DESCRIPTION
                )
            )

        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{HUMIDIFIER_DOMAIN}",
            async_add_humidifier,
        )
    )


class ZWaveHumidifier(ZWaveBaseEntity, HumidifierEntity):
    """Representation of a Z-Wave Humidifier or Dehumidifier."""

    entity_description: ZwaveHumidifierEntityDescription
    _current_mode: ZwaveValue
    _setpoint: ZwaveValue | None = None

    def __init__(
        self,
        config_entry: ConfigEntry,
        driver: Driver,
        info: ZwaveDiscoveryInfo,
        description: ZwaveHumidifierEntityDescription,
    ) -> None:
        """Initialize humidifier."""
        super().__init__(config_entry, driver, info)

        self.entity_description = description

        self._attr_name = f"{self._attr_name} {description.key}"
        self._attr_unique_id = f"{self._attr_unique_id}_{description.key}"

        self._current_mode = self.info.primary_value

        self._setpoint = self.get_zwave_value(
            HUMIDITY_CONTROL_SETPOINT_PROPERTY,
            command_class=CommandClass.HUMIDITY_CONTROL_SETPOINT,
            value_property_key=description.setpoint_type,
            add_to_watched_value_ids=True,
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        if (value := self._current_mode.value) is None:
            return None
        return int(value) in [self.entity_description.on_mode, HumidityControlMode.AUTO]

    def _supports_inverse_mode(self) -> bool:
        return (
            str(self.entity_description.inverse_mode.value)
            in self._current_mode.metadata.states
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on device."""
        if (value := self._current_mode.value) is None:
            return
        mode = int(value)
        if mode == HumidityControlMode.OFF:
            new_mode = self.entity_description.on_mode
        elif mode == self.entity_description.inverse_mode:
            new_mode = HumidityControlMode.AUTO
        else:
            return

        await self._async_set_value(self._current_mode, new_mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off device."""
        if (value := self._current_mode.value) is None:
            return
        mode = int(value)
        if mode == HumidityControlMode.AUTO:
            if self._supports_inverse_mode():
                new_mode = self.entity_description.inverse_mode
            else:
                new_mode = HumidityControlMode.OFF
        elif mode == self.entity_description.on_mode:
            new_mode = HumidityControlMode.OFF
        else:
            return

        await self._async_set_value(self._current_mode, new_mode)

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        if not self._setpoint or self._setpoint.value is None:
            return None
        return int(self._setpoint.value)

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        if self._setpoint:
            await self._async_set_value(self._setpoint, humidity)

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        min_value = DEFAULT_MIN_HUMIDITY
        if self._setpoint and self._setpoint.metadata.min:
            min_value = self._setpoint.metadata.min
        return min_value

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        max_value = DEFAULT_MAX_HUMIDITY
        if self._setpoint and self._setpoint.metadata.max:
            max_value = self._setpoint.metadata.max
        return max_value
