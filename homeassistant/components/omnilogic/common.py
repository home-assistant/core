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

        parsed_data = {}

        for backyard in data:
            backyard_id = backyard.get("systemId")
            parsed_data[backyard_id, None, None] = backyard
            parsed_data[backyard_id, None, None]["type"] = "backyard"

            for relay in backyard["Relays"]:
                parsed_data[backyard_id, None, relay.get("systemId")] = relay
                parsed_data[backyard_id, None, relay.get("systemId")]["type"] = "relay"
                parsed_data[backyard_id, None, relay.get("systemId")][
                    "parent_backyard"
                ] = (backyard_id, None, None)
                parsed_data[backyard_id, None, relay.get("systemId")][
                    "parent_bow"
                ] = None

            for bow in backyard["BOWS"]:
                bow_id = bow.get("systemId")
                parsed_data[backyard_id, bow_id, None] = bow
                parsed_data[backyard_id, bow_id, None]["type"] = "bow"
                parsed_data[backyard_id, bow_id, None]["parent_backyard"] = (
                    backyard_id,
                    None,
                    None,
                )
                parsed_data[backyard_id, bow_id, None]["parent_bow"] = None

                if "Filter" in bow:
                    parsed_data[
                        backyard_id, bow_id, bow["Filter"].get("systemId")
                    ] = bow["Filter"]
                    parsed_data[backyard_id, bow_id, bow["Filter"].get("systemId")][
                        "type"
                    ] = "filter"
                    parsed_data[backyard_id, bow_id, bow["Filter"].get("systemId")][
                        "parent_backyard"
                    ] = (backyard_id, None, None)
                    parsed_data[backyard_id, bow_id, bow["Filter"].get("systemId")][
                        "parent_bow"
                    ] = (backyard_id, bow_id, None)

                if "Heater" in bow:
                    parsed_data[
                        backyard_id, bow_id, bow["Heater"].get("systemId")
                    ] = bow["Heater"]
                    parsed_data[backyard_id, bow_id, bow["Heater"].get("systemId")][
                        "type"
                    ] = "heater"
                    parsed_data[backyard_id, bow_id, bow["Heater"].get("systemId")][
                        "parent_backyard"
                    ] = (backyard_id, None, None)
                    parsed_data[backyard_id, bow_id, bow["Heater"].get("systemId")][
                        "parent_bow"
                    ] = (backyard_id, bow_id, None)

                if "Chlorinator" in bow:
                    parsed_data[
                        backyard_id, bow_id, bow["Chlorinator"].get("systemId")
                    ] = bow["Chlorinator"]
                    parsed_data[
                        backyard_id, bow_id, bow["Chlorinator"].get("systemId")
                    ]["type"] = "chlorinator"
                    parsed_data[
                        backyard_id, bow_id, bow["Chlorinator"].get("systemId")
                    ]["parent_backyard"] = (backyard_id, None, None)
                    parsed_data[
                        backyard_id, bow_id, bow["Chlorinator"].get("systemId")
                    ]["parent_bow"] = (backyard_id, bow_id, None)

                if "CSAD" in bow:
                    parsed_data[backyard_id, bow_id, bow["CSAD"].get("systemId")] = bow[
                        "CSAD"
                    ]
                    parsed_data[backyard_id, bow_id, bow["CSAD"].get("systemId")][
                        "type"
                    ] = "csad"
                    parsed_data[backyard_id, bow_id, bow["CSAD"].get("systemId")][
                        "parent_backyard"
                    ] = (backyard_id, None, None)
                    parsed_data[backyard_id, bow_id, bow["CSAD"].get("systemId")][
                        "parent_bow"
                    ] = (backyard_id, bow_id, None)

                for light in bow["Lights"]:
                    parsed_data[backyard_id, bow_id, light.get("systemId")] = light
                    parsed_data[backyard_id, bow_id, light.get("systemId")][
                        "type"
                    ] = "light"
                    parsed_data[backyard_id, bow_id, light.get("systemId")][
                        "parent_backyard"
                    ] = (backyard_id, None, None)
                    parsed_data[backyard_id, bow_id, light.get("systemId")][
                        "parent_bow"
                    ] = (backyard_id, bow_id, None)

                for relay in bow["Relays"]:
                    parsed_data[backyard_id, bow_id, relay.get("systemId")] = relay
                    parsed_data[backyard_id, bow_id, relay.get("systemId")][
                        "type"
                    ] = "relay"
                    parsed_data[backyard_id, bow_id, relay.get("systemId")][
                        "parent_backyard"
                    ] = (backyard_id, None, None)
                    parsed_data[backyard_id, bow_id, relay.get("systemId")][
                        "parent_bow"
                    ] = (backyard_id, bow_id, None)

                for pump in bow["Pumps"]:
                    parsed_data[backyard_id, bow_id, pump.get("systemId")] = pump
                    parsed_data[backyard_id, bow_id, pump.get("systemId")][
                        "type"
                    ] = "pump"
                    parsed_data[backyard_id, bow_id, pump.get("systemId")][
                        "parent_backyard"
                    ] = (backyard_id, None, None)
                    parsed_data[backyard_id, bow_id, pump.get("systemId")][
                        "parent_bow"
                    ] = (backyard_id, bow_id, None)

        return parsed_data


class OmniLogicEntity(CoordinatorEntity):
    """Defines the base OmniLogic entity."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        kind: str,
        name: str,
        entity_data: dict,
        entity: tuple,
        icon: str,
    ):
        """Initialize the OmniLogic Entity."""
        super().__init__(coordinator)

        bow_name = None

        if entity_data.get("parent_backyard") is None:
            backyard_name = entity_data.get("BackyardName")
            msp_system_id = entity_data.get("systemId")
            entity_friendly_name = f"{entity_data.get('BackyardName')} "
            unique_id = f"{msp_system_id}_{kind}"
        else:
            backyard_name = coordinator.data[entity_data.get("parent_backyard")].get(
                "BackyardName"
            )
            msp_system_id = coordinator.data[entity_data.get("parent_backyard")].get(
                "systemId"
            )
            entity_friendly_name = f"{coordinator.data[entity_data.get('parent_backyard')]['BackyardName']} "

        backyard_name = backyard_name.replace(" ", "_")

        if entity_data.get("parent_bow") is not None:
            bow_name = coordinator.data[entity_data.get("parent_bow")]["Name"].replace(
                " ", "_"
            )
            entity_friendly_name = f"{entity_friendly_name}{coordinator.data[entity_data.get('parent_bow')].get('Name')} "
            unique_id = f"{msp_system_id}_{coordinator.data[entity_data.get('parent_bow')]['systemId']}_{kind}"
        elif entity_data.get("parent_backyard") is not None:
            unique_id = f"{msp_system_id}_{entity_data.get('Name')}_{kind}"

        if entity_data.get("Name") is not None:
            entity_friendly_name = f"{entity_friendly_name}{entity_data.get('Name')} "

        entity_friendly_name = f"{entity_friendly_name}{name}"

        self._kind = kind
        self._name = entity_friendly_name
        self._unique_id = unique_id
        self._entity_data = entity_data
        self._entity = entity
        self._icon = icon
        self._attrs = {}
        self._backyard_name = backyard_name
        self._bow_name = bow_name
        self._msp_system_id = msp_system_id

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
            ATTR_NAME: self._backyard_name,
            ATTR_MANUFACTURER: "Hayward",
            ATTR_MODEL: "OmniLogic",
        }
