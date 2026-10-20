"""Tests for Imou siren platform."""

from unittest.mock import MagicMock

from pyimouapi.const import PARAM_SIREN_START, PARAM_SIREN_STOP
from pyimouapi.exceptions import ImouException, InvalidAppIdOrSecretException
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.siren import DOMAIN as SIREN_DOMAIN, SirenEntityFeature
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    EntityStateAttribute,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import create_online_device

SIREN_DEVICES = [
    create_online_device(
        "d1",
        "Device 1",
        button_keys=(PARAM_SIREN_START, PARAM_SIREN_STOP),
    ),
]


@pytest.mark.parametrize("platforms", [[Platform.SIREN]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [SIREN_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_siren_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot siren entities created when the device exposes siren controls."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("platforms", [[Platform.SIREN]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [SIREN_DEVICES], indirect=True)
@pytest.mark.parametrize(
    ("service", "button_type"),
    [
        (SERVICE_TURN_ON, PARAM_SIREN_START),
        (SERVICE_TURN_OFF, PARAM_SIREN_STOP),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_siren_service_calls_vendor_button(
    hass: HomeAssistant,
    mock_imou_ha_device_manager: MagicMock,
    service: str,
    button_type: str,
) -> None:
    """Turn on and turn off call the matching siren button on the device."""
    await hass.services.async_call(
        SIREN_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "siren.device_1_siren"},
        blocking=True,
    )

    mock_imou_ha_device_manager.async_press_button.assert_awaited_once()
    call = mock_imou_ha_device_manager.async_press_button.await_args
    assert call is not None
    assert call.args[1] == button_type
    assert call.args[2] == 0


@pytest.mark.parametrize("platforms", [[Platform.SIREN]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [SIREN_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_siren_service_propagates_api_error(
    hass: HomeAssistant,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """Imou API errors from the siren command surface to the service call."""
    mock_imou_ha_device_manager.async_press_button.side_effect = ImouException(
        "cloud failure"
    )

    with pytest.raises(HomeAssistantError, match="Imou rejected the siren change"):
        await hass.services.async_call(
            SIREN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "siren.device_1_siren"},
            blocking=True,
        )


@pytest.mark.parametrize("platforms", [[Platform.SIREN]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [SIREN_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_siren_invalid_auth_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """Rejected credentials while controlling the siren start reauthentication."""
    mock_imou_ha_device_manager.async_press_button.side_effect = (
        InvalidAppIdOrSecretException("fail")
    )

    with pytest.raises(
        HomeAssistantError, match="Imou rejected the App ID and App secret"
    ):
        await hass.services.async_call(
            SIREN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "siren.device_1_siren"},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.parametrize("platforms", [[Platform.SIREN]], indirect=True)
@pytest.mark.parametrize(
    ("imou_mock_devices", "expected_features", "service", "button_type"),
    [
        (
            [create_online_device("d1", "Device 1", button_keys=(PARAM_SIREN_START,))],
            SirenEntityFeature.TURN_ON,
            SERVICE_TURN_ON,
            PARAM_SIREN_START,
        ),
        (
            [create_online_device("d1", "Device 1", button_keys=(PARAM_SIREN_STOP,))],
            SirenEntityFeature.TURN_OFF,
            SERVICE_TURN_OFF,
            PARAM_SIREN_STOP,
        ),
    ],
    indirect=["imou_mock_devices"],
)
@pytest.mark.usefixtures("init_integration")
async def test_siren_partial_controls(
    hass: HomeAssistant,
    mock_imou_ha_device_manager: MagicMock,
    expected_features: SirenEntityFeature,
    service: str,
    button_type: str,
) -> None:
    """Devices with only start or only stop expose matching siren features."""
    state = hass.states.get("siren.device_1_siren")
    assert state is not None
    assert (
        state.attributes[EntityStateAttribute.SUPPORTED_FEATURES] == expected_features
    )

    await hass.services.async_call(
        SIREN_DOMAIN,
        service,
        {ATTR_ENTITY_ID: state.entity_id},
        blocking=True,
    )

    mock_imou_ha_device_manager.async_press_button.assert_awaited_once()
    call = mock_imou_ha_device_manager.async_press_button.await_args
    assert call is not None
    assert call.args[1] == button_type


@pytest.mark.parametrize("platforms", [[Platform.SIREN]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [SIREN_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_siren_toggle_alternates_start_and_stop(
    hass: HomeAssistant,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """Toggle turns the siren on and off using the matching cloud commands."""
    entity_id = "siren.device_1_siren"

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    call = mock_imou_ha_device_manager.async_press_button.await_args
    assert call is not None
    assert call.args[1] == PARAM_SIREN_START

    mock_imou_ha_device_manager.async_press_button.reset_mock()

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"
    call = mock_imou_ha_device_manager.async_press_button.await_args
    assert call is not None
    assert call.args[1] == PARAM_SIREN_STOP


@pytest.mark.parametrize("platforms", [[Platform.SIREN]], indirect=True)
@pytest.mark.parametrize(
    "imou_mock_devices",
    [[create_online_device("d1", "Device 1", button_keys=("not_a_siren",))]],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_setup_ignores_devices_without_siren(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Devices without siren start or stop buttons do not get a siren entity."""
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert entries == []
