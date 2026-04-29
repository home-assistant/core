"""Tests for the LG Infrared button platform."""

from __future__ import annotations

from infrared_protocols.codes.lg.tv import LGTVCode
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
        identifiers={("lg_infrared", mock_config_entry.entry_id)}
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
    mock_infrared_entity: MockInfraredEntity,
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

    assert len(mock_infrared_entity.send_command_calls) == 1
    assert mock_infrared_entity.send_command_calls[0] == expected_code


@pytest.mark.usefixtures("init_integration")
async def test_button_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test button becomes unavailable when IR entity is unavailable."""
    entity_id = "button.lg_tv_power_on"
    await check_availability_follows_ir_entity(hass, entity_id)
