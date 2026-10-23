"""Tests for Imou alarm control panel platform."""

from unittest.mock import MagicMock

from pyimouapi.const import PARAM_REF, PARAM_STATE, PARAM_SUPPORTED, PARAM_VALUE_TYPE
from pyimouapi.exceptions import ImouException, InvalidAppIdOrSecretException
from pyimouapi.ha_device import ImouHaDevice
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import create_online_device

from tests.common import MockConfigEntry, snapshot_platform

ALARM_PANEL = {
    PARAM_REF: "arm_mode",
    PARAM_STATE: "disarm",
    PARAM_SUPPORTED: ["home", "away", "disarm"],
    PARAM_VALUE_TYPE: "int",
}


def alarm_mock_devices() -> list[ImouHaDevice]:
    """Return a device list with an arming panel."""
    device = create_online_device("d1", "Gateway", button_keys=())
    device.alarm_control_panel = dict(ALARM_PANEL)
    return [device]


def alarm_panel_without_modes_devices() -> list[ImouHaDevice]:
    """Return a device whose panel lists no supported modes."""
    device = create_online_device("d1", "Gateway", button_keys=())
    device.alarm_control_panel = {**ALARM_PANEL, PARAM_SUPPORTED: []}
    return [device]


def alarm_panel_disarm_only_devices() -> list[ImouHaDevice]:
    """Return a device that supports disarm but no arm modes."""
    device = create_online_device("d1", "Gateway", button_keys=())
    device.alarm_control_panel = {**ALARM_PANEL, PARAM_SUPPORTED: ["disarm"]}
    return [device]


def alarm_panel_home_without_disarm_devices() -> list[ImouHaDevice]:
    """Return a device that supports home but not disarm."""
    device = create_online_device("d1", "Gateway", button_keys=())
    device.alarm_control_panel = {**ALARM_PANEL, PARAM_SUPPORTED: ["home"]}
    return [device]


@pytest.mark.parametrize("platforms", [[Platform.ALARM_CONTROL_PANEL]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [alarm_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_alarm_control_panel_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot alarm control panel entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("platforms", [[Platform.ALARM_CONTROL_PANEL]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [alarm_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_arm_home_via_service(
    hass: HomeAssistant,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """Arming home calls the vendor library."""
    entity_id = hass.states.async_all(ALARM_DOMAIN)[0].entity_id

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_HOME,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_imou_ha_device_manager.async_set_alarm_mode.assert_called_once()
    assert mock_imou_ha_device_manager.async_set_alarm_mode.call_args[0][1] == "home"


@pytest.mark.parametrize("platforms", [[Platform.ALARM_CONTROL_PANEL]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [alarm_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_arm_away_via_service(
    hass: HomeAssistant,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """Arming away calls the vendor library."""
    entity_id = hass.states.async_all(ALARM_DOMAIN)[0].entity_id

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_imou_ha_device_manager.async_set_alarm_mode.assert_called_once()
    assert mock_imou_ha_device_manager.async_set_alarm_mode.call_args[0][1] == "away"


@pytest.mark.parametrize("platforms", [[Platform.ALARM_CONTROL_PANEL]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [alarm_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_disarm_via_service(
    hass: HomeAssistant,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """Disarm calls the vendor library."""
    entity_id = hass.states.async_all(ALARM_DOMAIN)[0].entity_id

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_imou_ha_device_manager.async_set_alarm_mode.assert_called_once()
    assert mock_imou_ha_device_manager.async_set_alarm_mode.call_args[0][1] == "disarm"


@pytest.mark.parametrize("platforms", [[Platform.ALARM_CONTROL_PANEL]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [alarm_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_arm_home_propagates_api_error(
    hass: HomeAssistant,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """An API error while arming raises a translated error."""
    mock_imou_ha_device_manager.async_set_alarm_mode.side_effect = ImouException("fail")
    entity_id = hass.states.async_all(ALARM_DOMAIN)[0].entity_id

    with pytest.raises(HomeAssistantError, match="Imou rejected the arming change"):
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_ARM_HOME,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


@pytest.mark.parametrize("platforms", [[Platform.ALARM_CONTROL_PANEL]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [alarm_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_arm_home_invalid_auth_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """Rejected credentials while arming start reauthentication."""
    mock_imou_ha_device_manager.async_set_alarm_mode.side_effect = (
        InvalidAppIdOrSecretException("fail")
    )
    entity_id = hass.states.async_all(ALARM_DOMAIN)[0].entity_id

    with pytest.raises(
        HomeAssistantError, match="Imou rejected the App ID and App secret"
    ):
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_ARM_HOME,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.parametrize("platforms", [[Platform.ALARM_CONTROL_PANEL]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [alarm_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_alarm_state_from_device(
    hass: HomeAssistant,
) -> None:
    """Alarm state reflects the device panel mode."""
    entity_id = hass.states.async_all(ALARM_DOMAIN)[0].entity_id
    assert hass.states.get(entity_id).state == AlarmControlPanelState.DISARMED


@pytest.mark.parametrize("platforms", [[Platform.ALARM_CONTROL_PANEL]], indirect=True)
@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        alarm_panel_without_modes_devices,
        alarm_panel_disarm_only_devices,
        alarm_panel_home_without_disarm_devices,
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_skips_incomplete_alarm_panel(hass: HomeAssistant) -> None:
    """Devices without disarm and an arm mode do not get an arming entity."""
    assert not hass.states.async_all(ALARM_DOMAIN)
