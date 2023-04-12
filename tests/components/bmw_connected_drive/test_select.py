"""Test BMW selects."""
from bimmer_connected.vehicle.remote_services import RemoteServices
import pytest
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_mocked_integration


async def test_entity_state_attrs(
    hass: HomeAssistant,
    bmw_fixture: respx.Router,
    snapshot: SnapshotAssertion,
) -> None:
    """Test select options and values.."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Get all select entities
    assert hass.states.async_all("select") == snapshot


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        ("select.i3_rex_charging_mode", "IMMEDIATE_CHARGING"),
        ("select.i4_edrive40_ac_charging_limit", "16"),
        ("select.i4_edrive40_target_soc", "80"),
        ("select.i4_edrive40_charging_mode", "DELAYED_CHARGING"),
    ],
)
async def test_update_triggers_success(
    hass: HomeAssistant,
    entity_id: str,
    value: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test allowed values for select inputs."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Test
    await hass.services.async_call(
        "select",
        "select_option",
        service_data={"option": value},
        blocking=True,
        target={"entity_id": entity_id},
    )
    assert RemoteServices.trigger_remote_service.call_count == 1


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        ("select.i4_edrive40_ac_charging_limit", "17"),
        ("select.i4_edrive40_target_soc", "81"),
    ],
)
async def test_update_triggers_fail(
    hass: HomeAssistant,
    entity_id: str,
    value: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test not allowed values for select inputs."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Test
    with pytest.raises(ValueError):
        await hass.services.async_call(
            "select",
            "select_option",
            service_data={"option": value},
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert RemoteServices.trigger_remote_service.call_count == 0
