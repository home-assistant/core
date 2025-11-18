"""Common methods used across tests."""

from homeassistant.components import inels
from homeassistant.components.inels.const import DOMAIN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

__all__ = [
    "MockConfigEntry",
    "get_entity_id",
    "get_entity_state",
    "inels",
    "set_mock_mqtt",
]

MAC_ADDRESS = "001122334455"
UNIQUE_ID = "C0FFEE"
CONNECTED_INELS_VALUE = b"on\n"
DISCONNECTED_INELS_VALUE = b"off\n"


def get_entity_id(
    hass: HomeAssistant, entity_config: dict, index: int | None = None
) -> str | None:
    """Get the entity ID from the entity registry."""
    entity_registry = er.async_get(hass)

    base_id = f"{MAC_ADDRESS}_{entity_config['unique_id'].lower()}_{entity_config['device_type']}"
    unique_id = f"{base_id}{index}" if index is not None else base_id

    return entity_registry.async_get_entity_id(
        entity_config["entity_type"], DOMAIN, unique_id
    )


def get_entity_state(
    hass: HomeAssistant, entity_config: dict, index: int
) -> State | None:
    """Return the state of the entity from the state machine."""
    entity_id = get_entity_id(hass, entity_config, index) or ""
    return hass.states.get(entity_id)


def set_mock_mqtt(
    mqtt,
    config: dict,
    status_value: bytes,
    device_available: bool = True,
    gw_available: bool = True,
    last_value=None,
):
    """Set mock mqtt communication."""
    gw_connected_value = '{"status":true}' if gw_available else '{"status":false}'
    device_connected_value = (
        CONNECTED_INELS_VALUE if device_available else DISCONNECTED_INELS_VALUE
    )

    mqtt.mock_messages = {
        config["gw_connected_topic"]: gw_connected_value,
        config["connected_topic"]: device_connected_value,
        config["status_topic"]: status_value,
    }
    mqtt.mock_discovery_all = {config["base_topic"]: status_value}

    if last_value is not None:
        mqtt.mock_last_value = {config["status_topic"]: last_value}
    else:
        mqtt.mock_last_value = {}
