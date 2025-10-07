"""Common methods used across tests."""

# pyright: reportMissingImports=false
try:
    from homeassistant.components import inels
    from homeassistant.components.inels.const import DOMAIN

    from tests.common import MockConfigEntry
except ImportError:
    from custom_components import inels
    from custom_components.inels.const import DOMAIN
    from pytest_homeassistant_custom_component.common import MockConfigEntry


from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import Entity

__all__ = [
    "MockConfigEntry",
    "get_entity",
    "get_entity_id",
    "inels",
    "old_entity_and_device_removal",
    "set_mock_mqtt",
]

MAC_ADDRESS = "001122334455"
UNIQUE_ID = "C0FFEE"
CONNECTED_INELS_VALUE = b"on\n"
DISCONNECTED_INELS_VALUE = b"off\n"


def get_entity_id(entity_config: dict, index: int) -> str:
    """Construct the entity_id based on the entity_config."""
    unique_id = entity_config["unique_id"].lower()
    base_id = f"{entity_config['entity_type']}.{MAC_ADDRESS}_{unique_id}_{entity_config['device_type']}"
    return f"{base_id}{f'_{index:03}'}" if index is not None else base_id


def get_entity(hass: HomeAssistant, entity_config: dict, index: int) -> Entity:
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
        data={},
        domain=DOMAIN,
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

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # The device was discovered, and at this point, the async_remove_old_entities function was called
    assert config_entry.runtime_data.devices
    assert old_entity.entity_id not in config_entry.runtime_data.old_entities[platform]

    # Get the new entity
    new_entity = entity_registry.async_get(get_entity_id(entity_config, index).lower())

    assert new_entity is not None

    # Verify that the new entity is in the registry
    assert entity_registry.async_get(new_entity.entity_id) is not None

    # Verify that the old entity is no longer in the registry
    assert entity_registry.async_get(old_entity.entity_id) is None

    # Verify that the device no longer exists in the registry
    assert device_registry.async_get_device({(DOMAIN, old_entity.unique_id)}) is None
