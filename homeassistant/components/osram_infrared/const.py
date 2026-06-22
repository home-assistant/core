"""Constants for the OSRAM infrared integration."""

DOMAIN = "osram_infrared"

CONF_IR_EMITTER_ENTITY_ID = "infrared_emitter_entity_id"
CONF_IR_RECEIVER_ENTITY_ID = "infrared_receiver_entity_id"


def get_unique_id(emitter_entity_id: str) -> str:
    """Return the config-entry unique ID for an infrared emitter."""
    return f"osram_ir_light_{emitter_entity_id}"
