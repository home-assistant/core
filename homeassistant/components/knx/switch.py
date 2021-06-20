"""Support for KNX/IP switches."""
from __future__ import annotations

from typing import Any

from xknx import XKNX
from xknx.devices import Sensor as XknxSensor, Switch as XknxSwitch

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, KNX_ADDRESS
from .knx_entity import KnxEntity
from .schema import SwitchSchema


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up switch(es) for KNX platform."""
    if not discovery_info or not discovery_info["platform_config"]:
        return

    platform_config = discovery_info["platform_config"]
    xknx: XKNX = hass.data[DOMAIN].xknx

    entities = []
    for entity_config in platform_config:
        entities.append(KNXSwitch(xknx, entity_config))

    async_add_entities(entities)


class KNXSwitch(KnxEntity, SwitchEntity, RestoreEntity):
    """Representation of a KNX switch."""

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize of KNX switch."""
        self._device: XknxSwitch
        super().__init__(
            device=XknxSwitch(
                xknx,
                name=config[CONF_NAME],
                group_address=config[KNX_ADDRESS],
                group_address_state=config.get(SwitchSchema.CONF_STATE_ADDRESS),
                invert=config[SwitchSchema.CONF_INVERT],
            )
        )
        self._unique_id = f"{self._device.switch.group_address}"
        self._total_energy_sensor = XknxSensor(
            xknx,
            name="Total Energy kWh",
            group_address_state=config.get(
                SwitchSchema.CONF_TOTAL_ENERGY_USAGE_STATE_ADDRESS
            ),
            value_type="active_energy_kwh",
        )
        self._current_energy_sensor = XknxSensor(
            xknx,
            name="Current Energy W",
            group_address_state=config.get(
                SwitchSchema.CONF_CURRENT_POWER_STATE_ADDRESS
            ),
            value_type="power",
        )

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if not self._device.switch.readable and (
            last_state := await self.async_get_last_state()
        ):
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                self._device.switch.value = last_state.state == STATE_ON

        if self._current_energy_sensor.sensor_value.readable:
            self._current_energy_sensor.register_device_updated_cb(
                self.after_update_callback
            )

        if self._total_energy_sensor.sensor_value.readable:
            self._total_energy_sensor.register_device_updated_cb(
                self.after_update_callback
            )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        await super().async_will_remove_from_hass()
        self._total_energy_sensor.unregister_device_updated_cb(
            self.after_update_callback
        )
        self._current_energy_sensor.unregister_device_updated_cb(
            self.after_update_callback
        )

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return bool(self._device.state)

    @property
    def current_power_w(self) -> float | None:
        """Return the current power usage in W."""
        if self._current_energy_sensor.sensor_value.readable:
            return self._current_energy_sensor.resolve_state()

        return None

    @property
    def today_energy_kwh(self) -> float | None:
        """Return the today total energy usage in kWh."""
        if self._total_energy_sensor.sensor_value.readable:
            return self._total_energy_sensor.resolve_state()

        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._device.set_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._device.set_off()
