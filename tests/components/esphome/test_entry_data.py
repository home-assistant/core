"""Test ESPHome entry data."""

from aioesphomeapi import (
    APIClient,
    EntityCategory as ESPHomeEntityCategory,
    SensorInfo,
    SensorState,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_migrate_entity_unique_id(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a generic sensor entity unique id migration."""
    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create(
        "sensor",
        "esphome",
        "my_sensor",
        suggested_object_id="old_sensor",
        disabled_by=None,
    )
    entity_info = [
        SensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            unique_id="my_sensor",
            entity_category=ESPHomeEntityCategory.DIAGNOSTIC,
            icon="mdi:leaf",
        )
    ]
    states = [SensorState(key=1, state=50)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.old_sensor")
    assert state is not None
    assert state.state == "50"
    entity_reg = er.async_get(hass)
    entry = entity_reg.async_get("sensor.old_sensor")
    assert entry is not None
    assert entity_reg.async_get_entity_id("sensor", "esphome", "my_sensor") is None
    # Note that ESPHome includes the EntityInfo type in the unique id
    # as this is not a 1:1 mapping to the entity platform (ie. text_sensor)
    assert entry.unique_id == "11:22:33:44:55:aa-sensor-mysensor"


async def test_migrate_entity_unique_id_downgrade_upgrade(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test unique id migration prefers the original entity on downgrade upgrade."""
    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create(
        "sensor",
        "esphome",
        "my_sensor",
        suggested_object_id="old_sensor",
        disabled_by=None,
    )
    ent_reg.async_get_or_create(
        "sensor",
        "esphome",
        "11:22:33:44:55:aa-sensor-mysensor",
        suggested_object_id="new_sensor",
        disabled_by=None,
    )
    entity_info = [
        SensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            unique_id="my_sensor",
            entity_category=ESPHomeEntityCategory.DIAGNOSTIC,
            icon="mdi:leaf",
        )
    ]
    states = [SensorState(key=1, state=50)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.new_sensor")
    assert state is not None
    assert state.state == "50"
    entity_reg = er.async_get(hass)
    entry = entity_reg.async_get("sensor.new_sensor")
    assert entry is not None
    # Confirm we did not touch the entity that was created
    # on downgrade so when they upgrade again they can delete the
    # entity that was only created on downgrade and they keep
    # the original one.
    assert entity_reg.async_get_entity_id("sensor", "esphome", "my_sensor") is not None
    # Note that ESPHome includes the EntityInfo type in the unique id
    # as this is not a 1:1 mapping to the entity platform (ie. text_sensor)
    assert entry.unique_id == "11:22:33:44:55:aa-sensor-mysensor"
