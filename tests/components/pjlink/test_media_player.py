"""Test the pjlink media player platform."""

from datetime import timedelta
import socket
from unittest.mock import MagicMock, create_autospec, patch

import pypjlink
from pypjlink import MUTE_AUDIO
from pypjlink.projector import ProjectorError
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


@pytest.fixture(name="projector_from_address")
def projector_from_address():
    """Create pjlink Projector mock."""

    with patch("pypjlink.Projector.from_address") as from_address:
        constructor = create_autospec(pypjlink.Projector)
        constructor.__enter__.return_value = constructor
        from_address.return_value = constructor
        yield from_address


@pytest.fixture(name="mocked_projector")
def mocked_projector(projector_from_address: MagicMock) -> MagicMock:
    """Create pjlink Projector instance mock."""

    instance = projector_from_address.return_value

    instance.get_name.return_value = "Test"
    instance.get_power.return_value = "on"
    instance.get_mute.return_value = [0, True]
    instance.get_input.return_value = [0, 1]
    instance.get_inputs.return_value = (
        ("HDMI", 1),
        ("HDMI", 2),
        ("VGA", 1),
    )

    instance.__enter__.return_value = instance

    return instance


@pytest.mark.parametrize("side_effect", [socket.timeout, OSError])
async def test_offline_initialization(
    projector_from_address: MagicMock, hass: HomeAssistant, side_effect: type[Exception]
) -> None:
    """Test initialization of a device that is offline."""

    projector_from_address.side_effect = side_effect

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "unavailable"


async def test_initialization(
    projector_from_address: MagicMock, hass: HomeAssistant
) -> None:
    """Test a device that is available."""

    mocked_instance = projector_from_address.return_value

    mocked_instance.get_name.return_value = "Test"
    mocked_instance.get_inputs.return_value = (
        ("HDMI", 1),
        ("HDMI", 2),
        ("VGA", 1),
    )
    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "off"

    assert "source_list" in state.attributes
    source_list = state.attributes["source_list"]

    assert set(source_list) == {"HDMI 1", "HDMI 2", "VGA 1"}


@pytest.mark.parametrize("power_state", ["on", "warm-up"])
async def test_on_state_init(
    mocked_projector: MagicMock, hass: HomeAssistant, power_state: str
) -> None:
    """Test a device that is available."""

    mocked_projector.get_power.return_value = power_state
    mocked_projector.get_input.return_value = ("HDMI", 1)

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "on"

    assert state.attributes["source"] == "HDMI 1"


async def test_api_error(mocked_projector: MagicMock, hass: HomeAssistant) -> None:
    """Test invalid api responses."""

    mocked_projector.get_power.side_effect = KeyError("OK")

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "off"


async def test_update_unavailable(
    projector_from_address: MagicMock, hass: HomeAssistant
) -> None:
    """Test update to a device that is unavailable."""

    mocked_instance = projector_from_address.return_value

    mocked_instance.get_name.return_value = "Test"
    mocked_instance.get_inputs.return_value = (
        ("HDMI", 1),
        ("HDMI", 2),
        ("VGA", 1),
    )

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "off"

    projector_from_address.side_effect = socket.timeout
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("media_player.test")
    assert state.state == "unavailable"


async def test_unavailable_time(
    mocked_projector: MagicMock, hass: HomeAssistant
) -> None:
    """Test unavailable time projector error."""

    await setup_pjlink_entry(hass)

    state = hass.states.get("media_player.test")
    assert state.state == "on"
    assert state.attributes["source"] is not None
    assert state.attributes["is_volume_muted"] is not False

    mocked_projector.get_power.side_effect = ProjectorError("unavailable time")
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("media_player.test")
    assert state.state == "off"
    assert "source" not in state.attributes
    assert "is_volume_muted" not in state.attributes


async def test_turn_off(mocked_projector: MagicMock, hass: HomeAssistant) -> None:
    """Test turning off beamer."""

    await setup_pjlink_entry(hass)

    await hass.services.async_call(
        domain=media_player.DOMAIN,
        service="turn_off",
        service_data={ATTR_ENTITY_ID: "media_player.test"},
        blocking=True,
    )

    mocked_projector.set_power.assert_called_with("off")


async def test_turn_on(mocked_projector: MagicMock, hass: HomeAssistant) -> None:
    """Test turning on beamer."""

    await setup_pjlink_entry(hass)

    await hass.services.async_call(
        domain=media_player.DOMAIN,
        service="turn_on",
        service_data={ATTR_ENTITY_ID: "media_player.test"},
        blocking=True,
    )

    mocked_projector.set_power.assert_called_with("on")


async def test_mute(mocked_projector: MagicMock, hass: HomeAssistant) -> None:
    """Test muting beamer."""

    await setup_pjlink_entry(hass)

    await hass.services.async_call(
        domain=media_player.DOMAIN,
        service="volume_mute",
        service_data={ATTR_ENTITY_ID: "media_player.test", "is_volume_muted": True},
        blocking=True,
    )

    mocked_projector.set_mute.assert_called_with(MUTE_AUDIO, True)


async def test_unmute(mocked_projector: MagicMock, hass: HomeAssistant) -> None:
    """Test unmuting beamer."""

    await setup_pjlink_entry(hass)

    await hass.services.async_call(
        domain=media_player.DOMAIN,
        service="volume_mute",
        service_data={ATTR_ENTITY_ID: "media_player.test", "is_volume_muted": False},
        blocking=True,
    )

    mocked_projector.set_mute.assert_called_with(MUTE_AUDIO, False)


async def test_select_source(mocked_projector: MagicMock, hass: HomeAssistant) -> None:
    """Test selecting source."""

    await setup_pjlink_entry(hass)

    await hass.services.async_call(
        domain=media_player.DOMAIN,
        service="select_source",
        service_data={ATTR_ENTITY_ID: "media_player.test", "source": "VGA 1"},
        blocking=True,
    )

    mocked_projector.set_input.assert_called_with("VGA", 1)


async def test_yaml_import(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mocked_projector: MagicMock,
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
        (RuntimeError, "invalid_auth"),
        (TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_failed_yaml_import(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mocked_projector: MagicMock,
    caplog: pytest.LogCaptureFixture,
    side_effect: type[Exception],
    error_str: str,
) -> None:
    """Test a YAML media player is imported and becomes an operational config entry."""

    with patch("pypjlink.Projector.from_address", side_effect=side_effect):
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
