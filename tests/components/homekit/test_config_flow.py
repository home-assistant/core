"""Test the HomeKit config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.homekit.accessories import HomeDriver
from homeassistant.components.homekit.config_flow import SUPPORTED_DOMAINS
from homeassistant.components.homekit.const import (
    CONF_EXCLUDE_TARGETS,
    CONF_FILTER,
    CONF_INCLUDE_TARGETS,
    DOMAIN,
    SHORT_BRIDGE_NAME,
)
from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_IMPORT, ConfigFlowResult
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_PORT,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, label_registry as lr
from homeassistant.helpers.entityfilter import CONF_INCLUDE_DOMAINS
from homeassistant.setup import async_setup_component

from .util import PATH_HOMEKIT, async_init_entry

from tests.common import MockConfigEntry


def _mock_config_entry_with_options_populated():
    """Create a mock config entry with options populated."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        options={
            "filter": {
                "include_domains": [
                    "fan",
                    "humidifier",
                    "vacuum",
                    "media_player",
                    "climate",
                    "alarm_control_panel",
                ],
                "exclude_entities": ["climate.front_gate"],
            },
        },
    )


async def test_setup_in_bridge_mode(hass: HomeAssistant) -> None:
    """Test we can setup a new instance in bridge mode."""
    hass.states.async_set("camera.target_only", "on")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["last_step"] is False

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"include_domains": ["light"]},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "include"
    assert result2["last_step"] is False

    include_targets = {
        ATTR_ENTITY_ID: ["camera.target_only"],
        ATTR_LABEL_ID: ["homekit"],
    }
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_INCLUDE_TARGETS: include_targets},
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "review"
    assert result3["last_step"] is False
    assert result3["description_placeholders"] == {"count": "0"}

    result3 = await hass.config_entries.flow.async_configure(result3["flow_id"], {})
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "pairing"
    assert result3["last_step"] is True

    with (
        patch(
            "homeassistant.components.homekit.config_flow.async_find_next_available_port",
            return_value=12345,
        ),
        patch(
            "homeassistant.components.homekit.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.homekit.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    bridge_name = (result4["title"].split(":"))[0]
    assert bridge_name == SHORT_BRIDGE_NAME
    assert result4["data"] == {
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["light"],
            "include_entities": [],
            CONF_INCLUDE_TARGETS: include_targets,
        },
        "exclude_accessory_mode": True,
        "mode": "bridge",
        "name": bridge_name,
        "port": 12345,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_setup_in_bridge_mode_entity_review(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test the review lists entities expanded from combined targets."""
    include_label = label_registry.async_create("HomeKit")
    exclude_label = label_registry.async_create("Private")

    for entity_id, labels in (
        ("light.included_by_domain", set()),
        ("switch.included_by_label", {include_label.label_id}),
        ("light.excluded_by_label", {exclude_label.label_id}),
        (
            "switch.excluded_at_equal_specificity",
            {include_label.label_id, exclude_label.label_id},
        ),
        ("sensor.unsupported_by_homekit", {include_label.label_id}),
    ):
        domain, object_id = entity_id.split(".", 1)
        entry = entity_registry.async_get_or_create(
            domain, "demo", object_id, suggested_object_id=object_id
        )
        entity_registry.async_update_entity(entry.entity_id, labels=labels)
        hass.states.async_set(entry.entity_id, "on")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_INCLUDE_DOMAINS: ["light"]}
    )

    assert result["step_id"] == "include"
    assert {key.schema for key in result["data_schema"].schema} == {
        CONF_INCLUDE_TARGETS,
        CONF_EXCLUDE_TARGETS,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_INCLUDE_TARGETS: {ATTR_LABEL_ID: [include_label.label_id]},
            CONF_EXCLUDE_TARGETS: {ATTR_LABEL_ID: [exclude_label.label_id]},
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "review"
    assert result["description_placeholders"] == {"count": "2"}
    selected_entities = {
        "light.included_by_domain",
        "switch.included_by_label",
    }
    schema = result["data_schema"].schema
    assert set(_get_schema_default(schema, CONF_ENTITIES)) == selected_entities
    entity_selector = next(
        value for key, value in schema.items() if key.schema == CONF_ENTITIES
    )
    assert entity_selector.config["read_only"] is True
    assert entity_selector.config["multiple"] is True
    assert set(entity_selector.config["include_entities"]) == selected_entities


async def test_setup_in_bridge_mode_name_taken(hass: HomeAssistant) -> None:
    """Test we can setup a new instance in bridge mode when the name is taken."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: SHORT_BRIDGE_NAME, CONF_PORT: 8000},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"include_domains": ["light"]},
    )
    result2 = await _async_complete_config_entity_selection(hass, result2)
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "pairing"

    with (
        patch(
            "homeassistant.components.homekit.config_flow.async_find_next_available_port",
            return_value=12345,
        ),
        patch(
            "homeassistant.components.homekit.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.homekit.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] != SHORT_BRIDGE_NAME
    assert result3["title"].startswith(SHORT_BRIDGE_NAME)
    bridge_name = (result3["title"].split(":"))[0]
    assert result3["data"] == {
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["light"],
            "include_entities": [],
        },
        "exclude_accessory_mode": True,
        "mode": "bridge",
        "name": bridge_name,
        "port": 12345,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 2


async def test_setup_creates_entries_for_accessory_mode_devices(
    hass: HomeAssistant,
) -> None:
    """Test setup creates entries for accessory mode devices."""
    hass.states.async_set("camera.one", "on")
    hass.states.async_set("camera.existing", "on")
    hass.states.async_set("lock.new", "on")
    hass.states.async_set("media_player.two", "on", {"device_class": "tv"})
    hass.states.async_set("remote.standard", "on")
    hass.states.async_set("remote.activity", "on", {"supported_features": 4})

    bridge_mode_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "bridge", CONF_PORT: 8001},
        options={
            "mode": "bridge",
            "filter": {
                "include_entities": ["camera.existing"],
            },
        },
    )
    bridge_mode_entry.add_to_hass(hass)
    accessory_mode_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "accessory", CONF_PORT: 8000},
        options={
            "mode": "accessory",
            "filter": {
                "include_entities": ["camera.existing"],
            },
        },
    )
    accessory_mode_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"include_domains": ["camera", "media_player", "light", "lock", "remote"]},
    )
    result2 = await _async_complete_config_entity_selection(hass, result2)
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "pairing"

    with (
        patch(
            "homeassistant.components.homekit.config_flow.async_find_next_available_port",
            return_value=12345,
        ),
        patch(
            "homeassistant.components.homekit.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.homekit.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"][:11] == "HASS Bridge"
    bridge_name = (result3["title"].split(":"))[0]
    assert result3["data"] == {
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["media_player", "light", "lock", "remote"],
            "include_entities": [],
        },
        "exclude_accessory_mode": True,
        "mode": "bridge",
        "name": bridge_name,
        "port": 12345,
    }
    assert len(mock_setup.mock_calls) == 1
    #
    # Existing accessory mode entries should get setup but not duplicated
    #
    # 1 - existing accessory for camera.existing
    # 2 - existing bridge for camera.one
    # 3 - new bridge
    # 4 - camera.one in accessory mode
    # 5 - media_player.two in accessory mode
    # 6 - remote.activity in accessory mode
    # 7 - lock.new in accessory mode
    assert len(mock_setup_entry.mock_calls) == 7


async def test_import(hass: HomeAssistant) -> None:
    """Test we can import instance."""

    ignored_entry = MockConfigEntry(domain=DOMAIN, data={}, source=SOURCE_IGNORE)
    ignored_entry.add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "port_name_in_use"

    with (
        patch(
            "homeassistant.components.homekit.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.homekit.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_NAME: "othername", CONF_PORT: 56789},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "othername:56789"
    assert result2["data"] == {
        "name": "othername",
        "port": 56789,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 2


async def test_options_flow_exclude_targets(hass: HomeAssistant) -> None:
    """Test excluding targets in the options flow."""

    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("climate.old", "off")
    hass.states.async_set("climate.front_gate", "off")
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["fan", "vacuum", "climate", "humidifier"],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "include"
    assert result["data_schema"]({})[CONF_EXCLUDE_TARGETS] == {
        ATTR_ENTITY_ID: ["climate.front_gate"]
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_INCLUDE_TARGETS: {},
            CONF_EXCLUDE_TARGETS: {ATTR_ENTITY_ID: ["climate.old"]},
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "review"

    # Inject garbage to ensure the options data
    # is being deep copied and we cannot mutate it in flight
    config_entry.options[CONF_FILTER][CONF_INCLUDE_DOMAINS].append("garbage")

    result2 = await _async_submit_options_review_step(hass, result)
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "climate"
    result2 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "bridged_device_triggers"

    with patch("homeassistant.components.homekit.async_setup_entry", return_value=True):
        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={},
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "devices": [],
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            CONF_EXCLUDE_TARGETS: {ATTR_ENTITY_ID: ["climate.old"]},
            "include_domains": ["climate", "fan", "humidifier", "vacuum"],
            "include_entities": [],
        },
    }


@patch(f"{PATH_HOMEKIT}.async_port_is_available", return_value=True)
@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_options_flow_devices(
    port_mock,
    hass: HomeAssistant,
    demo_cleanup,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test devices can be bridged."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        options={
            "devices": ["notexist"],
            "filter": {
                "include_domains": [
                    "fan",
                    "humidifier",
                    "vacuum",
                    "media_player",
                    "climate",
                    "alarm_control_panel",
                ],
                "exclude_entities": ["climate.front_gate"],
            },
        },
    )
    config_entry.add_to_hass(hass)

    demo_config_entry = MockConfigEntry(domain="domain")
    demo_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.homekit.HomeKit") as mock_homekit:
        mock_homekit.return_value = homekit = Mock(bridge=None, driver=None)
        type(homekit).async_start = AsyncMock()
        assert await async_setup_component(hass, DOMAIN, {"homekit": {}})
        assert await async_setup_component(hass, "homeassistant", {})
        assert await async_setup_component(hass, "demo", {"demo": {}})
        assert await async_setup_component(hass, DOMAIN, {"homekit": {}})

        hass.states.async_set("climate.old", "off")
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "domains": ["fan", "vacuum", "climate"],
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "include"

        entry = entity_registry.async_get("light.ceiling_lights")
        assert entry is not None
        device_id = entry.device_id

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_INCLUDE_TARGETS: {},
                CONF_EXCLUDE_TARGETS: {ATTR_ENTITY_ID: ["climate.old"]},
            },
        )
        result2 = await _async_submit_options_review_step(hass, result)

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "climate"
        result2 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={},
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "bridged_device_triggers"
        # The stale "notexist" device must be stripped from the form
        # default, otherwise the UI errors on an unknown device id
        assert result2["data_schema"]({})["devices"] == []

        with patch(
            "homeassistant.components.homekit.async_setup_entry", return_value=True
        ):
            result3 = await hass.config_entries.options.async_configure(
                result2["flow_id"],
                user_input={"devices": [device_id]},
            )

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert config_entry.options == {
            "devices": [device_id],
            "mode": "bridge",
            "filter": {
                "exclude_domains": [],
                "exclude_entities": [],
                CONF_EXCLUDE_TARGETS: {ATTR_ENTITY_ID: ["climate.old"]},
                "include_domains": ["climate", "fan", "vacuum"],
                "include_entities": [],
            },
        }

        # Reopen the flow and confirm the saved device is preselected
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "domains": ["fan", "vacuum", "climate"],
            },
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_INCLUDE_TARGETS: {},
                CONF_EXCLUDE_TARGETS: {ATTR_ENTITY_ID: ["climate.old"]},
            },
        )
        result2 = await _async_submit_options_review_step(hass, result)
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "climate"
        result2 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={},
        )
        assert result2["step_id"] == "bridged_device_triggers"
        assert result2["data_schema"]({})["devices"] == [device_id]

        await hass.async_block_till_done()
        await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_flow_migrates_legacy_include_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test valid legacy include entities migrate to direct targets."""
    hidden_switch = entity_registry.async_get_or_create(
        "switch",
        "demo",
        "hidden",
        hidden_by=er.RegistryEntryHider.INTEGRATION,
    )
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        options={
            "filter": {
                "include_entities": [
                    "climate.not_exist",
                    "climate.front_gate",
                    hidden_switch.entity_id,
                ],
            },
        },
    )
    config_entry.add_to_hass(hass)
    hass.states.async_set("climate.front_gate", "off")
    hass.states.async_set("climate.new", "off")
    hass.states.async_set(hidden_switch.entity_id, "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["fan", "vacuum", "climate"],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "include"

    assert result["data_schema"]({})[CONF_INCLUDE_TARGETS] == {
        ATTR_ENTITY_ID: ["climate.front_gate", hidden_switch.entity_id]
    }

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_INCLUDE_TARGETS: {
                ATTR_ENTITY_ID: [
                    "climate.new",
                    "climate.front_gate",
                    hidden_switch.entity_id,
                ]
            },
        },
    )
    assert set(_get_schema_default(result2["data_schema"].schema, CONF_ENTITIES)) == {
        "climate.front_gate",
        "climate.new",
        hidden_switch.entity_id,
    }
    result2 = await _async_submit_options_review_step(hass, result2)
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "climate"
    result2 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "bridged_device_triggers"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={},
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "devices": [],
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["climate", "fan", "vacuum"],
            "include_entities": [],
            CONF_INCLUDE_TARGETS: {
                ATTR_ENTITY_ID: [
                    "climate.new",
                    "climate.front_gate",
                    hidden_switch.entity_id,
                ]
            },
        },
    }
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_flow_exclude_targets_with_nonexistent_entity(
    hass: HomeAssistant,
) -> None:
    """Test exclude targets omit nonexistent stored entities."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        options={
            "filter": {
                "include_domains": ["climate"],
                "exclude_entities": ["climate.not_exist", "climate.front_gate"],
            },
        },
    )
    config_entry.add_to_hass(hass)
    hass.states.async_set("climate.front_gate", "off")
    hass.states.async_set("climate.new", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["climate"],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "include"
    assert result["data_schema"]({})[CONF_EXCLUDE_TARGETS] == {
        ATTR_ENTITY_ID: ["climate.front_gate"]
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_INCLUDE_TARGETS: {},
            CONF_EXCLUDE_TARGETS: {
                ATTR_ENTITY_ID: ["climate.new", "climate.front_gate"]
            },
        },
    )
    result2 = await _async_submit_options_review_step(hass, result)
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "bridged_device_triggers"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={},
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "devices": [],
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            CONF_EXCLUDE_TARGETS: {
                ATTR_ENTITY_ID: ["climate.new", "climate.front_gate"]
            },
            "include_domains": ["climate"],
            "include_entities": [],
        },
    }
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_flow_with_include_and_exclude_targets(
    hass: HomeAssistant,
) -> None:
    """Test config flow stores include and exclude targets together."""
    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("climate.old", "off")
    hass.states.async_set("climate.new", "off")

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )
    assert result["last_step"] is False
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["fan", "vacuum"],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "include"
    assert result["last_step"] is False
    assert _get_schema_default(result["data_schema"].schema, CONF_INCLUDE_TARGETS) == {}

    include_targets = {
        ATTR_AREA_ID: ["kitchen"],
        ATTR_DEVICE_ID: ["device-id"],
        ATTR_ENTITY_ID: ["climate.new"],
        ATTR_FLOOR_ID: ["ground-floor"],
        ATTR_LABEL_ID: ["homekit"],
    }
    exclude_targets = {
        ATTR_ENTITY_ID: ["climate.old"],
        ATTR_LABEL_ID: ["private"],
    }
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_INCLUDE_TARGETS: include_targets,
            CONF_EXCLUDE_TARGETS: exclude_targets,
        },
    )
    assert result2["description_placeholders"] == {"count": "1"}
    assert result2["last_step"] is False
    assert _get_schema_default(result2["data_schema"].schema, CONF_ENTITIES) == [
        "climate.new"
    ]
    result2 = await _async_submit_options_review_step(hass, result2)

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "climate"
    assert result2["last_step"] is False

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"], user_input=result2["data_schema"]({})
    )
    assert result3["step_id"] == "bridged_device_triggers"
    assert result3["last_step"] is True

    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"], user_input={}
    )

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "devices": [],
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["fan", "vacuum"],
            "include_entities": [],
            CONF_INCLUDE_TARGETS: include_targets,
            CONF_EXCLUDE_TARGETS: exclude_targets,
        },
    }
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_flow_target_selectors_allow_supported_domains(
    hass: HomeAssistant,
) -> None:
    """Test target selectors allow every supported domain."""
    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"domains": ["light"]}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "include"
    for target_key in (CONF_INCLUDE_TARGETS, CONF_EXCLUDE_TARGETS):
        target_selector = next(
            value
            for key, value in result["data_schema"].schema.items()
            if key.schema == target_key
        )
        assert target_selector.config == {
            "entity": [{"domain": SUPPORTED_DOMAINS}],
            "primary_entities_only": True,
        }


async def test_options_flow_camera_targets(hass: HomeAssistant) -> None:
    """Test including and excluding camera targets in the options flow."""

    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("climate.old", "off")
    hass.states.async_set("camera.native_h264", "off")
    hass.states.async_set("camera.transcode_h264", "off")
    hass.states.async_set("camera.excluded", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["fan", "vacuum", "climate", "camera"],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "include"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_INCLUDE_TARGETS: {
                ATTR_ENTITY_ID: ["camera.native_h264", "camera.transcode_h264"]
            },
        },
    )
    result2 = await _async_submit_options_review_step(hass, result2)
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "cameras"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"camera_copy": ["camera.native_h264"]},
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "climate"

    result3 = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        user_input={},
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "bridged_device_triggers"

    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        user_input={},
    )
    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "devices": [],
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["camera", "climate", "fan", "vacuum"],
            "include_entities": [],
            CONF_INCLUDE_TARGETS: {
                ATTR_ENTITY_ID: ["camera.native_h264", "camera.transcode_h264"]
            },
        },
        "entity_config": {"camera.native_h264": {"video_codec": "copy"}},
    }

    # Now run though again and verify we can turn off copy

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {
        "domains": ["camera", "climate", "fan", "vacuum"],
        "mode": "bridge",
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["climate", "fan", "vacuum", "camera"],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "include"
    assert result["data_schema"]({})[CONF_EXCLUDE_TARGETS] == {}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_INCLUDE_TARGETS: {},
            CONF_EXCLUDE_TARGETS: {ATTR_ENTITY_ID: ["climate.old", "camera.excluded"]},
        },
    )
    result2 = await _async_submit_options_review_step(hass, result)
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "cameras"
    assert result2["data_schema"]({}) == {
        "camera_copy": ["camera.native_h264"],
        "camera_audio": [],
    }
    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"camera_copy": []},
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "bridged_device_triggers"

    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        user_input={},
    )
    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "devices": [],
        "entity_config": {},
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            CONF_EXCLUDE_TARGETS: {ATTR_ENTITY_ID: ["climate.old", "camera.excluded"]},
            "include_domains": ["camera", "climate", "fan", "vacuum"],
            "include_entities": [],
        },
        "mode": "bridge",
    }
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_flow_with_camera_audio(hass: HomeAssistant) -> None:
    """Test config flow options with cameras that support audio."""

    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("climate.old", "off")
    hass.states.async_set("camera.audio", "off")
    hass.states.async_set("camera.no_audio", "off")
    hass.states.async_set("camera.excluded", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["fan", "vacuum", "climate", "camera"],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "include"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_INCLUDE_TARGETS: {ATTR_ENTITY_ID: ["camera.audio", "camera.no_audio"]},
        },
    )
    result2 = await _async_submit_options_review_step(hass, result2)
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "cameras"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"camera_audio": ["camera.audio"]},
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "climate"

    result3 = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        user_input={},
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "bridged_device_triggers"

    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        user_input={},
    )
    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "devices": [],
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["camera", "climate", "fan", "vacuum"],
            "include_entities": [],
            CONF_INCLUDE_TARGETS: {ATTR_ENTITY_ID: ["camera.audio", "camera.no_audio"]},
        },
        "entity_config": {"camera.audio": {"support_audio": True}},
    }

    # Now run though again and verify we can turn off audio

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {
        "domains": ["camera", "climate", "fan", "vacuum"],
        "mode": "bridge",
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["climate", "fan", "vacuum", "camera"],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "include"
    assert result["data_schema"]({})[CONF_EXCLUDE_TARGETS] == {}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_INCLUDE_TARGETS: {},
            CONF_EXCLUDE_TARGETS: {ATTR_ENTITY_ID: ["climate.old", "camera.excluded"]},
        },
    )
    result2 = await _async_submit_options_review_step(hass, result)
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "cameras"
    assert result2["data_schema"]({}) == {
        "camera_copy": [],
        "camera_audio": ["camera.audio"],
    }
    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"camera_audio": []},
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "bridged_device_triggers"

    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        user_input={},
    )
    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "devices": [],
        "entity_config": {},
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            CONF_EXCLUDE_TARGETS: {ATTR_ENTITY_ID: ["climate.old", "camera.excluded"]},
            "include_domains": ["camera", "climate", "fan", "vacuum"],
            "include_entities": [],
        },
        "mode": "bridge",
    }
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_flow_blocked_when_from_yaml(hass: HomeAssistant) -> None:
    """Test config flow options."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        options={
            "devices": [],
            "filter": {
                "include_domains": [
                    "fan",
                    "humidifier",
                    "vacuum",
                    "media_player",
                    "climate",
                    "alarm_control_panel",
                ],
                "exclude_entities": ["climate.front_gate"],
            },
        },
        source=SOURCE_IMPORT,
    )
    config_entry.add_to_hass(hass)

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "yaml"

    with patch("homeassistant.components.homekit.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={},
        )
        assert result2["type"] is FlowResultType.CREATE_ENTRY
    await hass.config_entries.async_unload(config_entry.entry_id)


@patch(f"{PATH_HOMEKIT}.async_port_is_available", return_value=True)
@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_options_flow_accessory_mode_entity_selection(
    port_mock,
    hass: HomeAssistant,
    hk_driver,
) -> None:
    """Test accessory mode entity selection."""
    config_entry = _mock_config_entry_with_options_populated()
    await async_init_entry(hass, config_entry)

    hass.states.async_set(
        "media_player.tv",
        "off",
        {"device_class": MediaPlayerDeviceClass.TV},
    )
    hass.states.async_set("media_player.sonos", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {
        "domains": [
            "fan",
            "humidifier",
            "vacuum",
            "media_player",
            "climate",
            "alarm_control_panel",
        ],
        "mode": "bridge",
    }

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"domains": ["media_player"], "mode": "accessory"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "accessory"
    schema = result2["data_schema"].schema
    assert _get_schema_default(schema, CONF_ENTITIES) is None
    entity_selector = next(
        value for key, value in schema.items() if key.schema == CONF_ENTITIES
    )
    assert entity_selector.config["include_entities"] == ["media_player.tv"]

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"entities": "media_player.tv"},
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "review"
    assert result3["last_step"] is True
    assert _get_schema_default(result3["data_schema"].schema, CONF_ENTITIES) == [
        "media_player.tv"
    ]

    result3 = await _async_submit_options_review_step(hass, result3)
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "mode": "accessory",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": [],
            "include_entities": ["media_player.tv"],
        },
    }

    # Now we check again to make sure the single entity is still
    # preselected

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {
        "domains": ["media_player"],
        "mode": "accessory",
    }

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"domains": ["media_player"], "mode": "accessory"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "accessory"
    assert (
        _get_schema_default(result2["data_schema"].schema, "entities")
        == "media_player.tv"
    )

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"entities": "media_player.tv"},
    )
    result3 = await _async_submit_options_review_step(hass, result3)
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "mode": "accessory",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": [],
            "include_entities": ["media_player.tv"],
        },
    }
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_converting_bridge_to_accessory_mode(
    hass: HomeAssistant, hk_driver
) -> None:
    """Test we can convert a bridge to accessory mode."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"include_domains": ["light"]},
    )
    result2 = await _async_complete_config_entity_selection(hass, result2)
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "pairing"

    # We need to actually setup the config entry or the data
    # will not get migrated to options
    with (
        patch(
            "homeassistant.components.homekit.config_flow.async_find_next_available_port",
            return_value=12345,
        ),
        patch(
            "homeassistant.components.homekit.HomeKit.async_start",
            return_value=True,
        ) as mock_async_start,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"][:11] == "HASS Bridge"
    bridge_name = (result3["title"].split(":"))[0]
    assert result3["data"] == {
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["light"],
            "include_entities": [],
        },
        "exclude_accessory_mode": True,
        "mode": "bridge",
        "name": bridge_name,
        "port": 12345,
    }
    assert len(mock_async_start.mock_calls) == 1

    config_entry = result3["result"]

    hass.states.async_set("camera.tv", "off")
    hass.states.async_set("camera.sonos", "off")

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert _get_schema_default(schema, "mode") == "bridge"
    assert _get_schema_default(schema, "domains") == ["light"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"domains": ["camera"], "mode": "accessory"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "accessory"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"entities": "camera.tv"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "review"
    assert result2["last_step"] is False

    result2 = await _async_submit_options_review_step(hass, result2)
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "cameras"
    assert result2["last_step"] is True

    with (
        patch(
            "homeassistant.components.homekit.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch("homeassistant.components.homekit.async_port_is_available"),
    ):
        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={"camera_copy": ["camera.tv"]},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "entity_config": {"camera.tv": {"video_codec": "copy"}},
        "mode": "accessory",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": [],
            "include_entities": ["camera.tv"],
        },
    }
    assert len(mock_setup_entry.mock_calls) == 1
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)


def _get_schema_default(schema, key_name):
    """Iterate schema to find a key."""
    for schema_key in schema:
        if schema_key == key_name:
            return schema_key.default()
    raise KeyError(f"{key_name} not found in schema")


async def _async_complete_config_entity_selection(
    hass: HomeAssistant, result: ConfigFlowResult
) -> ConfigFlowResult:
    """Complete config flow entity refinement and review."""
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "include"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_INCLUDE_TARGETS: {}}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "review"
    return await hass.config_entries.flow.async_configure(result["flow_id"], {})


async def _async_submit_options_review_step(
    hass: HomeAssistant, result: ConfigFlowResult
) -> ConfigFlowResult:
    """Submit the options flow entity-selection review step."""
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "review"
    return await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )


async def test_options_flow_climate_accessory_type_round_trip(
    hass: HomeAssistant,
) -> None:
    """Test setting and clearing the climate accessory type."""
    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("climate.new", "off")
    await hass.async_block_till_done()

    async def _configure(choice: str) -> None:
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "domains": ["climate"],
            },
        )
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_INCLUDE_TARGETS: {ATTR_ENTITY_ID: ["climate.new"]}},
        )
        result2 = await _async_submit_options_review_step(hass, result2)
        assert result2["step_id"] == "climate"
        result2 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={"new (climate.new)": choice},
        )
        assert result2["step_id"] == "bridged_device_triggers"
        with patch(
            "homeassistant.components.homekit.async_setup_entry", return_value=True
        ):
            result3 = await hass.config_entries.options.async_configure(
                result2["flow_id"],
                user_input={},
            )
        assert result3["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

    await _configure("heater_cooler")
    assert config_entry.options["entity_config"]["climate.new"]["type"] == (
        "heater_cooler"
    )

    await _configure("thermostat")
    assert config_entry.options["entity_config"]["climate.new"]["type"] == "thermostat"

    await _configure("automatic")
    assert "entity_config" not in config_entry.options


async def test_options_flow_cameras_step_with_whole_domain_included(
    hass: HomeAssistant,
) -> None:
    """Test the cameras step is offered for a whole camera domain include."""
    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("camera.native_h264", "off")
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["fan", "camera"],
        },
    )
    assert result["step_id"] == "include"

    # No camera is selected explicitly, so the whole domain is included
    # and the camera options are still offered
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_INCLUDE_TARGETS: {}},
    )
    result2 = await _async_submit_options_review_step(hass, result2)
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "cameras"
    await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize(
    (
        "mode_options",
        "init_input",
        "entities_step",
        "entities_input",
        "extra_submits",
    ),
    [
        pytest.param(
            {},
            {"domains": ["climate"]},
            "include",
            {CONF_INCLUDE_TARGETS: {ATTR_ENTITY_ID: ["climate.new"]}},
            [{}],
            id="bridge",
        ),
        pytest.param(
            {"mode": "accessory"},
            {
                "domains": ["climate"],
                "mode": "accessory",
            },
            "accessory",
            {"entities": "climate.new"},
            [],
            id="accessory",
        ),
    ],
)
@patch(f"{PATH_HOMEKIT}.async_port_is_available", return_value=True)
@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_options_flow_climate_step_shows_current_accessory(
    port_mock: MagicMock,
    hass: HomeAssistant,
    hk_driver: HomeDriver,
    mode_options: dict[str, str],
    init_input: dict[str, Any],
    entities_step: str,
    entities_input: dict[str, Any],
    extra_submits: list[dict[str, Any]],
) -> None:
    """Test the climate labels show the accessory the entity uses now."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        options={
            **mode_options,
            "filter": {
                "include_domains": [],
                "include_entities": ["climate.new"],
                "exclude_domains": [],
                "exclude_entities": [],
            },
        },
    )
    config_entry.add_to_hass(hass)

    # A basic climate entity bridges as a Thermostat
    hass.states.async_set("climate.new", "off")
    await hass.async_block_till_done()

    with (
        patch(f"{PATH_HOMEKIT}.HomeDriver", return_value=hk_driver),
        patch("pyhap.util.get_local_address", return_value="10.10.10.10"),
    ):
        hk_driver.async_start = AsyncMock()
        hk_driver.async_stop = AsyncMock()
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=init_input
        )
        assert result["step_id"] == entities_step
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=entities_input
        )
        if result2["step_id"] == "review":
            result2 = await _async_submit_options_review_step(hass, result2)
        assert result2["step_id"] == "climate"
        assert result2["last_step"] is (mode_options.get("mode") == "accessory")
        assert [str(key) for key in result2["data_schema"].schema] == [
            "new (climate.new) [Thermostat]"
        ]

        # The annotated label still round trips to the entity id
        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={"new (climate.new) [Thermostat]": "heater_cooler"},
        )
        for submit_input in extra_submits:
            result3 = await hass.config_entries.options.async_configure(
                result3["flow_id"], user_input=submit_input
            )
        assert result3["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert config_entry.options["entity_config"]["climate.new"]["type"] == (
            "heater_cooler"
        )
        await hass.config_entries.async_unload(config_entry.entry_id)


async def test_options_flow_climate_step_with_whole_domain_included(
    hass: HomeAssistant,
) -> None:
    """Test the climate step lists all climate entities for a domain include."""
    config_entry = _mock_config_entry_with_options_populated()
    config_entry.add_to_hass(hass)

    hass.states.async_set("climate.new", "off")
    hass.states.async_set("climate.old", "off")
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "domains": ["fan", "climate"],
        },
    )
    assert result["step_id"] == "include"

    # No climate entity is selected explicitly, so the whole domain is
    # included and every climate entity is offered in the climate step.
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_INCLUDE_TARGETS: {}},
    )
    result2 = await _async_submit_options_review_step(hass, result2)
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "climate"
    assert [str(key) for key in result2["data_schema"].schema] == [
        "new (climate.new)",
        "old (climate.old)",
    ]

    result2 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={
            "new (climate.new)": "heater_cooler",
            "old (climate.old)": "automatic",
        },
    )
    assert result2["step_id"] == "bridged_device_triggers"
    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={},
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "devices": [],
        "mode": "bridge",
        "filter": {
            "exclude_domains": [],
            "exclude_entities": [],
            "include_domains": ["climate", "fan"],
            "include_entities": [],
        },
        "entity_config": {"climate.new": {"type": "heater_cooler"}},
    }
    await hass.config_entries.async_unload(config_entry.entry_id)
