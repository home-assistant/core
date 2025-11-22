"""Test for the switch platform entity of the energenie_mi_home component."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import mock_config_entry

from tests.common import snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_mihome_api: MagicMock,
) -> None:
    """Test that coordinator returns the data we expect after the first refresh."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.energenie_mi_home.coordinator.MiHomeAPI",
            return_value=mock_mihome_api,
        ),
        patch(
            "homeassistant.components.energenie_mi_home._PLATFORMS", [Platform.SWITCH]
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_switch_turn_on_off(
    hass: HomeAssistant,
    mock_mihome_api: MagicMock,
) -> None:
    """Test turning switch on and off."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.energenie_mi_home.coordinator.MiHomeAPI",
            return_value=mock_mihome_api,
        ),
        patch(
            "homeassistant.components.energenie_mi_home._PLATFORMS", [Platform.SWITCH]
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "switch.power_socket_1_switch"
    entity_id = "switch.power_socket_1_switch"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    # Turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_mihome_api.async_set_device_state.call_count == 1
    mock_mihome_api.async_set_device_state.assert_called_with("2", True)

    # Turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_mihome_api.async_set_device_state.call_count == 2
    mock_mihome_api.async_set_device_state.assert_called_with("2", False)
