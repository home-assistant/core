"""Tests for the Nobø Ecohub switch platform."""

from unittest.mock import MagicMock

from pynobo import PynoboError, nobo
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nobo_hub.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import entity_unique_ids, fire_hub_update
from .conftest import SERIAL

from tests.common import MockConfigEntry, snapshot_platform

SWITCH_ENTITY = "switch.living_room_living_room_disable_global_overrides"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only set up the switch platform for these tests."""
    return [Platform.SWITCH]


@pytest.mark.usefixtures("init_integration")
async def test_switch_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """All switch entities match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "expected_override_allowed"),
    [
        (SERVICE_TURN_ON, nobo.API.OVERRIDE_NOT_ALLOWED),
        (SERVICE_TURN_OFF, nobo.API.OVERRIDE_ALLOWED),
    ],
    ids=["turn_on_disables", "turn_off_enables"],
)
@pytest.mark.usefixtures("init_integration")
async def test_switch_updates_zone(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    service: str,
    expected_override_allowed: str,
) -> None:
    """Toggling the switch updates the zone's override_allowed setting."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: SWITCH_ENTITY},
        blocking=True,
    )
    mock_nobo_hub.async_update_zone.assert_called_once_with(
        "1", override_allowed=expected_override_allowed
    )


@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
@pytest.mark.usefixtures("init_integration")
async def test_switch_wraps_library_error(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    service: str,
) -> None:
    """Library errors during toggling are raised as HomeAssistantError."""
    mock_nobo_hub.async_update_zone.side_effect = PynoboError("boom")
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: SWITCH_ENTITY},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "set_disable_global_override_failed"


@pytest.mark.usefixtures("init_integration")
async def test_switch_push_update(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """Pushed hub updates refresh the switch state."""
    assert hass.states.get(SWITCH_ENTITY).state == STATE_OFF

    mock_nobo_hub.zones["1"]["override_allowed"] = nobo.API.OVERRIDE_NOT_ALLOWED
    await fire_hub_update(hass, mock_nobo_hub)
    assert hass.states.get(SWITCH_ENTITY).state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_zone_removed_removes_switch(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """Removing a zone via the Nobø app removes its switch."""
    mock_nobo_hub.zones.pop("1")
    await fire_hub_update(hass, mock_nobo_hub)
    assert hass.states.get(SWITCH_ENTITY) is None


@pytest.mark.usefixtures("init_integration")
async def test_new_zone_adds_switch(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A zone added on the hub at runtime creates a switch."""
    entry_id = mock_config_entry.entry_id
    unique_id = f"{SERIAL}:2:disable_global_override"
    assert unique_id not in entity_unique_ids(entity_registry, entry_id)

    mock_nobo_hub.zones["2"] = {
        "zone_id": "2",
        "name": "Bedroom",
        "week_profile_id": "0",
        "temp_comfort_c": "22",
        "temp_eco_c": "18",
        "override_allowed": "1",
    }
    await fire_hub_update(hass, mock_nobo_hub)

    assert unique_id in entity_unique_ids(entity_registry, entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_readded_zone_reappears_switch(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A zone removed and re-added under the same id (the hub reuses ids) restores its switch."""
    entry_id = mock_config_entry.entry_id
    unique_id = f"{SERIAL}:2:disable_global_override"
    zone = {
        "zone_id": "2",
        "name": "Bedroom",
        "week_profile_id": "0",
        "temp_comfort_c": "22",
        "temp_eco_c": "18",
        "override_allowed": "1",
    }

    mock_nobo_hub.zones["2"] = zone
    await fire_hub_update(hass, mock_nobo_hub)
    assert unique_id in entity_unique_ids(entity_registry, entry_id)

    del mock_nobo_hub.zones["2"]
    await fire_hub_update(hass, mock_nobo_hub)
    assert unique_id not in entity_unique_ids(entity_registry, entry_id)

    mock_nobo_hub.zones["2"] = zone
    await fire_hub_update(hass, mock_nobo_hub)
    assert unique_id in entity_unique_ids(entity_registry, entry_id)
