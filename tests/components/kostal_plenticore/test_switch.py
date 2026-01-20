"""Test the Kostal Plenticore Solar Inverter switch platform."""

from datetime import timedelta
from unittest.mock import Mock

from pykoplenti import SettingsData
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = [
    pytest.mark.usefixtures("mock_plenticore_client"),
]


async def test_installer_setting_not_available(
    hass: HomeAssistant,
    mock_get_settings: dict[str, list[SettingsData]],
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the manual charge setting is not available when not using the installer login."""
    mock_get_settings.update(
        {
            "devices:local": [
                SettingsData(
                    min=None,
                    max=None,
                    default=None,
                    access="readwrite",
                    unit=None,
                    id="Battery:ManualCharge",
                    type="bool",
                )
            ]
        }
    )

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not entity_registry.async_is_registered("switch.scb_battery_manual_charge")


async def test_installer_setting_available(
    hass: HomeAssistant,
    mock_get_settings: dict[str, list[SettingsData]],
    mock_installer_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the manual charge setting is available when using the installer login."""
    mock_get_settings.update(
        {
            "devices:local": [
                SettingsData(
                    min=None,
                    max=None,
                    default=None,
                    access="readwrite",
                    unit=None,
                    id="Battery:ManualCharge",
                    type="bool",
                )
            ]
        }
    )

    mock_installer_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_installer_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_is_registered("switch.scb_battery_manual_charge")


async def test_invalid_string_count_value(
    hass: HomeAssistant,
    mock_get_setting_values: dict[str, dict[str, str]],
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that an invalid string count value is handled correctly."""
    mock_get_setting_values["devices:local"].update({"Properties:StringCnt": "invalid"})

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # ensure no shadow management switch entities were registered
    assert [
        name
        for name, _ in entity_registry.entities.items()
        if name.startswith("switch.scb_shadow_management_dc_string_")
    ] == []


@pytest.mark.parametrize(
    ("shadow_mgmt", "string"),
    [
        ("0", (STATE_OFF, STATE_OFF)),
        ("1", (STATE_ON, STATE_OFF)),
        ("2", (STATE_OFF, STATE_ON)),
        ("3", (STATE_ON, STATE_ON)),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_shadow_management_switch_state(
    hass: HomeAssistant,
    mock_get_setting_values: dict[str, dict[str, str]],
    mock_config_entry: MockConfigEntry,
    shadow_mgmt: str,
    string: tuple[str, str],
) -> None:
    """Test that the state of the shadow management switch is correct."""
    mock_get_setting_values["devices:local"].update(
        {"Properties:StringCnt": "2", "Generator:ShadowMgmt:Enable": shadow_mgmt}
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=300))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("switch.scb_shadow_management_dc_string_1")
    assert state is not None
    assert state.state == string[0]

    state = hass.states.get("switch.scb_shadow_management_dc_string_2")
    assert state is not None
    assert state.state == string[1]


@pytest.mark.parametrize(
    ("initial_shadow_mgmt", "dc_string", "service", "shadow_mgmt"),
    [
        ("0", 1, SERVICE_TURN_ON, "1"),
        ("0", 2, SERVICE_TURN_ON, "2"),
        ("2", 1, SERVICE_TURN_ON, "3"),
        ("1", 2, SERVICE_TURN_ON, "3"),
        ("1", 1, SERVICE_TURN_OFF, "0"),
        ("2", 2, SERVICE_TURN_OFF, "0"),
        ("3", 1, SERVICE_TURN_OFF, "2"),
        ("3", 2, SERVICE_TURN_OFF, "1"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_shadow_management_switch_action(
    hass: HomeAssistant,
    mock_get_setting_values: dict[str, dict[str, str]],
    mock_plenticore_client: Mock,
    mock_config_entry: MockConfigEntry,
    initial_shadow_mgmt: str,
    dc_string: int,
    service: str,
    shadow_mgmt: str,
) -> None:
    """Test that the shadow management can be switch on/off."""
    mock_get_setting_values["devices:local"].update(
        {
            "Properties:StringCnt": "2",
            "Generator:ShadowMgmt:Enable": initial_shadow_mgmt,
        }
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=300))
    await hass.async_block_till_done(wait_background_tasks=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        target={ATTR_ENTITY_ID: f"switch.scb_shadow_management_dc_string_{dc_string}"},
        blocking=True,
    )

    mock_plenticore_client.set_setting_values.assert_called_with(
        "devices:local", {"Generator:ShadowMgmt:Enable": shadow_mgmt}
    )
