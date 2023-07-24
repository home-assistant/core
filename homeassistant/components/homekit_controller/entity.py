"""Homekit Controller entities."""
from __future__ import annotations

from typing import Any

from aiohomekit.model import Accessory
from aiohomekit.model.characteristics import (
    Characteristic,
    CharacteristicPermissions,
    CharacteristicsTypes,
)
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.typing import ConfigType

from .connection import HKDevice, valid_serial_number
from .utils import folded_name


class HomeKitEntity(Entity):
    """Representation of a Home Assistant HomeKit device."""

    _attr_should_poll = False

    def __init__(self, accessory: HKDevice, devinfo: ConfigType) -> None:
        """Initialise a generic HomeKit device."""
        self._accessory = accessory
        self._aid = devinfo["aid"]
        self._iid = devinfo["iid"]
        self._char_name: str | None = None
        self.all_characteristics: set[tuple[int, int]] = set()
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
            self._accessory.async_subscribe(
                self.all_characteristics, self._async_write_ha_state
            )
        )

        self._accessory.add_pollable_characteristics(self.pollable_characteristics)
        await self._accessory.add_watchable_characteristics(
            self.watchable_characteristics
        )

    async def async_will_remove_from_hass(self) -> None:
        """Prepare to be removed from hass."""
        self._accessory.remove_pollable_characteristics(self._aid)
        self._accessory.remove_watchable_characteristics(self._aid)

    async def async_put_characteristics(self, characteristics: dict[str, Any]) -> None:
        """Write characteristics to the device.

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

        self.all_characteristics.update(self.pollable_characteristics)
        self.all_characteristics.update(self.watchable_characteristics)

    def _setup_characteristic(self, char: Characteristic) -> None:
        """Configure an entity based on a HomeKit characteristics metadata."""
        # Build up a list of (aid, iid) tuples to poll on update()
        if CharacteristicPermissions.paired_read in char.perms:
            self.pollable_characteristics.append((self._aid, char.iid))

        # Build up a list of (aid, iid) tuples to subscribe to
        if CharacteristicPermissions.events in char.perms:
            self.watchable_characteristics.append((self._aid, char.iid))

        if self._char_name is None:
            self._char_name = char.service.value(CharacteristicsTypes.NAME)

    @property
    def old_unique_id(self) -> str:
        """Return the OLD ID of this device."""
        info = self.accessory_info
        serial = info.value(CharacteristicsTypes.SERIAL_NUMBER)
        if valid_serial_number(serial):
            return f"homekit-{serial}-{self._iid}"
        # Some accessories do not have a serial number
        return f"homekit-{self._accessory.unique_id}-{self._aid}-{self._iid}"

    @property
    def unique_id(self) -> str:
        """Return the ID of this device."""
        return f"{self._accessory.unique_id}_{self._aid}_{self._iid}"

    @property
    def default_name(self) -> str | None:
        """Return the default name of the device."""
        return None

    @property
    def name(self) -> str | None:
        """Return the name of the device if any."""
        accessory_name = self.accessory.name
        # If the service has a name char, use that, if not
        # fallback to the default name provided by the subclass
        device_name = self._char_name or self.default_name
        folded_device_name = folded_name(device_name or "")
        folded_accessory_name = folded_name(accessory_name)
        if device_name:
            # Sometimes the device name includes the accessory
            # name already like My ecobee Occupancy / My ecobee
            if folded_device_name.startswith(folded_accessory_name):
                return device_name
            if (
                folded_accessory_name not in folded_device_name
                and folded_device_name not in folded_accessory_name
            ):
                return f"{accessory_name} {device_name}"
        return accessory_name

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

    async def async_update(self) -> None:
        """Update the entity."""
        await self._accessory.async_request_update()


class AccessoryEntity(HomeKitEntity):
    """A HomeKit entity that is related to an entire accessory rather than a specific service or characteristic."""

    @property
    def old_unique_id(self) -> str:
        """Return the old ID of this device."""
        serial = self.accessory_info.value(CharacteristicsTypes.SERIAL_NUMBER)
        return f"homekit-{serial}-aid:{self._aid}"

    @property
    def unique_id(self) -> str:
        """Return the ID of this device."""
        return f"{self._accessory.unique_id}_{self._aid}"


class CharacteristicEntity(HomeKitEntity):
    """A HomeKit entity that is related to an single characteristic rather than a whole service.

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
    def old_unique_id(self) -> str:
        """Return the old ID of this device."""
        serial = self.accessory_info.value(CharacteristicsTypes.SERIAL_NUMBER)
        return f"homekit-{serial}-aid:{self._aid}-sid:{self._char.service.iid}-cid:{self._char.iid}"

    @property
    def unique_id(self) -> str:
        """Return the ID of this device."""
        return f"{self._accessory.unique_id}_{self._aid}_{self._char.service.iid}_{self._char.iid}"
