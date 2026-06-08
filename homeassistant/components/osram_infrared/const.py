"""Constants for the OSRAM infrared integration."""

DOMAIN = "osram_infrared"

CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_INFRARED_RECEIVER_ENTITY_ID = "infrared_receiver_entity_id"


def get_unique_id(infrared_entity_id: str) -> str:
    """Return the config-entry unique ID for an infrared emitter."""
    return f"osram_ir_light_{infrared_entity_id}"
