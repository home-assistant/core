"""Thermopro button platform."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from thermopro_ble import SensorUpdate, ThermoProBluetoothDeviceData, ThermoProDevice

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_track_unavailable,
)
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import now

from .const import DOMAIN, SIGNAL_AVAILABILITY_UPDATED, SIGNAL_DATA_UPDATED

PARALLEL_UPDATES = 1  # one connection at a time


@dataclass(kw_only=True, frozen=True)
class ThermoProButtonEntityDescription(ButtonEntityDescription):
    """Describe a ThermoPro button entity."""

    press_action_fn: Callable[[HomeAssistant, str], Coroutine[None, Any, Any]]


async def _async_set_datetime(hass: HomeAssistant, address: str) -> None:
    """Set Date&Time for a given device."""
    ble_device = async_ble_device_from_address(hass, address, connectable=True)
    assert ble_device is not None
    await ThermoProDevice(ble_device).set_datetime(now(), am_pm=False)


BUTTON_ENTITIES: tuple[ThermoProButtonEntityDescription, ...] = (
    ThermoProButtonEntityDescription(
        key="datetime",
        translation_key="set_datetime",
        icon="mdi:calendar-clock",
        entity_category=EntityCategory.CONFIG,
        press_action_fn=_async_set_datetime,
    ),
)

MODELS_THAT_SUPPORT_BUTTONS = {"TP358", "TP393"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the thermopro button platform."""
    address = entry.unique_id
    assert address is not None
    availability_signal = f"{SIGNAL_AVAILABILITY_UPDATED}_{entry.entry_id}"
    entity_added = False

    @callback
    def _async_on_data_updated(
        data: ThermoProBluetoothDeviceData,
        service_info: BluetoothServiceInfoBleak,
        update: SensorUpdate,
    ) -> None:
        nonlocal entity_added
        sensor_device_info = update.devices[data.primary_device_id]
        if sensor_device_info.model not in MODELS_THAT_SUPPORT_BUTTONS:
            return

        if not entity_added:
            name = sensor_device_info.name
            assert name is not None
            entity_added = True
            async_add_entities(
                ThermoProButtonEntity(
                    description=description,
                    data=data,
                    availability_signal=availability_signal,
                    address=address,
                )
                for description in BUTTON_ENTITIES
            )

        if service_info.connectable:
            async_dispatcher_send(hass, availability_signal, True)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{SIGNAL_DATA_UPDATED}_{entry.entry_id}", _async_on_data_updated
        )
    )


class ThermoProButtonEntity(ButtonEntity):
    """Representation of a ThermoPro button entity."""

    _attr_has_entity_name = True
    entity_description: ThermoProButtonEntityDescription

    def __init__(
        self,
        description: ThermoProButtonEntityDescription,
        data: ThermoProBluetoothDeviceData,
        availability_signal: str,
        address: str,
    ) -> None:
        """Initialize the thermopro button entity."""
        self.entity_description = description
        self._address = address
        self._availability_signal = availability_signal
        self._attr_unique_id = f"{address}-{description.key}"
        self._attr_device_info = dr.DeviceInfo(
            name=data.get_device_name(),
            identifiers={(DOMAIN, address)},
            connections={(dr.CONNECTION_BLUETOOTH, address)},
        )

    async def async_added_to_hass(self) -> None:
        """Connect availability dispatcher."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._availability_signal,
                self._async_on_availability_changed,
            )
        )
        self.async_on_remove(
            async_track_unavailable(
                self.hass, self._async_on_unavailable, self._address, connectable=True
            )
        )

    @callback
    def _async_on_unavailable(self, _: BluetoothServiceInfoBleak) -> None:
        self._async_on_availability_changed(False)

    @callback
    def _async_on_availability_changed(self, available: bool) -> None:
        self._attr_available = available
        self.async_write_ha_state()

    async def async_press(self) -> None:
        """Execute the press action for the entity."""
        await self.entity_description.press_action_fn(self.hass, self._address)
