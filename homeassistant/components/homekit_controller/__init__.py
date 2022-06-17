"""Support for Homekit device discovery."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohomekit
from aiohomekit.model import Accessory
from aiohomekit.model.characteristics import (
    Characteristic,
    CharacteristicPermissions,
    CharacteristicsTypes,
)
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_IDENTIFIERS, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.typing import ConfigType

from .config_flow import normalize_hkid
from .connection import HKDevice, valid_serial_number
from .const import ENTITY_MAP, KNOWN_DEVICES, TRIGGERS
from .storage import EntityMapStorage
from .utils import async_get_controller

_LOGGER = logging.getLogger(__name__)


class HomeKitEntity(Entity):
    """Representation of a Home Assistant HomeKit device."""

    _attr_should_poll = False

    def __init__(self, accessory: HKDevice, devinfo: ConfigType) -> None:
        """Initialise a generic HomeKit device."""
        self._accessory = accessory
        self._aid = devinfo["aid"]
        self._iid = devinfo["iid"]
        self._features = 0
        self.setup()

        super().__init__()

    @property
    def accessory(self) -> Accessory:
        """Return an Accessory model that this entity is attached to."""
        return self._accessory.entity_map.aid(self._aid)

    @property
    def accessory_info(self) -> Service:
        """Information about the make and model of an accessory."""
        return self.accessory.services.first(
            service_type=ServicesTypes.ACCESSORY_INFORMATION
        )

    @property
    def service(self) -> Service:
        """Return a Service model that this entity is attached to."""
        return self.accessory.services.iid(self._iid)

    async def async_added_to_hass(self) -> None:
        """Entity added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._accessory.signal_state_updated,
                self.async_write_ha_state,
            )
        )

        self._accessory.add_pollable_characteristics(self.pollable_characteristics)
        self._accessory.add_watchable_characteristics(self.watchable_characteristics)

    async def async_will_remove_from_hass(self) -> None:
        """Prepare to be removed from hass."""
        self._accessory.remove_pollable_characteristics(self._aid)
        self._accessory.remove_watchable_characteristics(self._aid)

    async def async_put_characteristics(self, characteristics: dict[str, Any]) -> None:
        """
        Write characteristics to the device.

        A characteristic type is unique within a service, but in order to write
        to a named characteristic on a bridge we need to turn its type into
        an aid and iid, and send it as a list of tuples, which is what this
        helper does.

        E.g. you can do:

            await entity.async_put_characteristics({
                CharacteristicsTypes.ON: True
            })
        """
        payload = self.service.build_update(characteristics)
        return await self._accessory.put_characteristics(payload)

    def setup(self) -> None:
        """Configure an entity based on its HomeKit characteristics metadata."""
        self.pollable_characteristics: list[tuple[int, int]] = []
        self.watchable_characteristics: list[tuple[int, int]] = []

        char_types = self.get_characteristic_types()

        # Setup events and/or polling for characteristics directly attached to this entity
        for char in self.service.characteristics.filter(char_types=char_types):
            self._setup_characteristic(char)

        # Setup events and/or polling for characteristics attached to sub-services of this
        # entity (like an INPUT_SOURCE).
        for service in self.accessory.services.filter(parent_service=self.service):
            for char in service.characteristics.filter(char_types=char_types):
                self._setup_characteristic(char)

    def _setup_characteristic(self, char: Characteristic) -> None:
        """Configure an entity based on a HomeKit characteristics metadata."""
        # Build up a list of (aid, iid) tuples to poll on update()
        if CharacteristicPermissions.paired_read in char.perms:
            self.pollable_characteristics.append((self._aid, char.iid))

        # Build up a list of (aid, iid) tuples to subscribe to
        if CharacteristicPermissions.events in char.perms:
            self.watchable_characteristics.append((self._aid, char.iid))

    @property
    def unique_id(self) -> str:
        """Return the ID of this device."""
        info = self.accessory_info
        serial = info.value(CharacteristicsTypes.SERIAL_NUMBER)
        if valid_serial_number(serial):
            return f"homekit-{serial}-{self._iid}"
        # Some accessories do not have a serial number
        return f"homekit-{self._accessory.unique_id}-{self._aid}-{self._iid}"

    @property
    def name(self) -> str | None:
        """Return the name of the device if any."""
        return self.accessory.name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._accessory.available and self.service.available

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self._accessory.device_info_for_accessory(self.accessory)

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        raise NotImplementedError


class AccessoryEntity(HomeKitEntity):
    """A HomeKit entity that is related to an entire accessory rather than a specific service or characteristic."""

    @property
    def unique_id(self) -> str:
        """Return the ID of this device."""
        serial = self.accessory_info.value(CharacteristicsTypes.SERIAL_NUMBER)
        return f"homekit-{serial}-aid:{self._aid}"


class CharacteristicEntity(HomeKitEntity):
    """
    A HomeKit entity that is related to an single characteristic rather than a whole service.

    This is typically used to expose additional sensor, binary_sensor or number entities that don't belong with
    the service entity.
    """

    def __init__(
        self, accessory: HKDevice, devinfo: ConfigType, char: Characteristic
    ) -> None:
        """Initialise a generic single characteristic HomeKit entity."""
        self._char = char
        super().__init__(accessory, devinfo)

    @property
    def unique_id(self) -> str:
        """Return the ID of this device."""
        serial = self.accessory_info.value(CharacteristicsTypes.SERIAL_NUMBER)
        return f"homekit-{serial}-aid:{self._aid}-sid:{self._char.service.iid}-cid:{self._char.iid}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a HomeKit connection on a config entry."""
    conn = HKDevice(hass, entry, entry.data)
    hass.data[KNOWN_DEVICES][conn.unique_id] = conn

    # For backwards compat
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=normalize_hkid(conn.unique_id)
        )

    if not await conn.async_setup():
        del hass.data[KNOWN_DEVICES][conn.unique_id]
        raise ConfigEntryNotReady

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up for Homekit devices."""
    map_storage = hass.data[ENTITY_MAP] = EntityMapStorage(hass)
    await map_storage.async_initialize()

    await async_get_controller(hass)

    hass.data[KNOWN_DEVICES] = {}
    hass.data[TRIGGERS] = {}

    async def _async_stop_homekit_controller(event: Event) -> None:
        await asyncio.gather(
            *(
                connection.async_unload()
                for connection in hass.data[KNOWN_DEVICES].values()
            )
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_homekit_controller)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Disconnect from HomeKit devices before unloading entry."""
    hkid = entry.data["AccessoryPairingID"]

    if hkid in hass.data[KNOWN_DEVICES]:
        connection = hass.data[KNOWN_DEVICES][hkid]
        await connection.async_unload()

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Cleanup caches before removing config entry."""
    hkid = entry.data["AccessoryPairingID"]

    # Remove cached type data from .storage/homekit_controller-entity-map
    hass.data[ENTITY_MAP].async_delete_map(hkid)

    controller = await async_get_controller(hass)

    # Remove the pairing on the device, making the device discoverable again.
    # Don't reuse any objects in hass.data as they are already unloaded
    controller.load_pairing(hkid, dict(entry.data))
    try:
        await controller.remove_pairing(hkid)
    except aiohomekit.AccessoryDisconnectedError:
        _LOGGER.warning(
            "Accessory %s was removed from HomeAssistant but was not reachable "
            "to properly unpair. It may need resetting before you can use it with "
            "HomeKit again",
            entry.title,
        )


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove homekit_controller config entry from a device."""
    hkid = config_entry.data["AccessoryPairingID"]
    connection: HKDevice = hass.data[KNOWN_DEVICES][hkid]
    return not device_entry.identifiers.intersection(
        identifier
        for accessory in connection.entity_map.accessories
        for identifier in connection.device_info_for_accessory(accessory)[
            ATTR_IDENTIFIERS
        ]
    )
