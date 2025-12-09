"""Tests for Sure PetCare switches."""

from unittest.mock import AsyncMock, call, patch

import pytest
from surepy.const import BASE_RESOURCE, MESTART_RESOURCE
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.surepetcare.const import PROFILE_INDOOR, PROFILE_OUTDOOR
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import MOCK_API_DATA, MOCK_CAT_FLAP, MOCK_PET, MOCK_PET_FLAP, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def _mock_call_with_put_device_error(method, resource, json=None):
    """Mock API call that returns None on PUT (simulating 5XX error), succeeds on GET for refresh."""
    if method == "PUT" and "/tag/" in resource:
        return None
    if method == "GET" and resource == MESTART_RESOURCE:
        return {"data": MOCK_API_DATA}
    return None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switches(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    surepetcare,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch entities."""
    with patch("homeassistant.components.surepetcare.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry, surepetcare)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_turn_on(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on the switch (setting indoor mode)."""
    await setup_integration(hass, mock_config_entry, surepetcare)
    entity_id = "switch.pet_flap_pet_indoor_only_mode"

    # Verify initial state is off
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    surepetcare.call = AsyncMock(
        return_value={
            "data": {
                "id": MOCK_PET["tag_id"],
                "device_id": MOCK_PET_FLAP["id"],
                "profile": PROFILE_INDOOR,
            }
        }
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    surepetcare.call.assert_called_once_with(
        method="PUT",
        resource=f"{BASE_RESOURCE}/device/{MOCK_PET_FLAP['id']}/tag/{MOCK_PET['tag_id']}",
        json={"profile": PROFILE_INDOOR},
    )

    # Verify state changed to on
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_turn_off(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off the switch (setting outdoor mode)."""
    await setup_integration(hass, mock_config_entry, surepetcare)
    entity_id = "switch.cat_flap_pet_indoor_only_mode"

    # Verify initial state is on
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    surepetcare.call = AsyncMock(
        return_value={
            "data": {
                "id": MOCK_PET["tag_id"],
                "device_id": MOCK_CAT_FLAP["id"],
                "profile": PROFILE_OUTDOOR,
            }
        }
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    surepetcare.call.assert_called_once_with(
        method="PUT",
        resource=f"{BASE_RESOURCE}/device/{MOCK_CAT_FLAP['id']}/tag/{MOCK_PET['tag_id']}",
        json={"profile": PROFILE_OUTDOOR},
    )

    # Verify state changed to off
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_turn_on_already_on(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on a switch that's already on (no redundant API call)."""
    await setup_integration(hass, mock_config_entry, surepetcare)
    entity_id = "switch.cat_flap_pet_indoor_only_mode"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    surepetcare.call = AsyncMock()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    surepetcare.call.assert_not_called()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_turn_off_already_off(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off a switch that's already off (no redundant API call)."""
    await setup_integration(hass, mock_config_entry, surepetcare)
    entity_id = "switch.pet_flap_pet_indoor_only_mode"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    surepetcare.call = AsyncMock()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    surepetcare.call.assert_not_called()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_turn_on_api_error(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when API call fails during turn_on."""
    await setup_integration(hass, mock_config_entry, surepetcare)
    entity_id = "switch.pet_flap_pet_indoor_only_mode"

    # Verify initial state is off
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    surepetcare.call = AsyncMock(side_effect=_mock_call_with_put_device_error)

    with pytest.raises(
        HomeAssistantError, match="Failed to set Pet indoor mode on Pet Flap"
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_on",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    surepetcare.call.assert_has_calls(
        [
            call(
                method="PUT",
                resource=f"{BASE_RESOURCE}/device/{MOCK_PET_FLAP['id']}/tag/{MOCK_PET['tag_id']}",
                json={"profile": PROFILE_INDOOR},
            ),
            call(method="GET", resource=MESTART_RESOURCE),  # refresh after error
        ]
    )

    # Verify state remains off after error
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_turn_off_api_error(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when API call fails during turn_off."""
    await setup_integration(hass, mock_config_entry, surepetcare)
    entity_id = "switch.cat_flap_pet_indoor_only_mode"

    # Verify initial state is on
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    surepetcare.call = AsyncMock(side_effect=_mock_call_with_put_device_error)

    with pytest.raises(
        HomeAssistantError, match="Failed to set Pet outdoor mode on Cat Flap"
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_off",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    surepetcare.call.assert_has_calls(
        [
            call(
                method="PUT",
                resource=f"{BASE_RESOURCE}/device/{MOCK_CAT_FLAP['id']}/tag/{MOCK_PET['tag_id']}",
                json={"profile": PROFILE_OUTDOOR},
            ),
            call(method="GET", resource=MESTART_RESOURCE),  # refresh after error
        ]
    )

    # Verify state remains on after error
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_pet_removed_from_flap(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch becomes unavailable when pet is removed from flap configuration."""
    coordinator = await setup_integration(hass, mock_config_entry, surepetcare)
    entity_id = "switch.cat_flap_pet_indoor_only_mode"

    # Verify initial state is on
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    async def mock_call_without_pet(method, resource, json=None):
        if method == "GET" and resource == MESTART_RESOURCE:
            return {
                "data": {
                    "devices": [
                        {
                            **MOCK_CAT_FLAP,
                            "tags": [],  # Pet removed from flap configuration
                        },
                    ],
                    "pets": [MOCK_PET],
                }
            }
        return None

    surepetcare.call = AsyncMock(side_effect=mock_call_without_pet)

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify entity is now unavailable
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"
