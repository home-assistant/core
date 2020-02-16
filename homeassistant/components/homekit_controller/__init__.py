"""Support for Homekit device discovery."""
import logging

import homekit
from homekit.model.characteristics import CharacteristicsTypes

from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from .config_flow import normalize_hkid
from .connection import HKDevice, get_accessory_information
from .const import CONTROLLER, DOMAIN, ENTITY_MAP, KNOWN_DEVICES
from .storage import EntityMapStorage

_LOGGER = logging.getLogger(__name__)


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
        self._chars = {}
        self.setup()

        self._signals = []

    async def async_added_to_hass(self):
        """Entity added to hass."""
        self._signals.append(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                self._accessory.signal_state_updated, self.async_state_changed
            )
        )

        self._accessory.add_pollable_characteristics(self.pollable_characteristics)

    async def async_will_remove_from_hass(self):
        """Prepare to be removed from hass."""
        self._accessory.remove_pollable_characteristics(self._aid)

        for signal_remove in self._signals:
            signal_remove()
        self._signals.clear()

    @property
    def should_poll(self) -> bool:
        """Return False.

        Data update is triggered from HKDevice.
        """
        return False

    def setup(self):
        """Configure an entity baed on its HomeKit characteristics metadata."""
        accessories = self._accessory.accessories

        get_uuid = CharacteristicsTypes.get_uuid
        characteristic_types = [get_uuid(c) for c in self.get_characteristic_types()]

        self.pollable_characteristics = []
        self._chars = {}
        self._char_names = {}

        for accessory in accessories:
            if accessory["aid"] != self._aid:
                continue
            self._accessory_info = get_accessory_information(accessory)
            for service in accessory["services"]:
                if service["iid"] != self._iid:
                    continue
                for char in service["characteristics"]:
                    try:
                        uuid = CharacteristicsTypes.get_uuid(char["type"])
                    except KeyError:
                        # If a KeyError is raised its a non-standard
                        # characteristic. We must ignore it in this case.
                        continue
                    if uuid not in characteristic_types:
                        continue
                    self._setup_characteristic(char)

    def _setup_characteristic(self, char):
        """Configure an entity based on a HomeKit characteristics metadata."""
        # Build up a list of (aid, iid) tuples to poll on update()
        self.pollable_characteristics.append((self._aid, char["iid"]))

        # Build a map of ctype -> iid
        short_name = CharacteristicsTypes.get_short(char["type"])
        self._chars[short_name] = char["iid"]
        self._char_names[char["iid"]] = short_name

        # Callback to allow entity to configure itself based on this
        # characteristics metadata (valid values, value ranges, features, etc)
        setup_fn_name = escape_characteristic_name(short_name)
        setup_fn = getattr(self, f"_setup_{setup_fn_name}", None)
        if not setup_fn:
            return
        setup_fn(char)

    def get_hk_char_value(self, characteristic_type):
        """Return the value for a given characteristic type enum."""
        state = self._accessory.current_state.get(self._aid)
        if not state:
            return None
        char = self._chars.get(CharacteristicsTypes.get_short(characteristic_type))
        if not char:
            return None
        return state.get(char, {}).get("value")

    @callback
    def async_state_changed(self):
        """Collect new data from bridge and update the entity state in hass."""
        accessory_state = self._accessory.current_state.get(self._aid, {})
        for iid, result in accessory_state.items():
            # No value so don't process this result
            if "value" not in result:
                continue

            # Unknown iid - this is probably for a sibling service that is part
            # of the same physical accessory. Ignore it.
            if iid not in self._char_names:
                continue

            # Callback to update the entity with this characteristic value
            char_name = escape_characteristic_name(self._char_names[iid])
            update_fn = getattr(self, f"_update_{char_name}", None)
            if not update_fn:
                continue

            update_fn(result["value"])

        self.async_write_ha_state()

    @property
    def unique_id(self):
        """Return the ID of this device."""
        serial = self._accessory_info["serial-number"]
        return f"homekit-{serial}-{self._iid}"

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._accessory_info.get("name")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._accessory.available

    @property
    def device_info(self):
        """Return the device info."""
        accessory_serial = self._accessory_info["serial-number"]

        device_info = {
            "identifiers": {(DOMAIN, "serial-number", accessory_serial)},
            "name": self._accessory_info["name"],
            "manufacturer": self._accessory_info.get("manufacturer", ""),
            "model": self._accessory_info.get("model", ""),
            "sw_version": self._accessory_info.get("firmware.revision", ""),
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

    conn_info = conn.connection_info

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={
            (DOMAIN, "serial-number", conn_info["serial-number"]),
            (DOMAIN, "accessory-id", conn.unique_id),
        },
        name=conn.name,
        manufacturer=conn_info.get("manufacturer"),
        model=conn_info.get("model"),
        sw_version=conn_info.get("firmware.revision"),
    )

    return True


async def async_setup(hass, config):
    """Set up for Homekit devices."""
    map_storage = hass.data[ENTITY_MAP] = EntityMapStorage(hass)
    await map_storage.async_initialize()

    hass.data[CONTROLLER] = homekit.Controller()
    hass.data[KNOWN_DEVICES] = {}

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
