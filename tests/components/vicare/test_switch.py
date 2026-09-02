"""Test ViCare switch."""

from unittest.mock import patch

import pytest
from PyViCare.PyViCareUtils import (
    PyViCareCommandError,
    PyViCareNotSupportedFeatureError,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import MODULE, setup_integration
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry, snapshot_platform

VENTILATION_FIXTURES: list[Fixture] = [
    Fixture({"type:ventilation"}, "vicare/ViAir300F.json"),
    Fixture({"type:ventilation"}, "vicare/VitoPure.json"),
    Fixture({"type:heatpump"}, "vicare/Vitocal222G_Vitovent300W.json"),
]


async def setup_switch_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vicare: MockPyViCare,
) -> None:
    """Set up the switch platform with the given mocked devices."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=mock_vicare.as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.SWITCH]),
    ):
        await setup_integration(hass, mock_config_entry)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_switch_platform(
        hass, mock_config_entry, MockPyViCare(VENTILATION_FIXTURES)
    )

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_created_per_available_quickmode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that only quickmodes that can be switched get an entity."""
    await setup_switch_platform(
        hass, mock_config_entry, MockPyViCare(VENTILATION_FIXTURES)
    )

    assert set(hass.states.async_entity_ids(SWITCH_DOMAIN)) == {
        "switch.model0_boost",
        "switch.model0_silent",
        "switch.model1_boost",
        "switch.model1_silent",
        "switch.model2_intensive",
        "switch.model2_eco",
    }


async def test_switch_state_follows_quickmode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an active quickmode is reported as on."""
    mock_vicare = MockPyViCare(VENTILATION_FIXTURES)
    activate_quickmode(mock_vicare, 2, "comfort")

    await setup_switch_platform(hass, mock_config_entry, mock_vicare)

    assert hass.states.get("switch.model2_intensive").state == STATE_ON
    assert hass.states.get("switch.model2_eco").state == STATE_OFF


async def test_turn_on_activates_quickmode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that turning the switch on activates the quickmode."""
    mock_vicare = MockPyViCare(VENTILATION_FIXTURES)
    await setup_switch_platform(hass, mock_config_entry, mock_vicare)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.model2_intensive"},
        blocking=True,
    )

    device = mock_vicare.devices[2]
    device.service.setProperty.assert_called_once_with(
        device.accessor, "ventilation.quickmodes.comfort", "activate", {}
    )


async def test_turn_off_deactivates_quickmode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that turning the switch off deactivates the quickmode."""
    mock_vicare = MockPyViCare(VENTILATION_FIXTURES)
    await setup_switch_platform(hass, mock_config_entry, mock_vicare)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.model0_boost"},
        blocking=True,
    )

    device = mock_vicare.devices[0]
    device.service.setProperty.assert_called_once_with(
        device.accessor, "ventilation.quickmodes.forcedLevelFour", "deactivate", {}
    )


async def test_no_switch_for_non_ventilation_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a device without ventilation does not get quickmode switches."""
    await setup_switch_platform(
        hass,
        mock_config_entry,
        MockPyViCare([Fixture({"type:boiler"}, "vicare/Vitodens300W.json")]),
    )

    assert not hass.states.async_entity_ids(SWITCH_DOMAIN)


async def test_turn_on_error_is_raised(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a failed activation is not swallowed."""
    mock_vicare = MockPyViCare(VENTILATION_FIXTURES)
    await setup_switch_platform(hass, mock_config_entry, mock_vicare)
    mock_vicare.devices[
        2
    ].service.setProperty.side_effect = PyViCareNotSupportedFeatureError("comfort")

    with pytest.raises(PyViCareNotSupportedFeatureError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.model2_intensive"},
            blocking=True,
        )


async def test_turn_on_refused_while_another_quickmode_runs(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the device refusing a second quickmode reads as a clear error."""
    mock_vicare = MockPyViCare(VENTILATION_FIXTURES)
    await setup_switch_platform(hass, mock_config_entry, mock_vicare)
    mock_vicare.devices[2].service.setProperty.side_effect = PyViCareCommandError(
        {"statusCode": 400, "extendedPayload": "COMMAND_NOT_EXECUTABLE"}
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.model2_intensive"},
            blocking=True,
        )

    assert err.value.translation_key == "quickmode_not_activated"


def activate_quickmode(mock_vicare: MockPyViCare, device: int, quickmode: str) -> None:
    """Mark a quickmode as active in the fixture data of a mocked device."""
    config = mock_vicare.devices[device]
    for feature in config.service._features[config.device_id]:
        if feature["feature"] == f"ventilation.quickmodes.{quickmode}":
            feature["properties"]["active"]["value"] = True
            return
    pytest.fail(f"quickmode {quickmode} not found in fixture")
