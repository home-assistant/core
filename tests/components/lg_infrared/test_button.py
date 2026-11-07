"""Tests for the LG Infrared button platform."""

from infrared_protocols.codes.lg.ac import LGACCode
from infrared_protocols.codes.lg.home_theater import LGHomeTheaterCode
from infrared_protocols.codes.lg.tv import LGTVCode
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.components.common import (
    assert_availability_follows_source_entity,
)
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.lg_infrared.const import LGDeviceType
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.BUTTON]


@pytest.mark.parametrize(
    "device_type", [LGDeviceType.TV, LGDeviceType.AC, LGDeviceType.HOME_THEATER]
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all button entities are created with correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Verify all entities belong to the same device
    device_entry = device_registry.async_get_device_by_identifier(
        ("lg_infrared", mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize(
    ("entity_id", "expected_code"),
    [
        ("button.lg_tv_power", LGTVCode.POWER),
        ("button.lg_tv_power_on", LGTVCode.POWER_ON),
        ("button.lg_tv_power_off", LGTVCode.POWER_OFF),
        ("button.lg_tv_hdmi_1", LGTVCode.HDMI_1),
        ("button.lg_tv_hdmi_2", LGTVCode.HDMI_2),
        ("button.lg_tv_hdmi_3", LGTVCode.HDMI_3),
        ("button.lg_tv_hdmi_4", LGTVCode.HDMI_4),
        ("button.lg_tv_exit", LGTVCode.EXIT),
        ("button.lg_tv_info", LGTVCode.INFO),
        ("button.lg_tv_guide", LGTVCode.GUIDE),
        ("button.lg_tv_up", LGTVCode.NAV_UP),
        ("button.lg_tv_down", LGTVCode.NAV_DOWN),
        ("button.lg_tv_left", LGTVCode.NAV_LEFT),
        ("button.lg_tv_right", LGTVCode.NAV_RIGHT),
        ("button.lg_tv_ok", LGTVCode.OK),
        ("button.lg_tv_back", LGTVCode.BACK),
        ("button.lg_tv_home", LGTVCode.HOME),
        ("button.lg_tv_menu", LGTVCode.MENU),
        ("button.lg_tv_input", LGTVCode.INPUT),
        ("button.lg_tv_number_0", LGTVCode.NUM_0),
        ("button.lg_tv_number_1", LGTVCode.NUM_1),
        ("button.lg_tv_number_2", LGTVCode.NUM_2),
        ("button.lg_tv_number_3", LGTVCode.NUM_3),
        ("button.lg_tv_number_4", LGTVCode.NUM_4),
        ("button.lg_tv_number_5", LGTVCode.NUM_5),
        ("button.lg_tv_number_6", LGTVCode.NUM_6),
        ("button.lg_tv_number_7", LGTVCode.NUM_7),
        ("button.lg_tv_number_8", LGTVCode.NUM_8),
        ("button.lg_tv_number_9", LGTVCode.NUM_9),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_button_press_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    expected_code: LGTVCode,
) -> None:
    """Test pressing a button sends the correct IR code."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert mock_infrared_emitter_entity.send_command_calls[0] == expected_code


@pytest.mark.usefixtures("init_integration")
async def test_button_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test button becomes unavailable when IR entity is unavailable."""
    entity_id = "button.lg_tv_power_on"
    await assert_availability_follows_source_entity(
        hass, entity_id, [EMITTER_ENTITY_ID]
    )


@pytest.mark.parametrize("device_type", [LGDeviceType.AC])
@pytest.mark.parametrize(
    ("entity_id", "expected_code"),
    [
        ("button.lg_ac_jet_mode", LGACCode.JET),
        ("button.lg_ac_eco_mode", LGACCode.ECO),
        ("button.lg_ac_viraat_mode", LGACCode.VIRAAT),
        ("button.lg_ac_ai_mode", LGACCode.AI_CONVERTIBLE),
        ("button.lg_ac_toggle_light", LGACCode.LIGHT_TOGGLE),
        ("button.lg_ac_start_wi_fi_pairing", LGACCode.WIFI_TOGGLE),
        ("button.lg_ac_toggle_beep", LGACCode.AUDIO_TOGGLE),
        ("button.lg_ac_diagnose", LGACCode.DIAGNOSE),
        ("button.lg_ac_toggle_vertical_swing", LGACCode.SWING_V_TOGGLE),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_ac_button_press_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    expected_code: LGACCode,
) -> None:
    """Test pressing an AC button sends the matching fixed IR code."""
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == expected_code.to_command().get_raw_timings()


@pytest.mark.parametrize("device_type", [LGDeviceType.AC])
@pytest.mark.parametrize("key", ["swing_v_toggle", "viraat"])
@pytest.mark.usefixtures("init_integration")
async def test_ac_buttons_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    key: str,
) -> None:
    """Test the buttons only some units support are registered but disabled."""
    entity_id = entity_registry.async_get_entity_id(
        BUTTON_DOMAIN, "lg_infrared", f"{mock_config_entry.entry_id}_{key}"
    )
    assert entity_id is not None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("device_type", [LGDeviceType.HOME_THEATER])
@pytest.mark.parametrize(
    ("entity_id", "expected_code"),
    [
        ("button.lg_home_theater_power", LGHomeTheaterCode.POWER),
        ("button.lg_home_theater_home", LGHomeTheaterCode.HOME),
        ("button.lg_home_theater_input", LGHomeTheaterCode.FUNCTION),
        ("button.lg_home_theater_info", LGHomeTheaterCode.INFO_MENU),
        ("button.lg_home_theater_disc_menu", LGHomeTheaterCode.DISC_MENU),
        ("button.lg_home_theater_title_popup", LGHomeTheaterCode.TITLE_POPUP),
        ("button.lg_home_theater_up", LGHomeTheaterCode.NAV_UP),
        ("button.lg_home_theater_down", LGHomeTheaterCode.NAV_DOWN),
        ("button.lg_home_theater_left", LGHomeTheaterCode.NAV_LEFT),
        ("button.lg_home_theater_right", LGHomeTheaterCode.NAV_RIGHT),
        ("button.lg_home_theater_ok", LGHomeTheaterCode.OK),
        ("button.lg_home_theater_back", LGHomeTheaterCode.BACK),
        ("button.lg_home_theater_clear", LGHomeTheaterCode.CLEAR),
        ("button.lg_home_theater_number_0", LGHomeTheaterCode.NUM_0),
        ("button.lg_home_theater_number_1", LGHomeTheaterCode.NUM_1),
        ("button.lg_home_theater_number_2", LGHomeTheaterCode.NUM_2),
        ("button.lg_home_theater_number_3", LGHomeTheaterCode.NUM_3),
        ("button.lg_home_theater_number_4", LGHomeTheaterCode.NUM_4),
        ("button.lg_home_theater_number_5", LGHomeTheaterCode.NUM_5),
        ("button.lg_home_theater_number_6", LGHomeTheaterCode.NUM_6),
        ("button.lg_home_theater_number_7", LGHomeTheaterCode.NUM_7),
        ("button.lg_home_theater_number_8", LGHomeTheaterCode.NUM_8),
        ("button.lg_home_theater_number_9", LGHomeTheaterCode.NUM_9),
        ("button.lg_home_theater_asterisk", LGHomeTheaterCode.ASTERISK),
        ("button.lg_home_theater_open_close", LGHomeTheaterCode.OPEN_CLOSE),
        (
            "button.lg_home_theater_optical_tv_sound",
            LGHomeTheaterCode.OPTICAL_TV_SOUND,
        ),
        ("button.lg_home_theater_sound_effect", LGHomeTheaterCode.SOUND_EFFECT),
        ("button.lg_home_theater_speaker_level", LGHomeTheaterCode.SPEAKER_LEVEL),
        ("button.lg_home_theater_audio_track", LGHomeTheaterCode.AUDIO),
        ("button.lg_home_theater_subtitle", LGHomeTheaterCode.SUBTITLE),
        ("button.lg_home_theater_sleep", LGHomeTheaterCode.SLEEP),
        ("button.lg_home_theater_record", LGHomeTheaterCode.RECORD),
        ("button.lg_home_theater_repeat", LGHomeTheaterCode.REPEAT),
        ("button.lg_home_theater_rewind", LGHomeTheaterCode.SCAN_BACKWARD),
        ("button.lg_home_theater_fast_forward", LGHomeTheaterCode.SCAN_FORWARD),
        ("button.lg_home_theater_red", LGHomeTheaterCode.RED),
        ("button.lg_home_theater_green", LGHomeTheaterCode.GREEN),
        ("button.lg_home_theater_yellow", LGHomeTheaterCode.YELLOW),
        ("button.lg_home_theater_blue", LGHomeTheaterCode.BLUE),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_home_theater_button_press_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    expected_code: LGHomeTheaterCode,
) -> None:
    """Test pressing a Home Theater button sends the correct IR code."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert mock_infrared_emitter_entity.send_command_calls[0] == expected_code


@pytest.mark.parametrize("device_type", [LGDeviceType.HOME_THEATER])
@pytest.mark.usefixtures("init_integration")
async def test_home_theater_button_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test Home Theater button becomes unavailable when IR entity is unavailable."""
    entity_id = "button.lg_home_theater_power"
    await assert_availability_follows_source_entity(
        hass, entity_id, [EMITTER_ENTITY_ID]
    )
