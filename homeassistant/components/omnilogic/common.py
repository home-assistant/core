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

from .const import (
    ALL_ITEM_KINDS,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    DOMAIN,
)

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
            raise UpdateFailed(f"Error updating from OmniLogic: {error}") from error

        parsed_data = {}

        def get_item_data(item, item_kind, current_id, data):
            """Get data per kind of Omnilogic API item."""
            if isinstance(item, list):
                for single_item in item:
                    data = get_item_data(single_item, item_kind, current_id, data)

            if "systemId" in item:
                system_id = item["systemId"]
                current_id = current_id + (item_kind, system_id)
                data[current_id] = item

            for kind in ALL_ITEM_KINDS:
                if kind in item:
                    data = get_item_data(item[kind], kind, current_id, data)

            return data

        parsed_data = get_item_data(data, "Backyard", (), parsed_data)

        return parsed_data


class OmniLogicEntity(CoordinatorEntity):
    """Defines the base OmniLogic entity."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        kind: str,
        name: str,
        item_id: tuple,
        icon: str,
    ):
        """Initialize the OmniLogic Entity."""
        super().__init__(coordinator)

        bow_id = None
        entity_data = coordinator.data[item_id]

        backyard_id = item_id[:2]
        if len(item_id) == 6:
            bow_id = item_id[:4]

        msp_system_id = coordinator.data[backyard_id]["systemId"]
        entity_friendly_name = f"{coordinator.data[backyard_id]['BackyardName']} "
        unique_id = f"{msp_system_id}"

        if bow_id is not None:
            unique_id = f"{unique_id}_{coordinator.data[bow_id]['systemId']}"
            entity_friendly_name = (
                f"{entity_friendly_name}{coordinator.data[bow_id]['Name']} "
            )

        unique_id = f"{unique_id}_{coordinator.data[item_id]['systemId']}_{kind}"

        if entity_data.get("Name") is not None:
            entity_friendly_name = f"{entity_friendly_name} {entity_data['Name']}"

        entity_friendly_name = f"{entity_friendly_name} {name}"

        unique_id = unique_id.replace(" ", "_")

        self._kind = kind
        self._name = entity_friendly_name
        self._unique_id = unique_id
        self._item_id = item_id
        self._icon = icon
        self._attrs = {}
        self._msp_system_id = msp_system_id
        self._backyard_name = coordinator.data[backyard_id]["BackyardName"]

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
