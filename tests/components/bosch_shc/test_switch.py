"""Tests for the Bosch SHC switch platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from boschshcpy import ThermostatService
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    light_switch_bsm_device,
    micromodule_relay_device,
    setup_integration,
    thermostat_device,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the switch platform."""
    with patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.parametrize(
    "device_buckets",
    [{"thermostats": [thermostat_device(child_lock=ThermostatService.State.OFF)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_child_lock(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A thermostat's enum-based child lock is exposed and controllable."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.thermostats[0]

    state = hass.states.get("switch.thermostat_child_lock")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.thermostat_child_lock"},
        blocking=True,
    )
    assert device.child_lock is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.thermostat_child_lock"},
        blocking=True,
    )
    assert device.child_lock is False


@pytest.mark.parametrize(
    "device_buckets",
    [{"micromodule_relays": [micromodule_relay_device(child_lock=False)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_micromodule_relay_child_lock(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A ChildProtection device's bool-based child lock is exposed and controllable."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.micromodule_relays[0]

    state = hass.states.get("switch.relay_child_lock")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.relay_child_lock"},
        blocking=True,
    )
    assert device.child_lock is True


@pytest.mark.parametrize(
    "device_buckets",
    [{"light_switches_bsm": [light_switch_bsm_device(child_lock=False)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_light_switch_bsm_child_lock_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A BSM light switch's primary switch and child-lock switch use distinct unique_ids."""
    await setup_integration(hass, mock_config_entry)

    lightswitch_entry = entity_registry.async_get("switch.light_switch")
    child_lock_entry = entity_registry.async_get("switch.light_switch_child_lock")
    assert lightswitch_entry is not None
    assert child_lock_entry is not None
    assert lightswitch_entry.unique_id != child_lock_entry.unique_id
