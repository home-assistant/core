"""Test BMW selects."""
from bimmer_connected.vehicle.remote_services import RemoteServices
import pytest

from homeassistant.core import HomeAssistant

from . import setup_mocked_integration

FIXTURE_AC_LIMITS = [
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "20",
    "32",
]
FIXTURE_SOC = [
    "20",
    "25",
    "30",
    "35",
    "40",
    "45",
    "50",
    "55",
    "60",
    "65",
    "70",
    "75",
    "80",
    "85",
    "90",
    "95",
    "100",
]
FIXTURE_CHARGING_MODE = ["IMMEDIATE_CHARGING", "DELAYED_CHARGING"]


@pytest.mark.parametrize(
    ("entity_id", "exists", "options", "value", "unit_of_measurement"),
    [
        ("select.i3_rex_ac_charging_limit", False, [], "", ""),
        ("select.i3_rex_target_soc", False, [], "", ""),
        (
            "select.i3_rex_charging_mode",
            True,
            FIXTURE_CHARGING_MODE,
            "DELAYED_CHARGING",
            None,
        ),
        (
            "select.i4_edrive40_ac_charging_limit",
            True,
            FIXTURE_AC_LIMITS,
            "16",
            "A",
        ),
        ("select.i4_edrive40_target_soc", True, FIXTURE_SOC, "80", "%"),
        (
            "select.i4_edrive40_charging_mode",
            True,
            FIXTURE_CHARGING_MODE,
            "IMMEDIATE_CHARGING",
            None,
        ),
    ],
)
async def test_entity_state_attrs(
    hass: HomeAssistant,
    entity_id: str,
    exists: bool,
    options: list[str],
    value: str,
    unit_of_measurement: str,
    bmw_fixture,
) -> None:
    """Test select options and values.."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Test
    entity = hass.states.get(entity_id)
    if exists:
        assert entity.attributes.get("options") == options
        assert entity.state == value
        assert entity.attributes.get("unit_of_measurement") == unit_of_measurement
    else:
        assert entity is None


@pytest.mark.parametrize(
    ("entity_id", "value", "exception"),
    [
        ("select.i3_rex_charging_mode", "IMMEDIATE_CHARGING", False),
        ("select.i4_edrive40_ac_charging_limit", "16", False),
        ("select.i4_edrive40_ac_charging_limit", "17", True),
        ("select.i4_edrive40_target_soc", "80", False),
        ("select.i4_edrive40_target_soc", "81", True),
        ("select.i4_edrive40_charging_mode", "DELAYED_CHARGING", False),
    ],
)
async def test_update_triggers(
    hass: HomeAssistant,
    entity_id: str,
    value: str,
    exception: bool,
    bmw_fixture,
) -> None:
    """Test select options and values.."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Test
    if exception:
        with pytest.raises(ValueError):
            await hass.services.async_call(
                "select",
                "select_option",
                service_data={"option": value},
                blocking=True,
                target={"entity_id": entity_id},
            )
        assert RemoteServices.trigger_remote_service.call_count == 0
    else:
        await hass.services.async_call(
            "select",
            "select_option",
            service_data={"option": value},
            blocking=True,
            target={"entity_id": entity_id},
        )
        assert RemoteServices.trigger_remote_service.call_count == 1
