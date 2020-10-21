"""Support for Homekit device discovery."""
from typing import Any, Dict

import aiohomekit
from aiohomekit.model import Accessory
from aiohomekit.model.characteristics import (
    Characteristic,
    CharacteristicPermissions,
    CharacteristicsTypes,
)
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.components import zeroconf
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import Entity

from .config_flow import normalize_hkid
from .connection import HKDevice
from .const import CONTROLLER, DOMAIN, ENTITY_MAP, KNOWN_DEVICES, TRIGGERS
from .storage import EntityMapStorage


def escape_characteristic_name(char_name):
    """Escape any dash or dots in a characteristics name."""
    return char_name.replace("-", "_").replace(".", "_")


class HomeKitEntity(Entity):
    """Representation of a Home Assistant HomeKit device."""

    def __init__(self, accessory, devinfo):
        """Initialise a generic HomeKit device."""
        self._accessory = accessory
        self._aid = devinfo["aid"]
        self._iid = devinfo["iid"]
        self._features = 0
        self.setup()

        self._signals = []

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

    async def async_added_to_hass(self):
        """Entity added to hass."""
        self._signals.append(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                self._accessory.signal_state_updated, self.async_write_ha_state
            )
        )

        self._accessory.add_pollable_characteristics(self.pollable_characteristics)
        self._accessory.add_watchable_characteristics(self.watchable_characteristics)

    async def async_will_remove_from_hass(self):
        """Prepare to be removed from hass."""
        self._accessory.remove_pollable_characteristics(self._aid)
        self._accessory.remove_watchable_characteristics(self._aid)

        for signal_remove in self._signals:
            signal_remove()
        self._signals.clear()

    async def async_put_characteristics(self, characteristics: Dict[str, Any]):
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

    @property
    def should_poll(self) -> bool:
        """Return False.

        Data update is triggered from HKDevice.
        """
        return False

    def setup(self):
        """Configure an entity baed on its HomeKit characteristics metadata."""
        self.pollable_characteristics = []
        self.watchable_characteristics = []

        char_types = self.get_characteristic_types()

        # Setup events and/or polling for characteristics directly attached to this entity
        for char in self.service.characteristics.filter(char_types=char_types):
            self._setup_characteristic(char)

        # Setup events and/or polling for characteristics attached to sub-services of this
        # entity (like an INPUT_SOURCE).
        for service in self.accessory.services.filter(parent_service=self.service):
            for char in service.characteristics.filter(char_types=char_types):
                self._setup_characteristic(char)

    def _setup_characteristic(self, char: Characteristic):
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
        serial = self.accessory_info.value(CharacteristicsTypes.SERIAL_NUMBER)
        return f"homekit-{serial}-{self._iid}"

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self.accessory_info.value(CharacteristicsTypes.NAME)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._accessory.available

    @property
    def device_info(self):
        """Return the device info."""
        info = self.accessory_info
        accessory_serial = info.value(CharacteristicsTypes.SERIAL_NUMBER)

        device_info = {
            "identifiers": {(DOMAIN, "serial-number", accessory_serial)},
            "name": info.value(CharacteristicsTypes.NAME),
            "manufacturer": info.value(CharacteristicsTypes.MANUFACTURER, ""),
            "model": info.value(CharacteristicsTypes.MODEL, ""),
            "sw_version": info.value(CharacteristicsTypes.FIRMWARE_REVISION, ""),
        }

        # Some devices only have a single accessory - we don't add a
        # via_device otherwise it would be self referential.
        bridge_serial = self._accessory.connection_info["serial-number"]
        if accessory_serial != bridge_serial:
            device_info["via_device"] = (DOMAIN, "serial-number", bridge_serial)

        return device_info

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        raise NotImplementedError


async def async_setup_entry(hass, entry):
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


async def async_setup(hass, config):
    """Set up for Homekit devices."""
    map_storage = hass.data[ENTITY_MAP] = EntityMapStorage(hass)
    await map_storage.async_initialize()

    zeroconf_instance = await zeroconf.async_get_instance(hass)
    hass.data[CONTROLLER] = aiohomekit.Controller(zeroconf_instance=zeroconf_instance)
    hass.data[KNOWN_DEVICES] = {}
    hass.data[TRIGGERS] = {}

    return True


async def async_unload_entry(hass, entry):
    """Disconnect from HomeKit devices before unloading entry."""
    hkid = entry.data["AccessoryPairingID"]

    if hkid in hass.data[KNOWN_DEVICES]:
        connection = hass.data[KNOWN_DEVICES][hkid]
        await connection.async_unload()

    return True


async def async_remove_entry(hass, entry):
    """Cleanup caches before removing config entry."""
    hkid = entry.data["AccessoryPairingID"]
    hass.data[ENTITY_MAP].async_delete_map(hkid)
