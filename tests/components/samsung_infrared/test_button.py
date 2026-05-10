"""Tests for the Samsung Infrared button platform."""

from infrared_protocols.codes.samsung.tv import SamsungTVCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MockInfraredEntity
from .utils import check_availability_follows_ir_entity

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.BUTTON]


@pytest.mark.usefixtures("init_integration")
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
    device_entry = device_registry.async_get_device(
        identifiers={("samsung_infrared", mock_config_entry.entry_id)}
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
        ("button.samsung_tv_power", SamsungTVCode.POWER),
        ("button.samsung_tv_power_off", SamsungTVCode.POWER_OFF),
        ("button.samsung_tv_hdmi_1", SamsungTVCode.HDMI_1),
        ("button.samsung_tv_hdmi_2", SamsungTVCode.HDMI_2),
        ("button.samsung_tv_hdmi_3", SamsungTVCode.HDMI_3),
        ("button.samsung_tv_hdmi_4", SamsungTVCode.HDMI_4),
        ("button.samsung_tv_exit", SamsungTVCode.EXIT),
        ("button.samsung_tv_info", SamsungTVCode.INFO),
        ("button.samsung_tv_up", SamsungTVCode.NAV_UP),
        ("button.samsung_tv_down", SamsungTVCode.NAV_DOWN),
        ("button.samsung_tv_left", SamsungTVCode.NAV_LEFT),
        ("button.samsung_tv_right", SamsungTVCode.NAV_RIGHT),
        ("button.samsung_tv_ok", SamsungTVCode.OK),
        ("button.samsung_tv_return", SamsungTVCode.RETURN),
        ("button.samsung_tv_home", SamsungTVCode.HOME),
        ("button.samsung_tv_settings", SamsungTVCode.SETTINGS),
        ("button.samsung_tv_source", SamsungTVCode.SOURCE),
        ("button.samsung_tv_mute", SamsungTVCode.MUTE),
        ("button.samsung_tv_volume_up", SamsungTVCode.VOLUME_UP),
        ("button.samsung_tv_volume_down", SamsungTVCode.VOLUME_DOWN),
        ("button.samsung_tv_channel_up", SamsungTVCode.CHANNEL_UP),
        ("button.samsung_tv_channel_down", SamsungTVCode.CHANNEL_DOWN),
        ("button.samsung_tv_number_0", SamsungTVCode.NUM_0),
        ("button.samsung_tv_number_1", SamsungTVCode.NUM_1),
        ("button.samsung_tv_number_2", SamsungTVCode.NUM_2),
        ("button.samsung_tv_number_3", SamsungTVCode.NUM_3),
        ("button.samsung_tv_number_4", SamsungTVCode.NUM_4),
        ("button.samsung_tv_number_5", SamsungTVCode.NUM_5),
        ("button.samsung_tv_number_6", SamsungTVCode.NUM_6),
        ("button.samsung_tv_number_7", SamsungTVCode.NUM_7),
        ("button.samsung_tv_number_8", SamsungTVCode.NUM_8),
        ("button.samsung_tv_number_9", SamsungTVCode.NUM_9),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_button_press_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_entity: MockInfraredEntity,
    entity_id: str,
    expected_code: SamsungTVCode,
) -> None:
    """Test pressing a button sends the correct IR code."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mock_infrared_entity.send_command_calls) == 1
    assert mock_infrared_entity.send_command_calls[0] == expected_code


@pytest.mark.usefixtures("init_integration")
async def test_button_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test button becomes unavailable when IR entity is unavailable."""
    entity_id = "button.samsung_tv_power"
    await check_availability_follows_ir_entity(hass, entity_id)
