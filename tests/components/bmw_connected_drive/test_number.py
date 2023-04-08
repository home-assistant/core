"""Test BMW numbers."""
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
    """Test number options and values.."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Get all number entities
    assert hass.states.async_all("number") == snapshot


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        ("number.i4_edrive40_target_soc", "80"),
    ],
)
async def test_update_triggers_success(
    hass: HomeAssistant,
    entity_id: str,
    value: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test allowed values for number inputs."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Test
    await hass.services.async_call(
        "number",
        "set_value",
        service_data={"value": value},
        blocking=True,
        target={"entity_id": entity_id},
    )
    assert RemoteServices.trigger_remote_service.call_count == 1


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        ("number.i4_edrive40_target_soc", "81"),
    ],
)
async def test_update_triggers_fail(
    hass: HomeAssistant,
    entity_id: str,
    value: str,
    bmw_fixture: respx.Router,
) -> None:
    """Test not allowed values for number inputs."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Test
    with pytest.raises(ValueError):
        await hass.services.async_call(
            "number",
            "set_value",
            service_data={"value": value},
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert RemoteServices.trigger_remote_service.call_count == 0
