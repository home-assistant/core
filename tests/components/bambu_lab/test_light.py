"""Tests for the Bambu Lab light platform."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

from aiobambulab import BambuLabConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import push_update, setup_integration

CHAMBER_LIGHT = "light.x1_carbon_chamber_light"


@pytest.mark.usefixtures("mock_bambu_lab_client")
async def test_lights(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the light of a printer."""
    with patch("homeassistant.components.bambu_lab._PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_no_chamber_light(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a printer that does not report a chamber light has no light."""
    mock_bambu_lab_client.state = replace(
        mock_bambu_lab_client.state, chamber_light_on=None
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(CHAMBER_LIGHT) is None


@pytest.mark.parametrize(
    ("service", "on"),
    [
        pytest.param(SERVICE_TURN_ON, True, id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, False, id="turn_off"),
    ],
)
async def test_turn_on_and_off(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    on: bool,
) -> None:
    """Test turning the light on and off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN, service, {ATTR_ENTITY_ID: CHAMBER_LIGHT}, blocking=True
    )

    mock_bambu_lab_client.set_chamber_light.assert_awaited_once_with(on=on)


async def test_update(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light follows what the printer pushes."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(CHAMBER_LIGHT).state == STATE_ON

    mock_bambu_lab_client.state = replace(
        mock_bambu_lab_client.state, chamber_light_on=False
    )
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(CHAMBER_LIGHT).state == STATE_OFF


async def test_command_error(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an error is raised when the command cannot be sent."""
    await setup_integration(hass, mock_config_entry)
    mock_bambu_lab_client.set_chamber_light.side_effect = BambuLabConnectionError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: CHAMBER_LIGHT},
            blocking=True,
        )

    assert exc_info.value.translation_key == "command_error"
