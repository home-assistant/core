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

    availability_topic = f"{SIGNAL_AVAILABILITY_UPDATED}_{entry.entry_id}"
    entity_added = False

    @callback
    def _async_on_data_updated(
        data: ThermoProBluetoothDeviceData,
        service_info: BluetoothServiceInfoBleak,
        update: SensorUpdate,
    ) -> None:
        nonlocal entity_added
        _LOGGER.debug(
            "got update data=%s update=%s service_info=%s", data, update, service_info
        )

        assert entry.unique_id is not None
        assert None in update.devices
        assert update.devices[None].model is not None

        if update.devices[None].model not in ("TP358", "TP393"):
            return

        if not entity_added:
            name = update.devices[None].name
            assert name is not None

            entity_added = True

            async_add_entities(
                [
                    ThermoProDateTimeButtonEntity(
                        availability_topic=availability_topic,
                        address=entry.unique_id,
                        device_name=name,
                        description=DATETIME_UPDATE,
                    )
                ]
            )

        if service_info.connectable:
            _LOGGER.debug("sending availability '%s' for %s", True, availability_topic)
            async_dispatcher_send(
                hass,
                availability_topic,
                True,
            )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{SIGNAL_DATA_UPDATED}_{entry.entry_id}", _async_on_data_updated
        )
    )


class ThermoProDateTimeButtonEntity(
    ButtonEntity,
):
    """Representation of a ThermoProDateTime button entity."""

    def __init__(
        self,
        availability_topic: str,
        address: str,
        device_name: str,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the thermopro datetime button entity."""
        self.address = address
        self.entity_description = description
        self.availability_topic = availability_topic
        self._attr_unique_id = f"{address}-{description.key}"

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(dr.CONNECTION_BLUETOOTH, address)},
        )

    async def async_added_to_hass(self) -> None:
        """Connect availability dispatcher."""
        await super().async_added_to_hass()
        _LOGGER.debug(
            "registering for availability callback for %s", self.availability_topic
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.availability_topic,
                self._async_on_availability_changed,
            )
        )

        self.async_on_remove(
            async_track_unavailable(
                self.hass, self._async_on_unavailable, self.address, connectable=True
            )
        )

    @callback
    def _async_on_unavailable(self, service_info: BluetoothServiceInfoBleak) -> None:
        _LOGGER.debug("service info unavailable %s", service_info)
        self._async_on_availability_changed(False)

    @callback
    def _async_on_availability_changed(self, available: bool) -> None:
        _LOGGER.debug(
            "got availability callback with '%s' for %s",
            available,
            self.availability_topic,
        )
        self._attr_available = available
        self.async_write_ha_state()  # write state to state machine

    async def async_press(self) -> None:
        """Set Date&Time for a given device."""
        address = self.address
        ble = async_ble_device_from_address(self.hass, address, connectable=True)

        assert ble is not None

        tpd = ThermoProDevice(ble)

        await tpd.set_datetime(now(), False)
