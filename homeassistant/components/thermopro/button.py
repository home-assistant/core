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
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import now

from .const import DOMAIN, SIGNAL_AVAILABILITY_UPDATED, SIGNAL_DATA_UPDATED

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
                entry_id=entry.entry_id,
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
            _LOGGER.debug("sending availability '%s' for %s", True, entry.entry_id)
            async_dispatcher_send(
                hass,
                f"{SIGNAL_AVAILABILITY_UPDATED}_{entry.entry_id}_button_datetime",
                True,
            )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{SIGNAL_DATA_UPDATED}_{entry.entry_id}", _async_on_data_updated
        )
    )

    @callback
    def _async_on_unavailable(service_info: BluetoothServiceInfoBleak) -> None:
        _LOGGER.debug("service info unavailable %s", service_info)
        if set_datetime_entity:
            _LOGGER.debug("sending availability '%s' for %s", False, entry.entry_id)
            async_dispatcher_send(
                hass,
                f"{SIGNAL_AVAILABILITY_UPDATED}_{entry.entry_id}_button_datetime",
                False,
            )

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
        self,
        entry_id: str,
        address: str,
        device_name: str,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the thermopro datetime button entity."""
        self.address = address
        self.entity_description = description
        self.entry_id = entry_id
        self._attr_unique_id = f"{device_name}-{description.key}"

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(dr.CONNECTION_BLUETOOTH, address)},
        )

    async def async_added_to_hass(self) -> None:
        """Connect availability dispatcher."""
        _LOGGER.debug("registering for availability callback for %s", self.entry_id)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                "{SIGNAL_AVAILABILITY_UPDATED}_{self.entry_id}_button_datetime",
                self._async_on_available_changed,
            )
        )
        await super().async_added_to_hass()

    @callback
    def _async_on_available_changed(self, available: bool) -> None:
        _LOGGER.debug(
            "got availability callback with '%s' for %s", available, self.entry_id
        )
        self._attr_available = available
        self.async_write_ha_state()  # write state to state machine

    async def async_press(self) -> None:
        """Set Date&Time for a given device."""
        address = self.address

        assert address is not None

        ble = async_ble_device_from_address(self.hass, address, connectable=True)

        assert ble is not None

        tpd = ThermoProDevice(ble)

        await tpd.set_datetime(now(), False)
