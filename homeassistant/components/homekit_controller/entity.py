"""Homekit Controller entities."""
from __future__ import annotations

import contextlib
from typing import Any

from aiohomekit.model.characteristics import (
    EVENT_CHARACTERISTICS,
    Characteristic,
    CharacteristicPermissions,
    CharacteristicsTypes,
)
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

from .connection import HKDevice, valid_serial_number
from .utils import folded_name


class HomeKitEntity(Entity):
    """Representation of a Home Assistant HomeKit device."""

    _attr_should_poll = False
    pollable_characteristics: list[tuple[int, int]]
    watchable_characteristics: list[tuple[int, int]]
    all_characteristics: set[tuple[int, int]]
    all_iids: set[int]
    accessory_info: Service

    def __init__(self, accessory: HKDevice, devinfo: ConfigType) -> None:
        """Initialise a generic HomeKit device."""
        self._accessory = accessory
        self._aid: int = devinfo["aid"]
        self._iid: int = devinfo["iid"]
        self._entity_key: tuple[int, int | None, int | None] = (
            self._aid,
            None,
            self._iid,
        )
        self._char_name: str | None = None
        self._char_subscription: CALLBACK_TYPE | None = None
        self.async_setup()
        self._attr_unique_id = f"{accessory.unique_id}_{self._aid}_{self._iid}"
        super().__init__()

    @callback
    def _async_handle_entity_removed(self) -> None:
        """Handle entity removal."""
        # We call _async_unsubscribe_chars as soon as we
        # know the entity is about to be removed so we do not try to
        # update characteristics that no longer exist. It will get
        # called in async_will_remove_from_hass as well, but that is
        # too late.
        self._async_unsubscribe_chars()
        self.hass.async_create_task(self.async_remove(force_remove=True))

    @callback
    def _async_remove_entity_if_accessory_or_service_disappeared(self) -> bool:
        """Handle accessory or service disappearance."""
        entity_map = self._accessory.entity_map
        if not (
            accessory := entity_map.aid_or_none(self._aid)
        ) or not accessory.services.iid_or_none(self._iid):
            self._async_handle_entity_removed()
            return True
        return False

    @callback
    def _async_config_changed(self) -> None:
        """Handle accessory discovery changes."""
        if not self._async_remove_entity_if_accessory_or_service_disappeared():
            self._async_reconfigure()

    @callback
    def _async_clear_property_cache(self, properties: tuple[str, ...]) -> None:
        """Clear the cache of properties."""
        for prop in properties:
            # suppress is slower than try-except-pass, but
            # we do not expect to have many properties to clear
            # or this to be called often.
            with contextlib.suppress(AttributeError):
                delattr(self, prop)

    @callback
    def _async_reconfigure(self) -> None:
        """Reconfigure the entity."""
        self._async_unsubscribe_chars()
        self.async_setup()
        self._async_subscribe_chars()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Entity added to hass."""
        self._async_subscribe_chars()
        self.async_on_remove(
            self._accessory.async_subscribe_config_changed(self._async_config_changed)
        )
        self.async_on_remove(
            self._accessory.async_subscribe_availability(self._async_write_ha_state)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Prepare to be removed from hass."""
        self._async_unsubscribe_chars()
        self._accessory.async_entity_key_removed(self._entity_key)

    @callback
    def _async_unsubscribe_chars(self) -> None:
        """Handle unsubscribing from characteristics."""
        if self._char_subscription:
            self._char_subscription()
            self._char_subscription = None
        self._accessory.remove_pollable_characteristics(self.pollable_characteristics)
        self._accessory.remove_watchable_characteristics(self.watchable_characteristics)

    @callback
    def _async_subscribe_chars(self) -> None:
        """Handle registering characteristics to watch and subscribe."""
        self._accessory.add_pollable_characteristics(self.pollable_characteristics)
        self._accessory.add_watchable_characteristics(self.watchable_characteristics)
        self._char_subscription = self._accessory.async_subscribe(
            self.all_characteristics, self._async_write_ha_state
        )

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

    @callback
    def async_setup(self) -> None:
        """Configure an entity based on its HomeKit characteristics metadata."""
        accessory = self._accessory
        self.accessory = accessory.entity_map.aid(self._aid)
        self.service = self.accessory.services.iid(self._iid)
        accessory_info = self.accessory.services.first(
            service_type=ServicesTypes.ACCESSORY_INFORMATION
        )
        assert accessory_info
        self.accessory_info = accessory_info
        # If we re-setup, we need to make sure we make new
        # lists since we passed them to the connection before
        # and we do not want to inadvertently modify the old
        # ones.
        self.pollable_characteristics = []
        self.watchable_characteristics = []
        self.all_characteristics = set()
        self.all_iids = set()

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
        self.all_iids = {iid for _, iid in self.all_characteristics}

    def _setup_characteristic(self, char: Characteristic) -> None:
        """Configure an entity based on a HomeKit characteristics metadata."""
        # Build up a list of (aid, iid) tuples to poll on update()
        if (
            CharacteristicPermissions.paired_read in char.perms
            and char.type not in EVENT_CHARACTERISTICS
        ):
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
    def default_name(self) -> str | None:
        """Return the default name of the device."""
        return None

    @property
    def name(self) -> str | None:
        """Return the name of the device if any."""
        accessory_name = self.accessory.name
        # If the service has a name char, use that, if not
        # fallback to the default name provided by the subclass
        if device_name := self._char_name or self.default_name:
            folded_device_name = folded_name(device_name)
            folded_accessory_name = folded_name(accessory_name)
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
        all_iids = self.all_iids
        for char in self.service.characteristics:
            if char.iid in all_iids and not char.available:
                return False
        return self._accessory.available

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

    def __init__(self, accessory: HKDevice, devinfo: ConfigType) -> None:
        """Initialise a generic HomeKit accessory."""
        super().__init__(accessory, devinfo)
        self._attr_unique_id = f"{accessory.unique_id}_{self._aid}"

    @property
    def old_unique_id(self) -> str:
        """Return the old ID of this device."""
        serial = self.accessory_info.value(CharacteristicsTypes.SERIAL_NUMBER)
        return f"homekit-{serial}-aid:{self._aid}"


class BaseCharacteristicEntity(HomeKitEntity):
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
        self._entity_key = (self._aid, self._iid, char.iid)

    @callback
    def _async_remove_entity_if_characteristics_disappeared(self) -> bool:
        """Handle characteristic disappearance."""
        if (
            not self._accessory.entity_map.aid(self._aid)
            .services.iid(self._iid)
            .get_char_by_iid(self._char.iid)
        ):
            self._async_handle_entity_removed()
            return True
        return False

    @callback
    def _async_config_changed(self) -> None:
        """Handle accessory discovery changes."""
        if (
            not self._async_remove_entity_if_accessory_or_service_disappeared()
            and not self._async_remove_entity_if_characteristics_disappeared()
        ):
            super()._async_reconfigure()


class CharacteristicEntity(BaseCharacteristicEntity):
    """A HomeKit entity that is related to an single characteristic rather than a whole service.

    This is typically used to expose additional sensor, binary_sensor or number entities that don't belong with
    the service entity.
    """

    def __init__(
        self, accessory: HKDevice, devinfo: ConfigType, char: Characteristic
    ) -> None:
        """Initialise a generic single characteristic HomeKit entity."""
        super().__init__(accessory, devinfo, char)
        self._attr_unique_id = (
            f"{accessory.unique_id}_{self._aid}_{char.service.iid}_{char.iid}"
        )

    @property
    def old_unique_id(self) -> str:
        """Return the old ID of this device."""
        serial = self.accessory_info.value(CharacteristicsTypes.SERIAL_NUMBER)
        return f"homekit-{serial}-aid:{self._aid}-sid:{self._char.service.iid}-cid:{self._char.iid}"
