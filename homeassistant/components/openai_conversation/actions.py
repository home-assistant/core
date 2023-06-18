"""OpenAI callable executable functions."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


class Actions:
    """Actions exectutable against hass."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.functions = [
            {
                "name": "exec_control_switch",
                "description": "Execute an action to control a switch by turning it on, off, or toggling",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity": {
                            "type": "string",
                            "description": "ID of the entity without the switch prefix",
                        },
                        "action": {
                            "type": "string",
                            "enum": ["turn_on", "turn_off", "toggle"],
                            "description": "Action to perform on the entity",
                        },
                    },
                    "required": ["entity", "action"],
                },
            },
            {
                "name": "exec_manage_shopping_list",
                "description": "Execute an action to add or remove items from a shopping list",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["add", "remove"],
                            "description": "Action to perform on the shopping list",
                        },
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of items to add or remove",
                        },
                    },
                    "required": ["action", "items"],
                },
            },
            # {
            #     "name": "exec_adjust_temperature",
            #     "description": "Set the temperature of a thermostat or air conditioning device",
            #     "parameters": {
            #         "type": "object",
            #         "properties": {
            #             "entity": {
            #                 "type": "string",
            #                 "description": "ID of the entity without the climate prefix",
            #             },
            #             "temperature": {
            #                 "type": "number",
            #                 "description": "Desired temperature in degrees",
            #             },
            #             "unit": {
            #                 "type": "string",
            #                 "enum": ["celsius", "fahrenheit"],
            #                 "description": "Unit of the temperature",
            #             },
            #         },
            #         "required": ["device", "temperature", "unit"],
            #     },
            # },
        ]

    async def exec_control_switch(self, entity, action):
        """Control a switch by turning it on, off, or toggling."""
        state = self.hass.states.get("switch." + entity)
        if state is None:
            return "This entity does not exist, find the correct one via the query_all_entities function"

        await self.hass.services.async_call(
            "switch", action, {"entity_id": "switch." + entity}, False
        )
        return "Switch control executed"

    async def exec_manage_shopping_list(self, action, items):
        """Add or remove items from a shopping list."""
        for item in items:
            await self.hass.services.async_call(
                "shopping_list", action, {"name": item}, False
            )
        return "Shopping list updated"

    # async def exec_adjust_temperature(self, action):
    #     """Turn the hallway light on or off"""
    #     await self.hass.services.async_call(
    #         "switch", action, {"entity_id": "switch.stairway_light"}, False
    #     )
