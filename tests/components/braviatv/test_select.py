"""Test the BraviaTV select platform."""

from unittest.mock import patch

from pybravia import BraviaError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.braviatv.const import CONF_USE_PSK, DOMAIN
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_MAC, CONF_PIN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

BRAVIA_SYSTEM_INFO = {
    "product": "TV",
    "region": "XEU",
    "language": "pol",
    "model": "TV-Model",
    "serial": "serial_number",
    "macAddr": "AA:BB:CC:DD:EE:FF",
    "name": "BRAVIA",
    "generation": "5.2.0",
    "area": "POL",
    "cid": "very_unique_string",
}

PICTURE_SETTINGS_WITH_ENUMS = [
    {
        # Enum setting with dict-style candidates (real Sony API format)
        "target": "pictureMode",
        "currentValue": "vivid",
        "candidate": [
            {"value": "vivid"},
            {"value": "standard"},
            {"value": "cinema"},
            {"value": "custom"},
        ],
        "isAvailable": True,
    },
    {
        # Enum setting with dict-style candidates
        "target": "colorSpace",
        "currentValue": "auto",
        "candidate": [{"value": "auto"}, {"value": "bt2020"}, {"value": "bt709"}],
        "isAvailable": True,
    },
    {
        # Enum setting with dict-style candidates
        "target": "hdrMode",
        "currentValue": "auto",
        "candidate": [{"value": "auto"}, {"value": "on"}, {"value": "off"}],
        "isAvailable": True,
    },
    {
        # Numeric setting - should NOT be created as select
        "target": "brightness",
        "currentValue": "50",
        "candidate": [{"min": 0, "max": 100, "step": 1}],
        "isAvailable": True,
    },
]


@pytest.fixture
def platforms() -> list[Platform]:
    """Overridden fixture to specify platforms to test."""
    return [Platform.SELECT]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the BraviaTV integration for testing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="BRAVIA TV-Model",
        data={
            CONF_HOST: "localhost",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_USE_PSK: True,
            CONF_PIN: "12345qwerty",
        },
        unique_id="very_unique_string",
        entry_id="3bd2acb0e4f0476d40865546d0d91921",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.braviatv.PLATFORMS", platforms),
        patch("pybravia.BraviaClient.connect"),
        patch("pybravia.BraviaClient.pair"),
        patch("pybravia.BraviaClient.set_wol_mode"),
        patch("pybravia.BraviaClient.get_system_info", return_value=BRAVIA_SYSTEM_INFO),
        patch("pybravia.BraviaClient.get_power_status", return_value="active"),
        patch("pybravia.BraviaClient.get_external_status", return_value=[]),
        patch("pybravia.BraviaClient.get_volume_info", return_value={}),
        patch("pybravia.BraviaClient.get_playing_info", return_value={}),
        patch("pybravia.BraviaClient.get_app_list", return_value=[]),
        patch("pybravia.BraviaClient.get_content_list_all", return_value=[]),
        patch(
            "pybravia.BraviaClient.get_picture_setting",
            return_value=PICTURE_SETTINGS_WITH_ENUMS,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the select entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_entities_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that select entities are disabled by default."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, "3bd2acb0e4f0476d40865546d0d91921"
    )
    select_entities = [
        entry for entry in entity_entries if entry.domain == SELECT_DOMAIN
    ]

    # Should have 3 entities (one for each enum setting, not the numeric one)
    assert len(select_entities) == 3

    # All should be disabled by default
    for entity in select_entities:
        assert entity.disabled_by == er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_select_option(
    hass: HomeAssistant,
) -> None:
    """Test selecting an option."""
    state = hass.states.get("select.bravia_tv_model_picture_mode")
    assert state
    assert state.state == "vivid"
    assert state.attributes["options"] == ["vivid", "standard", "cinema", "custom"]

    with patch("pybravia.BraviaClient.set_picture_setting") as mock_set:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.bravia_tv_model_picture_mode",
                ATTR_OPTION: "cinema",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_set.assert_called_once_with("pictureMode", "cinema")


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_select_option_error(
    hass: HomeAssistant,
) -> None:
    """Test error handling when selecting an option."""
    with (
        patch(
            "pybravia.BraviaClient.set_picture_setting",
            side_effect=BraviaError("Test error"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.bravia_tv_model_picture_mode",
                ATTR_OPTION: "cinema",
            },
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_enum_settings_available(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test when no enum settings are available."""
    # Only numeric settings - no select entities should be created
    picture_settings_numeric_only = [
        {
            "target": "brightness",
            "currentValue": "50",
            "candidate": [{"min": 0, "max": 100, "step": 1}],
        },
        {
            "target": "contrast",
            "currentValue": "75",
            "candidate": [{"min": 0, "max": 100, "step": 1}],
        },
    ]

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="BRAVIA TV-Model",
        data={
            CONF_HOST: "localhost",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_USE_PSK: True,
            CONF_PIN: "12345qwerty",
        },
        unique_id="very_unique_string_no_enums",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.braviatv.PLATFORMS", [Platform.SELECT]),
        patch("pybravia.BraviaClient.connect"),
        patch("pybravia.BraviaClient.pair"),
        patch("pybravia.BraviaClient.set_wol_mode"),
        patch("pybravia.BraviaClient.get_system_info", return_value=BRAVIA_SYSTEM_INFO),
        patch("pybravia.BraviaClient.get_power_status", return_value="active"),
        patch("pybravia.BraviaClient.get_external_status", return_value=[]),
        patch("pybravia.BraviaClient.get_volume_info", return_value={}),
        patch("pybravia.BraviaClient.get_playing_info", return_value={}),
        patch("pybravia.BraviaClient.get_app_list", return_value=[]),
        patch("pybravia.BraviaClient.get_content_list_all", return_value=[]),
        patch(
            "pybravia.BraviaClient.get_picture_setting",
            return_value=picture_settings_numeric_only,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Should have no select entities
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    select_entities = [
        entry for entry in entity_entries if entry.domain == SELECT_DOMAIN
    ]
    assert len(select_entities) == 0


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_select_entity_values(
    hass: HomeAssistant,
) -> None:
    """Test that select entities have correct values and options."""
    # Test picture mode
    state = hass.states.get("select.bravia_tv_model_picture_mode")
    assert state
    assert state.state == "vivid"
    assert state.attributes["options"] == ["vivid", "standard", "cinema", "custom"]

    # Test color space
    state = hass.states.get("select.bravia_tv_model_color_space")
    assert state
    assert state.state == "auto"
    assert state.attributes["options"] == ["auto", "bt2020", "bt709"]

    # Test HDR mode
    state = hass.states.get("select.bravia_tv_model_hdr_mode")
    assert state
    assert state.state == "auto"
    assert state.attributes["options"] == ["auto", "on", "off"]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_numeric_settings_not_created_as_selects(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that numeric settings are not created as select entities."""
    # Mix of numeric and enum settings - only enum should create entities
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="BRAVIA TV-Model",
        data={
            CONF_HOST: "localhost",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_USE_PSK: True,
            CONF_PIN: "12345qwerty",
        },
        unique_id="very_unique_string_mixed",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.braviatv.PLATFORMS", [Platform.SELECT]),
        patch("pybravia.BraviaClient.connect"),
        patch("pybravia.BraviaClient.pair"),
        patch("pybravia.BraviaClient.set_wol_mode"),
        patch("pybravia.BraviaClient.get_system_info", return_value=BRAVIA_SYSTEM_INFO),
        patch("pybravia.BraviaClient.get_power_status", return_value="active"),
        patch("pybravia.BraviaClient.get_external_status", return_value=[]),
        patch("pybravia.BraviaClient.get_volume_info", return_value={}),
        patch("pybravia.BraviaClient.get_playing_info", return_value={}),
        patch("pybravia.BraviaClient.get_app_list", return_value=[]),
        patch("pybravia.BraviaClient.get_content_list_all", return_value=[]),
        patch(
            "pybravia.BraviaClient.get_picture_setting",
            return_value=PICTURE_SETTINGS_WITH_ENUMS,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Only enum settings should be created (3 from PICTURE_SETTINGS_WITH_ENUMS)
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    select_entities = [
        entry for entry in entity_entries if entry.domain == SELECT_DOMAIN
    ]
    assert len(select_entities) == 3

    # Enum settings should exist
    assert hass.states.get("select.bravia_tv_model_picture_mode")
    assert hass.states.get("select.bravia_tv_model_color_space")
    assert hass.states.get("select.bravia_tv_model_hdr_mode")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_is_available_field_affects_availability(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that Sony API isAvailable field affects entity availability."""
    picture_settings_with_availability = [
        {
            "target": "pictureMode",
            "currentValue": "vivid",
            "candidate": [
                {"value": "vivid"},
                {"value": "standard"},
                {"value": "cinema"},
            ],
            "isAvailable": True,
        },
        {
            "target": "colorSpace",
            "currentValue": "auto",
            "candidate": [
                {"value": "auto"},
                {"value": "bt2020"},
                {"value": "bt709"},
            ],
            "isAvailable": False,  # Not currently available
        },
    ]

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="BRAVIA TV-Model",
        data={
            CONF_HOST: "localhost",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_USE_PSK: True,
            CONF_PIN: "12345qwerty",
        },
        unique_id="very_unique_string_availability",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.braviatv.PLATFORMS", [Platform.SELECT]),
        patch("pybravia.BraviaClient.connect"),
        patch("pybravia.BraviaClient.pair"),
        patch("pybravia.BraviaClient.set_wol_mode"),
        patch("pybravia.BraviaClient.get_system_info", return_value=BRAVIA_SYSTEM_INFO),
        patch("pybravia.BraviaClient.get_power_status", return_value="active"),
        patch("pybravia.BraviaClient.get_external_status", return_value=[]),
        patch("pybravia.BraviaClient.get_volume_info", return_value={}),
        patch("pybravia.BraviaClient.get_playing_info", return_value={}),
        patch("pybravia.BraviaClient.get_app_list", return_value=[]),
        patch("pybravia.BraviaClient.get_content_list_all", return_value=[]),
        patch(
            "pybravia.BraviaClient.get_picture_setting",
            return_value=picture_settings_with_availability,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Picture mode should be available (isAvailable=True)
    state = hass.states.get("select.bravia_tv_model_picture_mode")
    assert state
    assert state.state == "vivid"

    # Color space should be unavailable (isAvailable=False)
    state = hass.states.get("select.bravia_tv_model_color_space")
    assert state
    assert state.state == "unavailable"
