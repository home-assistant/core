"""Test the Switch config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.group import DOMAIN, async_setup_entry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    (
        "group_type",
        "group_state",
        "member_state",
        "member_attributes",
        "extra_input",
        "extra_options",
        "extra_attrs",
    ),
    (
        ("binary_sensor", "on", "on", {}, {}, {"all": False}, {}),
        ("binary_sensor", "on", "on", {}, {"all": True}, {"all": True}, {}),
        ("cover", "open", "open", {}, {}, {}, {}),
        (
            "event",
            STATE_UNKNOWN,
            "2021-01-01T23:59:59.123+00:00",
            {
                "event_type": "single_press",
                "event_types": ["single_press", "double_press"],
            },
            {},
            {},
            {},
        ),
        ("fan", "on", "on", {}, {}, {}, {}),
        ("light", "on", "on", {}, {}, {}, {}),
        ("lock", "locked", "locked", {}, {}, {}, {}),
        ("media_player", "on", "on", {}, {}, {}, {}),
        (
            "sensor",
            "20.0",
            "10",
            {},
            {"type": "sum"},
            {"type": "sum"},
            {},
        ),
        ("switch", "on", "on", {}, {}, {}, {}),
    ),
)
async def test_config_flow(
    hass: HomeAssistant,
    group_type,
    group_state,
    member_state,
    member_attributes,
    extra_input,
    extra_options,
    extra_attrs,
) -> None:
    """Test the config flow."""
    members = [f"{group_type}.one", f"{group_type}.two"]
    for member in members:
        hass.states.async_set(member, member_state, member_attributes)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": group_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == group_type

    with patch(
        "homeassistant.components.group.async_setup_entry", wraps=async_setup_entry
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Living Room",
                "entities": members,
                **extra_input,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room"
    assert result["data"] == {}
    assert result["options"] == {
        "entities": members,
        "group_type": group_type,
        "hide_members": False,
        "name": "Living Room",
        **extra_options,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "entities": members,
        "group_type": group_type,
        "hide_members": False,
        "name": "Living Room",
        **extra_options,
    }

    state = hass.states.get(f"{group_type}.living_room")
    assert state.state == group_state
    assert state.attributes["entity_id"] == members
    for key in extra_attrs:
        assert state.attributes[key] == extra_attrs[key]


@pytest.mark.parametrize(
    ("hide_members", "hidden_by"), ((False, None), (True, "integration"))
)
@pytest.mark.parametrize(
    ("group_type", "extra_input"),
    (
        ("binary_sensor", {"all": False}),
        ("cover", {}),
        ("event", {}),
        ("fan", {}),
        ("light", {}),
        ("lock", {}),
        ("media_player", {}),
        ("switch", {}),
    ),
)
async def test_config_flow_hides_members(
    hass: HomeAssistant, group_type, extra_input, hide_members, hidden_by
) -> None:
    """Test the config flow hides members if requested."""
    fake_uuid = "a266a680b608c32770e6c45bfe6b8411"
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        group_type, "test", "unique", suggested_object_id="one"
    )
    assert entry.entity_id == f"{group_type}.one"
    assert entry.hidden_by is None

    entry = registry.async_get_or_create(
        group_type, "test", "unique3", suggested_object_id="three"
    )
    assert entry.entity_id == f"{group_type}.three"
    assert entry.hidden_by is None

    members = [f"{group_type}.one", f"{group_type}.two", fake_uuid, entry.id]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": group_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == group_type

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Living Room",
            "entities": members,
            "hide_members": hide_members,
            **extra_input,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY

    assert registry.async_get(f"{group_type}.one").hidden_by == hidden_by
    assert registry.async_get(f"{group_type}.three").hidden_by == hidden_by


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema:
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise Exception


@pytest.mark.parametrize(
    ("group_type", "member_state", "extra_options", "options_options"),
    (
        ("binary_sensor", "on", {"all": False}, {}),
        ("cover", "open", {}, {}),
        ("event", "2021-01-01T23:59:59.123+00:00", {}, {}),
        ("fan", "on", {}, {}),
        ("light", "on", {"all": False}, {}),
        ("lock", "locked", {}, {}),
        ("media_player", "on", {}, {}),
        (
            "sensor",
            "10",
            {"ignore_non_numeric": False, "type": "sum"},
            {"ignore_non_numeric": False, "type": "sum"},
        ),
        ("switch", "on", {"all": False}, {}),
    ),
)
async def test_options(
    hass: HomeAssistant, group_type, member_state, extra_options, options_options
) -> None:
    """Test reconfiguring."""
    members1 = [f"{group_type}.one", f"{group_type}.two"]
    members2 = [f"{group_type}.four", f"{group_type}.five"]

    for member in members1:
        hass.states.async_set(member, member_state, {})
    for member in members2:
        hass.states.async_set(member, member_state, {})

    group_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entities": members1,
            "group_type": group_type,
            "name": "Bed Room",
            **extra_options,
        },
        title="Bed Room",
    )
    group_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(group_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"{group_type}.bed_room")
    assert state.attributes["entity_id"] == members1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == group_type
    assert get_suggested(result["data_schema"].schema, "entities") == members1
    assert "name" not in result["data_schema"].schema
    assert result["data_schema"].schema["entities"].config["exclude_entities"] == [
        f"{group_type}.bed_room"
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"entities": members2, **options_options},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "entities": members2,
        "group_type": group_type,
        "hide_members": False,
        "name": "Bed Room",
        **extra_options,
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "entities": members2,
        "group_type": group_type,
        "hide_members": False,
        "name": "Bed Room",
        **extra_options,
    }
    assert config_entry.title == "Bed Room"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()
    state = hass.states.get(f"{group_type}.bed_room")
    assert state.attributes["entity_id"] == members2

    # Check we don't get suggestions from another entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": group_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == group_type

    assert get_suggested(result["data_schema"].schema, "entities") is None
    assert get_suggested(result["data_schema"].schema, "name") is None


@pytest.mark.parametrize(
    ("group_type", "extra_options", "extra_options_after", "advanced"),
    (
        ("light", {"all": False}, {"all": False}, False),
        ("light", {"all": True}, {"all": True}, False),
        ("light", {"all": False}, {"all": False}, True),
        ("light", {"all": True}, {"all": False}, True),
        ("switch", {"all": False}, {"all": False}, False),
        ("switch", {"all": True}, {"all": True}, False),
        ("switch", {"all": False}, {"all": False}, True),
        ("switch", {"all": True}, {"all": False}, True),
    ),
)
async def test_all_options(
    hass: HomeAssistant, group_type, extra_options, extra_options_after, advanced
) -> None:
    """Test reconfiguring."""
    members1 = [f"{group_type}.one", f"{group_type}.two"]
    members2 = [f"{group_type}.four", f"{group_type}.five"]

    group_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entities": members1,
            "group_type": group_type,
            "name": "Bed Room",
            **extra_options,
        },
        title="Bed Room",
    )
    group_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(group_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{group_type}.bed_room")

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": advanced}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == group_type

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": members2,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "entities": members2,
        "group_type": group_type,
        "hide_members": False,
        "name": "Bed Room",
        **extra_options_after,
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "entities": members2,
        "group_type": group_type,
        "hide_members": False,
        "name": "Bed Room",
        **extra_options_after,
    }
    assert config_entry.title == "Bed Room"


@pytest.mark.parametrize(
    ("hide_members", "hidden_by_initial", "hidden_by"),
    (
        (False, er.RegistryEntryHider.INTEGRATION, None),
        (True, None, er.RegistryEntryHider.INTEGRATION),
    ),
)
@pytest.mark.parametrize(
    ("group_type", "extra_input"),
    (
        ("binary_sensor", {"all": False}),
        ("cover", {}),
        ("event", {}),
        ("fan", {}),
        ("light", {}),
        ("lock", {}),
        ("media_player", {}),
        ("switch", {}),
    ),
)
async def test_options_flow_hides_members(
    hass: HomeAssistant,
    group_type,
    extra_input,
    hide_members,
    hidden_by_initial,
    hidden_by,
) -> None:
    """Test the options flow hides or unhides members if requested."""
    fake_uuid = "a266a680b608c32770e6c45bfe6b8411"
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        group_type,
        "test",
        "unique1",
        suggested_object_id="one",
        hidden_by=hidden_by_initial,
    )
    assert entry.entity_id == f"{group_type}.one"

    entry = registry.async_get_or_create(
        group_type,
        "test",
        "unique3",
        suggested_object_id="three",
        hidden_by=hidden_by_initial,
    )
    assert entry.entity_id == f"{group_type}.three"

    members = [f"{group_type}.one", f"{group_type}.two", fake_uuid, entry.id]

    group_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entities": members,
            "group_type": group_type,
            "hide_members": False,
            "name": "Bed Room",
            **extra_input,
        },
        title="Bed Room",
    )
    group_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(group_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(group_config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": members,
            "hide_members": hide_members,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY

    assert registry.async_get(f"{group_type}.one").hidden_by == hidden_by
    assert registry.async_get(f"{group_type}.three").hidden_by == hidden_by
