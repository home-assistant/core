"""Test the pjlink media player platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from aiopjlink import PJLinkERR3, PJLinkNoConnection, PJLinkPassword, Power, Sources
import pytest

from homeassistant.components import media_player
from homeassistant.components.pjlink.const import (
    CONF_ENCODING,
    DEFAULT_ENCODING,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_PORT,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import setup_pjlink_entry

from tests.common import async_fire_time_changed

_EXAMPLE_YAML_CONFIG = {
    Platform.MEDIA_PLAYER: [
        {
            CONF_PLATFORM: DOMAIN,
            CONF_HOST: "1.1.1.1",
            CONF_PORT: DEFAULT_PORT,
            CONF_PASSWORD: "test-password",
            CONF_ENCODING: DEFAULT_ENCODING,
        }
    ]
}


async def test_offline_initialization(
    mock_pjlink: MagicMock, hass: HomeAssistant
) -> None:
    """Test initialization of a device that is offline."""

    mock_pjlink.power.get.side_effect = PJLinkNoConnection

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "unavailable"


async def test_initialization(mock_pjlink: MagicMock, hass: HomeAssistant) -> None:
    """Test a device that is available."""

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "off"

    assert "source_list" in state.attributes
    source_list = state.attributes["source_list"]

    assert set(source_list) == {"DIGITAL 1", "DIGITAL 2", "VIDEO 1"}


@pytest.mark.parametrize("power_state", [Power.State.ON, Power.State.WARMING])
async def test_on_state_init(
    mock_pjlink: MagicMock, hass: HomeAssistant, power_state: str
) -> None:
    """Test a device that is available."""

    mock_pjlink.power.get.return_value = power_state

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "on"

    assert state.attributes["source"] == "DIGITAL 1"


async def test_api_error(mock_pjlink: MagicMock, hass: HomeAssistant) -> None:
    """Test invalid api responses."""

    mock_pjlink.power.get.return_value = Power.State.ON
    mock_pjlink.power.get.side_effect = KeyError("OK")

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "off"


async def test_update_unavailable(mock_pjlink: MagicMock, hass: HomeAssistant) -> None:
    """Test update to a device that is unavailable."""

    mock_pjlink.info.projector_name.return_value = "Test"
    mock_pjlink.sources.available.return_value = [
        (Sources.Mode.DIGITAL, 1),
        (Sources.Mode.DIGITAL, 2),
        (Sources.Mode.VIDEO, 1),
    ]

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "off"

    mock_pjlink.power.get.side_effect = PJLinkNoConnection
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("media_player.test")
    assert state.state == "unavailable"


async def test_unavailable_time(mock_pjlink: MagicMock, hass: HomeAssistant) -> None:
    """Test unavailable time projector error."""

    mock_pjlink.power.get.return_value = Power.State.ON

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "on"
    assert state.attributes["source"] is not None
    assert state.attributes["is_volume_muted"] is not False

    mock_pjlink.power.get.side_effect = PJLinkERR3
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("media_player.test")
    assert state.state == "off"
    assert "source" not in state.attributes
    assert "is_volume_muted" not in state.attributes


async def test_turn_off(mock_pjlink: MagicMock, hass: HomeAssistant) -> None:
    """Test turning off beamer."""

    await setup_pjlink_entry(hass)

    await hass.services.async_call(
        domain=media_player.DOMAIN,
        service="turn_off",
        service_data={ATTR_ENTITY_ID: "media_player.test"},
        blocking=True,
    )

    mock_pjlink.power.turn_off.assert_awaited()


async def test_turn_on(mock_pjlink: MagicMock, hass: HomeAssistant) -> None:
    """Test turning on beamer."""

    await setup_pjlink_entry(hass)

    await hass.services.async_call(
        domain=media_player.DOMAIN,
        service="turn_on",
        service_data={ATTR_ENTITY_ID: "media_player.test"},
        blocking=True,
    )

    mock_pjlink.power.turn_on.assert_awaited()


async def test_mute(mock_pjlink: MagicMock, hass: HomeAssistant) -> None:
    """Test muting beamer."""

    await setup_pjlink_entry(hass)

    await hass.services.async_call(
        domain=media_player.DOMAIN,
        service="volume_mute",
        service_data={ATTR_ENTITY_ID: "media_player.test", "is_volume_muted": True},
        blocking=True,
    )

    mock_pjlink.mute.audio.assert_awaited_with(True)


async def test_unmute(mock_pjlink: MagicMock, hass: HomeAssistant) -> None:
    """Test unmuting beamer."""

    await setup_pjlink_entry(hass)

    await hass.services.async_call(
        domain=media_player.DOMAIN,
        service="volume_mute",
        service_data={ATTR_ENTITY_ID: "media_player.test", "is_volume_muted": False},
        blocking=True,
    )

    mock_pjlink.mute.audio.assert_awaited_with(False)


async def test_select_source(mock_pjlink: MagicMock, hass: HomeAssistant) -> None:
    """Test selecting source."""

    await setup_pjlink_entry(hass)

    await hass.services.async_call(
        domain=media_player.DOMAIN,
        service="select_source",
        service_data={ATTR_ENTITY_ID: "media_player.test", "source": "VIDEO 1"},
        blocking=True,
    )

    mock_pjlink.sources.set.assert_awaited_with(Sources.Mode.VIDEO, 1)


async def test_yaml_import(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_pjlink: MagicMock,
) -> None:
    """Test a YAML media player is imported and becomes an operational config entry."""
    assert await async_setup_component(
        hass, Platform.MEDIA_PLAYER, _EXAMPLE_YAML_CONFIG
    )
    await hass.async_block_till_done()

    # Verify the config entry was created
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    # Verify a warning was issued about YAML deprecation
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize(
    ("side_effect", "error_str"),
    [
        (PJLinkPassword, "invalid_auth"),
        (PJLinkNoConnection, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_failed_yaml_import(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_pjlink: MagicMock,
    side_effect: type[Exception],
    error_str: str,
) -> None:
    """Test a YAML media player is imported and becomes an operational config entry."""

    mock_pjlink.info.projector_name.side_effect = side_effect
    assert await async_setup_component(
        hass, Platform.MEDIA_PLAYER, _EXAMPLE_YAML_CONFIG
    )
    await hass.async_block_till_done()

    # Verify the config entry was not created
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 0

    # verify no flows still in progress
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0

    # Verify a warning was issued about YAML not being imported
    assert issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{error_str}"
    )
