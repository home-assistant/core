"""Test the BraviaTV number platform."""

from unittest.mock import patch

from pybravia import BraviaError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.braviatv.const import CONF_USE_PSK, DOMAIN
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_MAC, CONF_PIN, Platform
from homeassistant.core import HomeAssistant
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

PICTURE_SETTINGS = [
    {"target": "brightness", "currentValue": "50", "minValue": "0", "maxValue": "100"},
    {"target": "contrast", "currentValue": "75", "minValue": "0", "maxValue": "100"},
    {"target": "color", "currentValue": "60", "minValue": "0", "maxValue": "100"},
    {"target": "sharpness", "currentValue": "30", "minValue": "0", "maxValue": "100"},
    {
        "target": "colorTemperature",
        "currentValue": "40",
        "minValue": "0",
        "maxValue": "100",
    },
]


@pytest.fixture
def platforms() -> list[Platform]:
    """Overridden fixture to specify platforms to test."""
    return [Platform.NUMBER]


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
            return_value=PICTURE_SETTINGS,
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
    """Test the number entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_entities_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that number entities are disabled by default."""
    # Check that entities exist but are disabled
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, "3bd2acb0e4f0476d40865546d0d91921"
    )
    number_entities = [
        entry for entry in entity_entries if entry.domain == NUMBER_DOMAIN
    ]

    # Should have 5 entities (one for each supported setting)
    assert len(number_entities) == 5

    # All should be disabled by default
    for entity in number_entities:
        assert entity.disabled_by == er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_set_number_value(
    hass: HomeAssistant,
) -> None:
    """Test setting a number value."""
    state = hass.states.get("number.bravia_tv_model_picture_brightness")
    assert state
    assert state.state == "50"

    with patch("pybravia.BraviaClient.set_picture_setting") as mock_set:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.bravia_tv_model_picture_brightness",
                ATTR_VALUE: 80,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_set.assert_called_once_with("brightness", "80")


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_set_number_value_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling when setting a number value."""
    with patch(
        "pybravia.BraviaClient.set_picture_setting",
        side_effect=BraviaError("Test error"),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.bravia_tv_model_picture_brightness",
                ATTR_VALUE: 80,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert "Command error: Test error" in caplog.text


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_picture_settings_available(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test when no picture settings are available."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="BRAVIA TV-Model",
        data={
            CONF_HOST: "localhost",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_USE_PSK: True,
            CONF_PIN: "12345qwerty",
        },
        unique_id="very_unique_string_2",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.braviatv.PLATFORMS", [Platform.NUMBER]),
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
            side_effect=BraviaError("Not supported"),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Should have no number entities
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    number_entities = [
        entry for entry in entity_entries if entry.domain == NUMBER_DOMAIN
    ]
    assert len(number_entities) == 0


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_number_entity_values(
    hass: HomeAssistant,
) -> None:
    """Test that number entities have correct values."""
    # Test brightness
    state = hass.states.get("number.bravia_tv_model_picture_brightness")
    assert state
    assert state.state == "50"

    # Test contrast
    state = hass.states.get("number.bravia_tv_model_picture_contrast")
    assert state
    assert state.state == "75"

    # Test color
    state = hass.states.get("number.bravia_tv_model_picture_color")
    assert state
    assert state.state == "60"

    # Test sharpness
    state = hass.states.get("number.bravia_tv_model_picture_sharpness")
    assert state
    assert state.state == "30"

    # Test color temperature
    state = hass.states.get("number.bravia_tv_model_color_temperature")
    assert state
    assert state.state == "40"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dynamic_attributes_from_api(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that min/max/step are dynamically read from API candidate data."""
    # Picture settings with candidate structure containing custom min/max/step
    picture_settings_with_candidates = [
        {
            "target": "brightness",
            "currentValue": "25",
            "candidate": [{"min": 10, "max": 50, "step": 5}],
        },
        {
            "target": "contrast",
            "currentValue": "60",
            "candidate": [{"min": 20, "max": 80, "step": 2}],
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
        unique_id="very_unique_string_dynamic",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.braviatv.PLATFORMS", [Platform.NUMBER]),
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
            return_value=picture_settings_with_candidates,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Test brightness entity has custom min/max/step from candidate data
    state = hass.states.get("number.bravia_tv_model_picture_brightness")
    assert state
    assert state.state == "25"
    assert state.attributes["min"] == 10
    assert state.attributes["max"] == 50
    assert state.attributes["step"] == 5

    # Test contrast entity has custom min/max/step from candidate data
    state = hass.states.get("number.bravia_tv_model_picture_contrast")
    assert state
    assert state.state == "60"
    assert state.attributes["min"] == 20
    assert state.attributes["max"] == 80
    assert state.attributes["step"] == 2


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_default_attributes_without_candidate_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that default min/max/step are used when API doesn't provide candidate data."""
    # Picture settings without candidate structure - should use defaults
    picture_settings_without_candidates = [
        {
            "target": "brightness",
            "currentValue": "50",
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
        unique_id="very_unique_string_defaults",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.braviatv.PLATFORMS", [Platform.NUMBER]),
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
            return_value=picture_settings_without_candidates,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Test brightness entity uses default min/max/step values
    state = hass.states.get("number.bravia_tv_model_picture_brightness")
    assert state
    assert state.state == "50"
    assert state.attributes["min"] == 0  # Default
    assert state.attributes["max"] == 100  # Default
    assert state.attributes["step"] == 1  # Default
