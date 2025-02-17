"""Demo platform that offers a fake button entity."""

from __future__ import annotations

import logging

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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import now

from .const import DOMAIN, SIGNAL_DATA_UPDATED

_LOGGER = logging.getLogger(__name__)

DATETIME_UPDATE = ButtonEntityDescription(
    key="datetime",
    translation_key="set_datetime",
    icon="mdi:calendar-clock",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo button platform."""
    assert entry.unique_id is not None

    set_datetime_entity = None

    @callback
    def _async_on_data_updated(
        data: ThermoProBluetoothDeviceData,
        service_info: BluetoothServiceInfoBleak,
        update: SensorUpdate,
    ) -> None:
        nonlocal set_datetime_entity
        _LOGGER.debug(
            "got update data=%s update=%s service_info=%s", data, update, service_info
        )

        assert entry.unique_id is not None
        assert None in update.devices
        assert update.devices[None].model is not None

        if update.devices[None].model not in ("TP358", "TP393"):
            return

        if not set_datetime_entity:
            name = update.devices[None].name
            assert name is not None
            set_datetime_entity = ThermoProDateTimeButtonEntity(
                address=entry.unique_id,
                device_name=name,
                description=DATETIME_UPDATE,
            )

            async_add_entities(
                [
                    set_datetime_entity,
                ]
            )

        if service_info.connectable and not set_datetime_entity.available:
            set_datetime_entity.set_available(True)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{SIGNAL_DATA_UPDATED}_{entry.entry_id}", _async_on_data_updated
        )
    )

    @callback
    def _async_on_unavailable(service_info: BluetoothServiceInfoBleak) -> None:
        _LOGGER.debug("service info unavailable %s", service_info)
        if set_datetime_entity:
            set_datetime_entity.set_available(False)

    entry.async_on_unload(
        async_track_unavailable(
            hass, _async_on_unavailable, entry.unique_id, connectable=True
        )
    )


class ThermoProDateTimeButtonEntity(
    ButtonEntity,
):
    """Representation of a ThermoProDateTime button entity."""

    def __init__(
        self, address: str, device_name: str, description: ButtonEntityDescription
    ) -> None:
        """Initialize the thermopro datetime button entity."""
        self.address = address
        self.entity_description = description
        self._attr_unique_id = f"{device_name}-{description.key}"

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(dr.CONNECTION_BLUETOOTH, address)},
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._attr_available

    def set_available(self, available: bool) -> None:
        """Set availability of ButtonEntity."""
        self._attr_available = available

    async def async_press(self) -> None:
        """Set Date&Time for a given device."""
        address = self.address

        assert address is not None

        ble = async_ble_device_from_address(self.hass, address, connectable=True)

        assert ble is not None

        tpd = ThermoProDevice(ble)

        await tpd.set_datetime(now(), False)
