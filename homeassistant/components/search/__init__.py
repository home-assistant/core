"""The Search integration."""
from collections import defaultdict

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import device_registry, entity_registry

DOMAIN = "search"


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Search component."""
    websocket_api.async_register_command(hass, websocket_search)
    return True


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "search",
        vol.Required("item_type"): vol.In(
            ("area", "device", "entity", "script", "scene", "automation")
        ),
        vol.Required("item_id"): str,
    }
)
async def websocket_search(hass, connection, msg):
    """Handle search."""
    searcher = Searcher(
        hass,
        await device_registry.async_get_registry(hass),
        await entity_registry.async_get_registry(hass),
    )
    connection.send_result(
        msg["id"], await searcher.search(msg["item_type"], msg["item_id"])
    )


class Searcher:
    """Find related things."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_reg: device_registry.DeviceRegistry,
        entity_reg: entity_registry.EntityRegistry,
    ):
        """Search results."""
        self.hass = hass
        self._device_reg = device_reg
        self._entity_reg = entity_reg
        self.results = defaultdict(set)
        self._to_resolve = set()

    async def search(self, item_type, item_id):
        """Find results."""
        self._add_or_resolve(item_type, item_id)

        while self._to_resolve:
            search_type, search_id = self._to_resolve.pop()
            await getattr(self, f"_resolve_{search_type}")(search_id)

        # Remove entry into graph from search results.
        self.results[item_type].remove(item_id)
        # Clean up entity results with types that are represented as entities
        self.results["entity"] -= self.results["script"]
        self.results["entity"] -= self.results["scene"]
        self.results["entity"] -= self.results["automation"]

        # Filter out empty sets.
        return {key: val for key, val in self.results.items() if val}

    def _add_or_resolve(self, item_type, item_id):
        """Add an item to explore."""
        if item_id in self.results[item_type]:
            return

        self.results[item_type].add(item_id)
        self._to_resolve.add((item_type, item_id))

    async def _resolve_area(self, area_id) -> None:
        """Resolve an area."""
        for device in device_registry.async_entries_for_area(self._device_reg, area_id):
            self._add_or_resolve("device", device.id)

    async def _resolve_device(self, device_id) -> None:
        """Resolve a device."""
        device_entry = self._device_reg.async_get(device_id)
        # Unlikely entry doesn't exist, but let's guard for bad data.
        if device_entry is not None:
            if device_entry.area_id:
                self._add_or_resolve("area", device_entry.area_id)

            # We do not resolve device_entry.via_device_id because that
            # device is not related data-wise inside HA.

        for entity_entry in entity_registry.async_entries_for_device(
            self._entity_reg, device_id
        ):
            self._add_or_resolve("entity", entity_entry.entity_id)

        # Extra: Find automations that reference this device

    async def _resolve_entity(self, entity_id) -> None:
        """Resolve an entity."""
        # Extra: Find automations, scripts, scenes that reference this entity.

        # Find devices
        entity_entry = self._entity_reg.async_get(entity_id)
        if entity_entry is not None:
            if entity_entry.device_id:
                self._add_or_resolve("device", entity_entry.device_id)

        domain = split_entity_id(entity_id)[0]

        # We can expand these types into more types.
        if domain in ("scene", "script", "automation"):
            self._add_or_resolve(domain, entity_id)

    async def _resolve_automation(self, automation_id) -> None:
        """Resolve an automation."""
        # Extra: Check with automation integration what entities/devices they reference

    async def _resolve_script(self, script_id) -> None:
        """Resolve a script."""
        # Extra: Check with script integration what entities/devices they reference

    async def _resolve_scene(self, scene_id) -> None:
        """Resolve a scene."""
        # Extra: Check with scene integration what entities they reference
