"""Support for The Things Network entities."""

from datetime import timedelta
import logging
from typing import Any, Optional

from ttn_client import TTN_SensorValue

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    OPTIONS_DEVICE_NAME,
    OPTIONS_FIELD_CONTEXT_RECENT_TIME_S,
    OPTIONS_FIELD_DEVICE_CLASS,
    OPTIONS_FIELD_ICON,
    OPTIONS_FIELD_NAME,
    OPTIONS_FIELD_PICTURE,
    OPTIONS_FIELD_SUPPORTED_FEATURES,
    OPTIONS_FIELD_UNIT_MEASUREMENT,
)
from .entry_settings import TTN_EntrySettings

_LOGGER = logging.getLogger(__name__)


class TTN_Entity(CoordinatorEntity, Entity):
    """Representation of a The Things Network Data Storage sensor."""

    @staticmethod
    def get_unique_id(device_id, field_id):
        """Get unique_id which is derived from device_id and field_id."""
        return f"{device_id}_{field_id}"

    def __init__(self, entry, coordinator, ttn_value: TTN_SensorValue) -> None:
        """Initialize a The Things Network Data Storage sensor."""

        self.__entry = entry
        self.__ttn_value = ttn_value

        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, context=self.unique_id)

        self.to_be_added = True
        self.to_be_removed = False

        # Values from options
        self._unit_of_measurement = None
        self.__device_class = None
        self.__icon = None
        self.__picture = None
        self.__supported_features = None
        self.__context_recent_time_s = 5

        self.__refresh_names()

    # -----------------------------------------------------------#
    # Methods to keep list of entities, device_ids and field_ids #
    # -----------------------------------------------------------#

    async def async_added_to_hass(self):
        """Remember added entity - see exits method below."""

        await super().async_added_to_hass()
        TTN_EntrySettings(self.__entry).get_entities()[self.unique_id] = self

    async def async_will_remove_from_hass(self):
        """Remove entity from hass."""

        await super().async_will_remove_from_hass()
        TTN_EntrySettings(self.__entry).get_entities().pop(self.unique_id)

    @staticmethod
    def exits(entry, device_id, field_id):
        """Check if an entry for this device/field already exists in HASS.

        It is used to avoid creating duplicates while still allowing adding new devices/fields without restarting the adapter.
        """
        return (
            TTN_Entity.get_unique_id(device_id, field_id)
            in TTN_EntrySettings(entry).get_entities()
        )

    # ---------------
    # Coordinator method
    # ---------------

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        my_entity_update = self.coordinator.data.get(self.device_id, {}).get(
            self.field_id, None
        )
        if (
            my_entity_update
            and my_entity_update.received_at > self.__ttn_value.received_at
        ):
            _LOGGER.debug(
                "Received update for %s: %s", self.unique_id, my_entity_update
            )
            self.__ttn_value = my_entity_update
            self.async_write_ha_state()

    # ---------------
    # standard Entity propertiess
    # ---------------

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self.get_unique_id(self.device_id, self.field_id)

    @property
    def name(self) -> Optional[str]:
        """Return the name of the entity."""
        return self.__name

    @property
    def state(self):
        """Return the state of the entity."""
        return self.__ttn_value.value

    @property
    def entitiy_state_attributes(self):
        """Return the state attributes of the sensor."""
        # if self._ttn_data_storage.data is not None:

        # TBD - add more info in the TTN upstream message such as signal strength, transmission time, etc
        return {}

    @property
    def capability_attributes(self) -> Optional[dict[str, Any]]:
        """Return the capability attributes.

        Attributes that explain the capabilities of an entity.

        Implemented by component base class. Convention for attribute names
        is lowercase snake_case.
        """
        return {}

    @property
    def state_attributes(self) -> Optional[dict[str, Any]]:
        """Return the state attributes.

        Implemented by component base class. Convention for attribute names
        is lowercase snake_case.
        """
        return {}

    @property
    def extra_state_attributes(self) -> Optional[dict[str, Any]]:
        """Return device specific state attributes.

        Implemented by platform classes. Convention for attribute names
        is lowercase snake_case.
        """
        return {}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes.

        Implemented by platform classes.
        """

        return DeviceInfo(
            {
                "identifiers": {
                    # Serial numbers are unique identifiers within a specific domain
                    (DOMAIN, self.device_id)
                },
                "name": self.device_name,
                # TBD - add more info in the TTN upstream message such as signal strength, transmission time, etc
            }
        )

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self.__device_class

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        return self.__icon

    @property
    def entity_picture(self) -> Optional[str]:
        """Return the entity picture to use in the frontend, if any."""
        return self.__picture

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return False

    @property
    def force_update(self) -> bool:
        """Return True if state updates should be forced.

        If True, a state change will be triggered anytime the state property is
        updated, not just when the value changes.
        """
        return False

    @property
    def supported_features(self) -> Optional[int]:
        """Flag supported features."""
        return self.__supported_features

    @property
    def context_recent_time(self) -> timedelta:
        """Time that a context is considered recent."""
        return timedelta(seconds=self.__context_recent_time_s)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    # ---------------
    # TTN integration additional methods
    # ---------------
    @property
    def device_id(self):
        """Return device_id."""
        return self.__ttn_value.device_id

    @property
    def field_id(self):
        """Return field_id."""
        return self.__ttn_value.field_id

    @property
    def device_name(self):
        """Return device_name."""
        return self.__device_name

    def __refresh_names(self):
        device_name = self.device_id
        field_name = self.field_id

        # Device options
        device_opts = TTN_EntrySettings(self.__entry).get_device_options(self.device_id)
        device_name = device_opts.get(OPTIONS_DEVICE_NAME, device_name)

        # Field options
        field_opts = TTN_EntrySettings(self.__entry).get_field_options(
            self.device_id, self.field_id
        )
        field_name = field_opts.get(OPTIONS_FIELD_NAME, field_name)
        self._unit_of_measurement = field_opts.get(OPTIONS_FIELD_UNIT_MEASUREMENT, None)
        self.__device_class = field_opts.get(OPTIONS_FIELD_DEVICE_CLASS, None)
        self.__icon = field_opts.get(OPTIONS_FIELD_ICON, None)
        self.__picture = field_opts.get(OPTIONS_FIELD_PICTURE, None)
        self.__supported_features = field_opts.get(
            OPTIONS_FIELD_SUPPORTED_FEATURES, None
        )
        self.__context_recent_time_s = field_opts.get(
            OPTIONS_FIELD_CONTEXT_RECENT_TIME_S, 5
        )

        self.__device_name = device_name
        self.__name = f"{device_name} {field_name}"
