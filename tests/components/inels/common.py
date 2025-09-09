"""Common methods used across tests."""

# pyright: reportMissingImports=false
try:
    from homeassistant.components import inels
    from homeassistant.components.inels import config_flow
    from homeassistant.components.inels.const import DOMAIN, OLD_ENTITIES

    from tests.common import MockConfigEntry
except ImportError:
    from custom_components import inels
    from custom_components.inels import config_flow
    from custom_components.inels.const import DOMAIN, OLD_ENTITIES
    from pytest_homeassistant_custom_component.common import MockConfigEntry


from inelsmqtt.const import MQTT_TRANSPORT

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import Entity

__all__ = [
    "MockConfigEntry",
    "inels",
    "config_flow",
    "get_entity",
    "get_entity_id",
    "set_mock_mqtt",
    "old_entity_and_device_removal",
]

MAC_ADDRESS = "001122334455"
UNIQUE_ID = "C0FFEE"
CONNECTED_INELS_VALUE = b"on\n"
DISCONNECTED_INELS_VALUE = b"off\n"


def get_entity_id(entity_config: dict, index: str = "") -> str:
    """Construct the entity_id based on the entity_config."""
    base_id = f"{entity_config['entity_type']}.{MAC_ADDRESS}_{entity_config['unique_id']}_{entity_config['device_type']}"
    return f"{base_id}{index}" if index else base_id


def get_entity(hass: HomeAssistant, entity_config: dict, index: str = "") -> Entity:
    """Return instance of the entity."""
    entity_id = get_entity_id(entity_config, index)
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
    gw_connected_value = b'{"status":true}' if gw_available else b'{"status":false}'
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


async def old_entity_and_device_removal(
    hass: HomeAssistant, mock_mqtt, platform, entity_config, value_key, index
):
    """Test that old entities are correctly identified and removed across different platforms."""

    set_mock_mqtt(
        mock_mqtt,
        config=entity_config,
        status_value=entity_config[value_key],
        gw_available=True,
        device_available=True,
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 1883,
            CONF_USERNAME: "test",
            CONF_PASSWORD: "pwd",
            MQTT_TRANSPORT: "tcp",
        },
        title="iNELS",
    )
    config_entry.add_to_hass(hass)

    # Create an old entity
    entity_registry = er.async_get(hass)
    old_entity = entity_registry.async_get_or_create(
        domain=platform,
        platform=DOMAIN,
        unique_id=f"old_{entity_config['unique_id']}",
        suggested_object_id=f"old_inels_{platform}_{entity_config['device_type']}",
        config_entry=config_entry,
    )

    # Create a device and associate it with the old entity
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, f"old_{entity_config['unique_id']}")},
        name=f"iNELS {platform.capitalize()} {entity_config['device_type']}",
        manufacturer="iNELS",
        model=entity_config["device_type"],
    )

    # Associate the old entity with the device
    entity_registry.async_update_entity(old_entity.entity_id, device_id=device.id)

    assert (
        device_registry.async_get_device({(DOMAIN, old_entity.unique_id)}) is not None
    )

    # Add the old entity to the OLD_ENTITIES
    hass.data[DOMAIN] = {
        config_entry.entry_id: {OLD_ENTITIES: {platform: [old_entity.entity_id]}}
    }

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the new entity
    new_entity = entity_registry.async_get(get_entity_id(entity_config, index).lower())

    assert new_entity is not None

    # Check that the OLD_ENTITIES list has been updated correctly
    assert (
        old_entity.entity_id
        in hass.data[DOMAIN][config_entry.entry_id][OLD_ENTITIES][platform]
    )
    assert (
        new_entity.entity_id
        not in hass.data[DOMAIN][config_entry.entry_id][OLD_ENTITIES][platform]
    )

    # Verify that the new entity is in the registry
    assert entity_registry.async_get(new_entity.entity_id) is not None

    # Verify that the old entity is no longer in the registry
    assert entity_registry.async_get(old_entity.entity_id) is None

    # Verify that the device no longer exists in the registry
    assert device_registry.async_get_device({(DOMAIN, old_entity.unique_id)}) is None

    # Assert that old_entity.entity_id is in the OLD_ENTITIES list
    assert (
        old_entity.entity_id
        in hass.data[DOMAIN][config_entry.entry_id][OLD_ENTITIES][platform]
    )
