"""Test the Sharp Aquos TV media player."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.aquostv.const import CONF_POWER_ON_ENABLED, DOMAIN
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
    SERVICE_VOLUME_SET,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PLATFORM,
    SERVICE_TURN_OFF,
    STATE_UNAVAILABLE,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import HOST

ENTITY_ID = "media_player.sharp_aquos_tv"


async def test_state_and_actions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the entity state and that actions reach the TV."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.ON
    assert state.attributes["source"] == "HDMI_IN_1"
    assert state.attributes["volume_level"] == 0.3
    assert entity_registry.async_get(ENTITY_ID).unique_id == mock_config_entry.entry_id

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "HDMI_IN_2"},
        blocking=True,
    )
    mock_tv.input.assert_any_call(2)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_tv.power.assert_any_call(0)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 1.0},
        blocking=True,
    )
    mock_tv.volume.assert_any_call(100)


@pytest.mark.parametrize(
    ("options", "can_turn_on", "network_power_on"),
    [
        pytest.param({}, True, 2, id="default"),
        pytest.param({CONF_POWER_ON_ENABLED: True}, True, 2, id="enabled"),
        pytest.param({CONF_POWER_ON_ENABLED: False}, False, 0, id="disabled"),
    ],
)
async def test_power_on_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
    options: dict[str, bool],
    can_turn_on: bool,
    network_power_on: int,
) -> None:
    """Test power on defaults to enabled and respects the imported option."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options=options)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    features = hass.states.get(ENTITY_ID).attributes["supported_features"]
    assert bool(features & MediaPlayerEntityFeature.TURN_ON) is can_turn_on
    mock_tv.power_on_command_settings.assert_any_call(network_power_on)


@pytest.mark.usefixtures("mock_tv")
async def test_unload(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test unloading the entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_tv")
async def test_yaml_import(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the YAML platform is imported and a deprecation issue is raised."""
    assert await async_setup_component(
        hass,
        MEDIA_PLAYER_DOMAIN,
        {MEDIA_PLAYER_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_HOST: HOST}},
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].title == "Sharp Aquos TV"
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_tv_off(hass: HomeAssistant, mock_tv: MagicMock) -> None:
    """Test an imported TV that is unreachable is still set up, as off."""
    mock_tv.power.side_effect = OSError
    assert await async_setup_component(
        hass,
        MEDIA_PLAYER_DOMAIN,
        {MEDIA_PLAYER_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_HOST: HOST}},
    )
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.OFF
