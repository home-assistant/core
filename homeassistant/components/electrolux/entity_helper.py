"""Contains entity helper methods."""

from collections.abc import Callable

from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import ElectroluxApiClient
from .const import NEW_APPLIANCE
from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity


async def async_setup_entities_helper(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    build_entities_fn: Callable[
        [ApplianceData, dict[str, ElectroluxDataUpdateCoordinator]],
        list[ElectroluxBaseEntity],
    ],
):
    """Provide async_setup_entry helper."""

    data = entry.runtime_data
    client: ElectroluxApiClient = data.client
    appliances: list[ApplianceData] = data.appliances

    if appliances is None:
        appliances = await client.fetch_appliance_data()
        data.appliances = appliances

    entities: list[ElectroluxBaseEntity] = []
    coordinators = data.coordinators

    for appliance_data in appliances:
        entities.extend(build_entities_fn(appliance_data, coordinators))

    async_add_entities(entities)

    # Listen for new/removed appliances
    async def _new_appliance(appliance_data: ApplianceData):
        new_entities = build_entities_fn(appliance_data, coordinators)
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{NEW_APPLIANCE}_{entry.entry_id}", _new_appliance
        )
    )
