"""Contains entity helper methods."""

from collections.abc import Callable
from typing import cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import ElectroluxData
from .api import ElectroluxApiClient
from .const import NEW_APPLIANCE


async def async_setup_entities_helper(
    hass: HomeAssistant,
    entry,
    async_add_entities: Callable,
    build_entities_fn: Callable[[object, dict], list],
):
    """Provide async_setup_entry helper."""

    data = cast(ElectroluxData, entry.runtime_data)
    client: ElectroluxApiClient = data.client
    appliances = await client.fetch_appliance_data()
    entities = []
    coordinators = data.coordinators

    for appliance_data in appliances:
        entities.extend(build_entities_fn(appliance_data, coordinators))

    async_add_entities(entities)

    # Listen for new/removed appliances
    async def _new_appliance(entry_id, appliance_data):
        if entry.entry_id != entry_id:
            return
        new_entities = build_entities_fn(appliance_data, coordinators)
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(async_dispatcher_connect(hass, NEW_APPLIANCE, _new_appliance))
