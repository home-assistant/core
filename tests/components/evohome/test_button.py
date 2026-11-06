"""The tests for the button platform of evohome.

All evohome systems have a controller and at least one zone.
"""

from collections.abc import Callable
from unittest.mock import patch

from evohomeasync2 import exceptions as evo_exc
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import TEST_INSTALLS


@pytest.fixture
def reset_button_id(
    entity_registry: er.EntityRegistry,
    entity_id: Callable[[Platform, str], str],
) -> Callable[[str], str]:
    """Return a helper to lookup the entity_id of an entity's reset button."""

    def get_reset_button_id(parent_id: str) -> str:
        """Return the entity_id of the reset button of the parent entity."""

        parent = entity_registry.async_get(parent_id)
        assert parent is not None, f"Entity not found: {parent_id}"

        return entity_id(Platform.BUTTON, f"{parent.unique_id}_reset")

    return get_reset_button_id


@pytest.fixture
def system_button_id(ctl_id: str, reset_button_id: Callable[[str], str]) -> str:
    """Return the entity_id of the system reset button."""

    return reset_button_id(ctl_id)


@pytest.fixture
def dhw_button_id(dhw_id: str, reset_button_id: Callable[[str], str]) -> str:
    """Return the entity_id of the DHW reset button."""

    return reset_button_id(dhw_id)


@pytest.fixture
def zone_button_id(zone_id: str, reset_button_id: Callable[[str], str]) -> str:
    """Return the entity_id of the first zone's reset button."""

    return reset_button_id(zone_id)


@pytest.mark.parametrize("install", [*TEST_INSTALLS, "botched"])
@pytest.mark.usefixtures("evohome")
async def test_setup_platform(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that button entities are created after setup of evohome."""

    button_states = hass.states.async_all(BUTTON_DOMAIN)
    assert button_states

    for x in button_states:
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


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.usefixtures("evohome")
async def test_dhw_reset_button_press(
    hass: HomeAssistant,
    dhw_button_id: str,
) -> None:
    """Test SERVICE_PRESS on the DHW reset button."""

    with patch("evohomeasync2.hotwater.HotWater.reset") as mock_fcn:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: dhw_button_id},
            blocking=True,
        )

        mock_fcn.assert_awaited_once_with()


@pytest.mark.parametrize("install", ["default"])
@pytest.mark.usefixtures("evohome")
async def test_button_press_api_call_failed(
    hass: HomeAssistant,
    system_button_id: str,
) -> None:
    """Test SERVICE_PRESS raises HomeAssistantError if the vendor's API call fails."""

    with (
        patch(
            "evohomeasync2.control_system.ControlSystem.reset",
            side_effect=evo_exc.ApiCallFailedError("API call failed"),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: system_button_id},
            blocking=True,
        )

    assert exc_info.value.translation_key == "api_call_failed"
