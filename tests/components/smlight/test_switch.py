"""Tests for the SMLIGHT switch platform."""

from collections.abc import Callable
from unittest.mock import MagicMock

from pysmlight import SettingsEvent
from pysmlight.const import Settings
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = [
    pytest.mark.usefixtures(
        "mock_smlight_client",
    )
]


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.SWITCH]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of SMLIGHT switches."""
    entry = await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_disabled_by_default_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test vpn enabled switch is disabled by default ."""
    await setup_integration(hass, mock_config_entry)
    for entity in ("vpn_enabled", "auto_zigbee_update"):
        assert not hass.states.get(f"switch.mock_title_{entity}")

        assert (entry := entity_registry.async_get(f"switch.mock_title_{entity}"))
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity", "setting"),
    [
        ("disable_leds", Settings.DISABLE_LEDS),
        ("led_night_mode", Settings.NIGHT_MODE),
        ("auto_zigbee_update", Settings.ZB_AUTOUPDATE),
        ("vpn_enabled", Settings.ENABLE_VPN),
    ],
)
async def test_switches(
    hass: HomeAssistant,
    entity: str,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    setting: Settings,
) -> None:
    """Test the SMLIGHT switches."""
    await setup_integration(hass, mock_config_entry)

    _page, _toggle = setting.value

    entity_id = f"switch.mock_title_{entity}"
    state = hass.states.get(entity_id)
    assert state is not None

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mock_smlight_client.set_toggle.mock_calls) == 1
    mock_smlight_client.set_toggle.assert_called_once_with(_page, _toggle, True)

    event_function: Callable[[SettingsEvent], None] = next(
        (
            call_args[0][1]
            for call_args in mock_smlight_client.sse.register_settings_cb.call_args_list
            if setting == call_args[0][0]
        ),
        None,
    )

    async def _call_event_function(state: bool = True):
        event_function(SettingsEvent(page=_page, origin="ha", setting={_toggle: state}))
        await hass.async_block_till_done()

    await _call_event_function(state=True)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mock_smlight_client.set_toggle.mock_calls) == 2
    mock_smlight_client.set_toggle.assert_called_with(_page, _toggle, False)

    await _call_event_function(state=False)

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
