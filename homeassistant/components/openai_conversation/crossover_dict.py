HASS_OPENAI_ACTIONS = {
    "plug_on": {
        "hass_action": {
            "domain": "switch",
            "service": "turn_on",
            "service_data": {"entity_id": "placeholder"},
            "blocking": False,
            "return_response": False,
        },
        "openai_function": {
            "name": "plug_on",
            "description": "plug_on",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "The entity ID of the plug/switch (example 'switch.someswitch')",
                    },
                },
                "required": ["entity_id"],
            },
        },
    },
    "plug_off": {
        "hass_action": {
            "domain": "switch",
            "service": "turn_off",
            "service_data": {"entity_id": "placeholder"},
            "blocking": False,
            "return_response": False,
        },
        "openai_function": {
            "name": "plug_off",
            "description": "plug_off",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "The entity ID of the plug/switch (example 'switch.someswitch')",
                    },
                },
                "required": ["entity_id"],
            },
        },
    },
    "light_on": {
        "hass_action": {
            "domain": "light",
            "service": "turn_on",
            "service_data": {"entity_id": "placeholder"},
            "blocking": False,
            "return_response": False,
        },
        "openai_function": {
            "name": "light_on",
            "description": "Turn the light on",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "The entity ID of the light (example 'light.somelight')",
                    },
                },
                "required": ["entity_id"],
            },
        },
    },
    "light_off": {
        "hass_action": {
            "domain": "light",
            "service": "turn_off",
            "service_data": {"entity_id": "placeholder"},
            "blocking": False,
            "return_response": False,
        },
        "openai_function": {
            "name": "light_off",
            "description": "Turn the light off",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "The entity ID of the light (example 'light.somelight')",
                    },
                },
                "required": ["entity_id"],
            },
        },
    },
}
