"""Demo platform that offers a fake button entity."""

from __future__ import annotations

import logging

from thermopro_ble import ThermoProBluetoothDeviceData, ThermoProDevice

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_process_advertisements,
)
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import now

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATETIME_UPDATE = ButtonEntityDescription(
    key="datetime",
    translation_key="set_datetime",
    icon="mdi:calendar-clock",
    entity_category=EntityCategory.CONFIG,
)

ADDITIONAL_DISCOVERY_TIMEOUT = 60


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo button platform."""

    assert config_entry.unique_id is not None

    data = ThermoProBluetoothDeviceData()
    parsed = None

    def no_more_updates(service_info: BluetoothServiceInfoBleak) -> bool:
        nonlocal parsed
        parsed = data.update(service_info)
        return None in parsed.devices

    try:
        await async_process_advertisements(
            hass,
            no_more_updates,
            {"address": config_entry.unique_id, "connectable": False},
            BluetoothScanningMode.ACTIVE,
            ADDITIONAL_DISCOVERY_TIMEOUT,
        )
    except TimeoutError:
        _LOGGER.debug(
            (
                "timeout while waiting for ThermoPro device %s"
                "- additional features will not be available"
            ),
            config_entry.unique_id,
        )
        return

    assert parsed is not None

    _LOGGER.debug("got parsed devices %s", parsed.devices)

    assert None in parsed.devices
    assert parsed.title is not None

    if parsed.devices[None].model not in ("TP358", "TP393"):
        return

    async_add_entities(
        [
            ThermoProDateTimeButtonEntity(
                address=config_entry.unique_id,
                title=parsed.title,
                description=DATETIME_UPDATE,
            ),
        ]
    )


class ThermoProDateTimeButtonEntity(
    ButtonEntity,
):
    """Representation of a ThermoProDateTime button entity."""

    def __init__(
        self, address: str, title: str, description: ButtonEntityDescription
    ) -> None:
        """Initialize the Demo button entity."""
        self.address = address
        self.entity_description = description
        self._attr_unique_id = f"{title}-{description.key}"

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(dr.CONNECTION_BLUETOOTH, address)},
        )

    async def async_press(self) -> None:
        """Send out a persistent notification."""
        address = self.address

        assert address is not None

        ble = async_ble_device_from_address(self.hass, address, connectable=True)

        assert ble is not None

        tpd = ThermoProDevice(ble)

        await tpd.set_datetime(now(), False)
