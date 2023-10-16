# only temporary, this needs to be created partially dynamically by openAI (the field entity_id)
HASS_OPENAI_ACTIONS = {
    "plug_on": {
        "hass_action": {
            "domain": "switch",
            "service": "turn_on",
            "service_data": {"entity_id": "switch.lumi_lumi_plug_maeu01_switch"},
            "blocking": False,
            "return_response": False,
        },
        "openai_function": {
            "name": "plug_on",
            "description": "plug_on",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    "plug_off": {
        "hass_action": {
            "domain": "switch",
            "service": "turn_off",
            "service_data": {"entity_id": "switch.lumi_lumi_plug_maeu01_switch"},
            "blocking": False,
            "return_response": False,
        },
        "openai_function": {
            "name": "plug_off",
            "description": "plug_off",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
}
