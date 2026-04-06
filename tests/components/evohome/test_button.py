"""The tests for the button platform of evohome.

All evohome systems have a controller and at least one zone.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from evohomeasync2 import EvohomeClient
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.evohome import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .const import TEST_INSTALLS


@pytest.fixture
def system_button_id(evohome: MagicMock) -> str:
    """Return the entity_id of the system reset button."""

    evo: EvohomeClient = evohome.return_value
    ctl = evo.tcs

    return f"{BUTTON_DOMAIN}.{DOMAIN}_{ctl.id}_reset_system"


@pytest.fixture
def zone_button_id(evohome: MagicMock) -> str:
    """Return the entity_id of the first zone's reset button."""

    evo: EvohomeClient = evohome.return_value
    zone = evo.tcs.zones[0]

    if zone.id == zone.tcs.id:
        return f"{BUTTON_DOMAIN}.{DOMAIN}_{zone.id}z_reset_override"

    return f"{BUTTON_DOMAIN}.{DOMAIN}_{zone.id}_reset_override"


@pytest.mark.parametrize("install", [*TEST_INSTALLS, "botched"])
@pytest.mark.usefixtures("evohome")
async def test_setup_platform(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that button entities are created after setup of evohome."""

    for x in hass.states.async_all(BUTTON_DOMAIN):
        assert x == snapshot(name=f"{x.entity_id}-state")


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.usefixtures("evohome")
async def test_system_reset_button_press(
    hass: HomeAssistant,
    system_button_id: str,
) -> None:
    """Test SERVICE_PRESS on the system reset button."""

    with patch("evohomeasync2.control_system.ControlSystem.reset") as mock_fcn:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: system_button_id},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.usefixtures("evohome")
async def test_zone_reset_button_press(
    hass: HomeAssistant,
    zone_button_id: str,
) -> None:
    """Test SERVICE_PRESS on a zone reset button."""

    with patch("evohomeasync2.zone.Zone.reset") as mock_fcn:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: zone_button_id},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()
