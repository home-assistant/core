"""Test BMW buttons."""

from unittest.mock import AsyncMock, patch

from bimmer_connected.models import MyBMWRemoteServiceError
from bimmer_connected.vehicle.remote_services import RemoteServices
import pytest
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import (
    REMOTE_SERVICE_EXC_TRANSLATION,
    check_remote_service_call,
    setup_mocked_integration,
)

from tests.common import snapshot_platform


@pytest.mark.usefixtures("bmw_fixture")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_state_attrs(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test button options and values."""

    # Setup component
    with patch(
        "homeassistant.components.bmw_connected_drive.PLATFORMS",
        [Platform.BUTTON],
    ):
        mock_config_entry = await setup_mocked_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "remote_service"),
    [
        ("button.i4_edrive40_flash_lights", "light-flash"),
        ("button.i4_edrive40_sound_horn", "horn-blow"),
    ],
)
async def test_service_call_success(
    hass: HomeAssistant,
    entity_id: str,
    remote_service: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test successful button press."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Test
    await hass.services.async_call(
        "button",
        "press",
        blocking=True,
        target={"entity_id": entity_id},
    )
    check_remote_service_call(bmw_fixture, remote_service)


@pytest.mark.usefixtures("bmw_fixture")
async def test_service_call_fail(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test failed button press."""

    # Setup component
    assert await setup_mocked_integration(hass)
    entity_id = "switch.i4_edrive40_climate"
    old_value = hass.states.get(entity_id).state

    # Setup exception
    monkeypatch.setattr(
        RemoteServices,
        "trigger_remote_service",
        AsyncMock(
            side_effect=MyBMWRemoteServiceError("HTTPStatusError: 502 Bad Gateway")
        ),
    )

    # Test
    with pytest.raises(HomeAssistantError, match=REMOTE_SERVICE_EXC_TRANSLATION):
        await hass.services.async_call(
            "button",
            "press",
            blocking=True,
            target={"entity_id": "button.i4_edrive40_activate_air_conditioning"},
        )
    assert hass.states.get(entity_id).state == old_value


@pytest.mark.parametrize(
    (
        "entity_id",
        "state_entity_id",
        "new_value",
        "old_value",
        "remote_service",
        "remote_service_params",
    ),
    [
        (
            "button.i4_edrive40_activate_air_conditioning",
            "switch.i4_edrive40_climate",
            "on",
            "off",
            "climate-now",
            {"action": "START"},
        ),
        (
            "button.i4_edrive40_deactivate_air_conditioning",
            "switch.i4_edrive40_climate",
            "off",
            "on",
            "climate-now",
            {"action": "STOP"},
        ),
        (
            "button.i4_edrive40_find_vehicle",
            "device_tracker.i4_edrive40",
            "not_home",
            "home",
            "vehicle-finder",
            {},
        ),
    ],
)
async def test_service_call_success_state_change(
    hass: HomeAssistant,
    entity_id: str,
    state_entity_id: str,
    new_value: str,
    old_value: str,
    remote_service: str,
    remote_service_params: dict,
    bmw_fixture: respx.Router,
) -> None:
    """Test successful button press with state change."""

    # Setup component
    assert await setup_mocked_integration(hass)
    hass.states.async_set(state_entity_id, old_value)
    assert hass.states.get(state_entity_id).state == old_value

    # Test
    await hass.services.async_call(
        "button",
        "press",
        blocking=True,
        target={"entity_id": entity_id},
    )
    check_remote_service_call(bmw_fixture, remote_service, remote_service_params)
    assert hass.states.get(state_entity_id).state == new_value


@pytest.mark.parametrize(
    ("entity_id", "state_entity_id", "new_attrs", "old_attrs"),
    [
        (
            "button.i4_edrive40_find_vehicle",
            "device_tracker.i4_edrive40",
            {"latitude": 12.345, "longitude": 34.5678, "direction": 121},
            {"latitude": 48.177334, "longitude": 11.556274, "direction": 180},
        ),
    ],
)
async def test_service_call_success_attr_change(
    hass: HomeAssistant,
    entity_id: str,
    state_entity_id: str,
    new_attrs: dict,
    old_attrs: dict,
    bmw_fixture: respx.Router,
) -> None:
    """Test successful button press with attribute change."""

    # Setup component
    assert await setup_mocked_integration(hass)

    assert {
        k: v
        for k, v in hass.states.get(state_entity_id).attributes.items()
        if k in old_attrs
    } == old_attrs

    # Test
    await hass.services.async_call(
        "button",
        "press",
        blocking=True,
        target={"entity_id": entity_id},
    )
    check_remote_service_call(bmw_fixture)
    assert {
        k: v
        for k, v in hass.states.get(state_entity_id).attributes.items()
        if k in new_attrs
    } == new_attrs
