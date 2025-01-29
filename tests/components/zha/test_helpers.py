"""Tests for ZHA helpers."""

import logging
from typing import Any

import pytest
import voluptuous_serialize
from zigpy.application import ControllerApplication
from zigpy.types.basic import uint16_t
from zigpy.zcl.clusters import lighting

import homeassistant.components.zha.const as zha_const
from homeassistant.components.zha.helpers import (
    cluster_command_schema_to_vol_schema,
    convert_to_zcl_values,
    create_zha_config,
    exclude_none_values,
    get_zha_data,
    migrate_entities_unique_ids,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_registry

_LOGGER = logging.getLogger(__name__)


async def test_zcl_schema_conversions(hass: HomeAssistant) -> None:
    """Test ZHA ZCL schema conversion helpers."""
    command_schema = lighting.Color.ServerCommandDefs.color_loop_set.schema
    expected_schema = [
        {
            "type": "multi_select",
            "options": ["Action", "Direction", "Time", "Start Hue"],
            "name": "update_flags",
            "required": True,
        },
        {
            "type": "select",
            "options": [
                ("Deactivate", "Deactivate"),
                ("Activate from color loop hue", "Activate from color loop hue"),
                ("Activate from current hue", "Activate from current hue"),
            ],
            "name": "action",
            "required": True,
        },
        {
            "type": "select",
            "options": [("Decrement", "Decrement"), ("Increment", "Increment")],
            "name": "direction",
            "required": True,
        },
        {
            "type": "integer",
            "valueMin": 0,
            "valueMax": 65535,
            "name": "time",
            "required": True,
        },
        {
            "type": "integer",
            "valueMin": 0,
            "valueMax": 65535,
            "name": "start_hue",
            "required": True,
        },
        {
            "type": "multi_select",
            "options": ["Execute if off present"],
            "name": "options_mask",
            "optional": True,
        },
        {
            "type": "multi_select",
            "options": ["Execute if off"],
            "name": "options_override",
            "optional": True,
        },
    ]
    vol_schema = voluptuous_serialize.convert(
        cluster_command_schema_to_vol_schema(command_schema),
        custom_serializer=cv.custom_serializer,
    )
    assert vol_schema == expected_schema

    raw_data = {
        "update_flags": ["Action", "Start Hue"],
        "action": "Activate from current hue",
        "direction": "Increment",
        "time": 20,
        "start_hue": 196,
    }

    converted_data = convert_to_zcl_values(raw_data, command_schema)

    assert isinstance(
        converted_data["update_flags"], lighting.Color.ColorLoopUpdateFlags
    )
    assert lighting.Color.ColorLoopUpdateFlags.Action in converted_data["update_flags"]
    assert (
        lighting.Color.ColorLoopUpdateFlags.Start_Hue in converted_data["update_flags"]
    )

    assert isinstance(converted_data["action"], lighting.Color.ColorLoopAction)
    assert (
        converted_data["action"]
        == lighting.Color.ColorLoopAction.Activate_from_current_hue
    )

    assert isinstance(converted_data["direction"], lighting.Color.ColorLoopDirection)
    assert converted_data["direction"] == lighting.Color.ColorLoopDirection.Increment

    assert isinstance(converted_data["time"], uint16_t)
    assert converted_data["time"] == 20

    assert isinstance(converted_data["start_hue"], uint16_t)
    assert converted_data["start_hue"] == 196

    raw_data = {
        "update_flags": [0b0000_0001, 0b0000_1000],
        "action": 0x02,
        "direction": 0x01,
        "time": 20,
        "start_hue": 196,
    }

    converted_data = convert_to_zcl_values(raw_data, command_schema)

    assert isinstance(
        converted_data["update_flags"], lighting.Color.ColorLoopUpdateFlags
    )
    assert lighting.Color.ColorLoopUpdateFlags.Action in converted_data["update_flags"]
    assert (
        lighting.Color.ColorLoopUpdateFlags.Start_Hue in converted_data["update_flags"]
    )

    assert isinstance(converted_data["action"], lighting.Color.ColorLoopAction)
    assert (
        converted_data["action"]
        == lighting.Color.ColorLoopAction.Activate_from_current_hue
    )

    assert isinstance(converted_data["direction"], lighting.Color.ColorLoopDirection)
    assert converted_data["direction"] == lighting.Color.ColorLoopDirection.Increment

    assert isinstance(converted_data["time"], uint16_t)
    assert converted_data["time"] == 20

    assert isinstance(converted_data["start_hue"], uint16_t)
    assert converted_data["start_hue"] == 196

    # This time, the update flags bitmap is empty
    raw_data = {
        "update_flags": [],
        "action": 0x02,
        "direction": 0x01,
        "time": 20,
        "start_hue": 196,
    }

    converted_data = convert_to_zcl_values(raw_data, command_schema)

    # No flags are passed through
    assert converted_data["update_flags"] == 0


@pytest.mark.parametrize(
    ("obj", "expected_output"),
    [
        ({"a": 1, "b": 2, "c": None}, {"a": 1, "b": 2}),
        ({"a": 1, "b": 2, "c": 0}, {"a": 1, "b": 2, "c": 0}),
        ({"a": 1, "b": 2, "c": ""}, {"a": 1, "b": 2, "c": ""}),
        ({"a": 1, "b": 2, "c": False}, {"a": 1, "b": 2, "c": False}),
    ],
)
def test_exclude_none_values(
    obj: dict[str, Any], expected_output: dict[str, Any]
) -> None:
    """Test exclude_none_values helper."""
    result = exclude_none_values(obj)
    assert result == expected_output

    for key, value in expected_output.items():
        assert value == obj[key]


async def test_create_zha_config_remove_unused(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_zigpy_connect: ControllerApplication,
) -> None:
    """Test creating ZHA config data with unused keys."""
    config_entry.add_to_hass(hass)

    options = config_entry.options.copy()
    options["custom_configuration"]["zha_options"]["some_random_key"] = "a value"

    hass.config_entries.async_update_entry(config_entry, options=options)

    assert (
        config_entry.options["custom_configuration"]["zha_options"]["some_random_key"]
        == "a value"
    )

    status = await async_setup_component(
        hass,
        zha_const.DOMAIN,
        {zha_const.DOMAIN: {zha_const.CONF_ENABLE_QUIRKS: False}},
    )
    assert status is True
    await hass.async_block_till_done()

    ha_zha_data = get_zha_data(hass)

    # Does not error out
    create_zha_config(hass, ha_zha_data)


class MockInfoObject:
    """Mock entity info object."""

    def __init__(self, unique_id: str, previous_unique_id: str | None = None) -> None:
        """Initialize a mocked entity info object."""
        self.unique_id: str = unique_id
        self.previous_unique_id: str | None = previous_unique_id


class MockEntity:
    """Mock entity."""

    def __init__(self, info_object: MockInfoObject) -> None:
        """Initialize a mocked entity."""
        self.info_object: MockInfoObject = info_object


class MockEntityData:
    """Mock entity data."""

    def __init__(self, entity: MockEntity) -> None:
        """Initialize a mocked entity data."""
        self.entity: MockEntity = entity


async def test_migrate_entities_unique_ids(hass: HomeAssistant) -> None:
    """Test migration of ZHA entities to new unique ids."""

    test_platform = "test_platform"
    test_entity_id = f"{test_platform}.test_entity_id"
    test_entity_unique_id = "zha.test_entity-unique-id"
    test_entity_id2 = f"{test_platform}.test_entity_id"
    test_entity_unique_id2 = "zha.test_entity-unique-id"

    entity_registry = mock_registry(
        hass,
        {
            test_entity_id: RegistryEntry(
                entity_id=test_entity_id,
                unique_id=test_entity_unique_id,
                platform=zha_const.DOMAIN,
                device_id="mock-zha.test_entity-dev-id",
            ),
            test_entity_id2: RegistryEntry(
                entity_id=test_entity_id2,
                unique_id=test_entity_unique_id2,
                platform=zha_const.DOMAIN,
                device_id="mock-zha.test_entity-dev-id",
            ),
        },
    )

    test_entity_new_unique_id = "zha.test_entity-new-unique-id"
    mock_entity_data = MockEntityData(
        entity=MockEntity(
            info_object=MockInfoObject(
                unique_id=test_entity_new_unique_id,
                previous_unique_id=test_entity_unique_id,
            )
        )
    )

    mock_entity_data2 = MockEntityData(
        entity=MockEntity(
            info_object=MockInfoObject(
                unique_id=test_entity_unique_id2,
                previous_unique_id=None,
            )
        )
    )

    await migrate_entities_unique_ids(
        hass, test_platform, [mock_entity_data, mock_entity_data2]
    )

    # First entity has a new unique id
    registry_entry = entity_registry.async_get(test_entity_id)
    assert registry_entry.entity_id is test_entity_id
    assert registry_entry.unique_id is test_entity_new_unique_id

    # Second entity is left unchanged
    registry_entry2 = entity_registry.async_get(test_entity_id2)
    assert registry_entry2.entity_id is test_entity_id2
    assert registry_entry2.unique_id is test_entity_unique_id2
