"""Common classes and elements for Omnilogic Integration."""

from datetime import timedelta
import logging

from omnilogic import OmniLogicException

from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import ATTR_IDENTIFIERS, ATTR_MANUFACTURER, ATTR_MODEL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OmniLogicUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching update data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: str,
        name: str,
        polling_interval: int,
    ):
        """Initialize the global Omnilogic data updater."""
        self.api = api

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=name,
            update_interval=timedelta(seconds=polling_interval),
        )

    async def _async_update_data(self):
        """Fetch data from OmniLogic."""
        try:
            data = await self.api.get_telemetry_data()

        except OmniLogicException as error:
            raise UpdateFailed("Error updating from OmniLogic: %s" % error) from error

        return data


class OmniLogicEntity(CoordinatorEntity):
    """Defines the base OmniLogic entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        kind: str,
        name: str,
        backyard: dict,
        bow: dict,
        icon: str,
        entitydata: dict,
    ):
        """Initialize the OmniLogic Entity."""
        super().__init__(coordinator)

        backyard_name = backyard["BackyardName"].replace(" ", "_")
        if bow != {}:
            bow_name = bow["Name"].replace(" ", "_")

            entity_name = f"{backyard_name}_{bow_name}_{kind}"
        else:
            entity_name = f"{backyard_name}_{kind}"

        self._kind = kind
        self._name = name
        self._unique_id = entity_name
        self._backyard = backyard
        self._backyard_name = backyard["BackyardName"]
        self._state = None
        self._icon = icon
        self._bow = bow
        self.entity_data = entitydata
        self._attrs = {}
        self._msp_system_id = backyard["systemId"]
        self.alarms = []
        self._unsub_dispatcher = None

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the entity."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the attributes."""
        return self._attrs

    @property
    def device_info(self):
        """Define the device as back yard/MSP System."""

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._msp_system_id)},
            ATTR_NAME: self._backyard.get("BackyardName"),
            ATTR_MANUFACTURER: "Hayward",
            ATTR_MODEL: "OmniLogic",
        }
