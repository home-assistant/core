"""Support for The Things Network entities."""

from abc import ABC, abstractmethod
import logging
from typing import TYPE_CHECKING, Optional

from ttn_client import TTNBaseValue, TTNSensorValue

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import TTNCoordinator

from .const import (
    CONF_APP_ID,
    OPTIONS_DEVICE_NAME,
    OPTIONS_FIELD_ICON,
    OPTIONS_FIELD_NAME,
    OPTIONS_FIELD_PICTURE,
    OPTIONS_FIELD_UNIT_MEASUREMENT,
)
from .entry_settings import TTN_EntrySettings

_LOGGER = logging.getLogger(__name__)


class TTN_Entity(CoordinatorEntity, Entity, ABC):
    """Representation of a The Things Network Data Storage sensor."""

    @staticmethod
    def get_unique_id(device_id: str, field_id: str) -> str:
        """Get unique_id which is derived from device_id and field_id."""
        return f"{device_id}_{field_id}"

    def __init__(
        self,
        entry: "ConfigEntry",
        coordinator: "TTNCoordinator",
        ttn_value: TTNSensorValue,
    ) -> None:
        """Initialize a The Things Network Data Storage sensor."""

        self.__entry = entry
        self._ttn_value = ttn_value

        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, context=self.unique_id)

        # Values from options
        self._unit_of_measurement = None
        self.__icon = None
        self.__picture = None

        self.__refresh_names()

    # -----------------------------------------------------------#
    # Methods to keep list of entities
    #
    # NOTE: the entity_registry helper cannot be used here as it
    # returns instances created in the past, even if they are
    # not longer available in TTN
    # -----------------------------------------------------------#

    async def async_added_to_hass(self) -> None:
        """Remember added entity - see exits method below."""

        await super().async_added_to_hass()
        TTN_EntrySettings(self.__entry).get_entities()[self.unique_id] = self

    async def async_will_remove_from_hass(self) -> None:
        """Remove entity from hass."""

        await super().async_will_remove_from_hass()
        TTN_EntrySettings(self.__entry).get_entities().pop(self.unique_id)

    @staticmethod
    def exits(entry: "ConfigEntry", device_id: str, field_id: str) -> bool:
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
            and my_entity_update.received_at > self._ttn_value.received_at
        ):
            _LOGGER.debug(
                "Received update for %s: %s", self.unique_id, my_entity_update
            )
            self._ttn_value = my_entity_update
            self.async_write_ha_state()

    # ---------------
    # standard Entity propertiess
    # ---------------

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.get_unique_id(self.device_id, self.field_id)

    @property
    def name(self) -> Optional[str]:
        """Return the name of the entity."""
        return self.__name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes.

        Implemented by platform classes.
        """

        return DeviceInfo(
            {
                "identifiers": {
                    # Serial numbers are unique identifiers within a specific domain
                    (self.__entry.data[CONF_APP_ID], self.device_id)
                },
                "name": self.device_name,
                # TBD - add more info in the TTN upstream message such as signal strength, transmission time, etc
            }
        )

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        return self.__icon

    @property
    def entity_picture(self) -> Optional[str]:
        """Return the entity picture to use in the frontend, if any."""
        return self.__picture

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    # ---------------
    # TTN integration additional methods
    # ---------------
    @property
    def device_id(self) -> str:
        """Return device_id."""
        return str(self._ttn_value.device_id)

    @property
    def field_id(self) -> str:
        """Return field_id."""
        return str(self._ttn_value.field_id)

    @property
    def device_name(self) -> str:
        """Return device_name."""
        return self.__device_name

    @staticmethod
    @abstractmethod
    def manages_uplink(
        entrySettings: TTN_EntrySettings, ttn_value: TTNBaseValue
    ) -> bool:
        """Check if this class maps to this ttn_value."""

    def __refresh_names(self) -> None:
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
        self.__icon = field_opts.get(OPTIONS_FIELD_ICON, None)
        self.__picture = field_opts.get(OPTIONS_FIELD_PICTURE, None)

        self.__device_name = device_name
        self.__name = f"{device_name} {field_name}"
