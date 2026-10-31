"""Tests for Redfish data models."""

import pytest

from homeassistant.components.redfish.models import (
    RedfishSystem,
    get_reset_action_info_target,
    parse_reset_action_info,
    parse_system,
)


def test_get_reset_action_info_target_without_reset_action() -> None:
    """Test an ActionInfo target requires a reset action."""
    assert get_reset_action_info_target({}) is None


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({}, id="missing-parameters"),
        pytest.param(
            {"Parameters": [{"Name": "ResetType"}]},
            id="missing-allowable-values",
        ),
        pytest.param(
            {"Parameters": [None, {"Name": "OtherParameter"}]},
            id="missing-reset-type-parameter",
        ),
    ],
)
def test_parse_reset_action_info_without_usable_values(
    payload: dict[str, object],
) -> None:
    """Test malformed ActionInfo parameters produce no reset types."""
    assert parse_reset_action_info(payload) == frozenset()


def test_parse_system_metadata_and_actions() -> None:
    """Test parsing system metadata and only usable advertised reset types."""
    assert parse_system(
        {
            "@odata.id": "/redfish/v1/Systems/1",
            "Id": "1",
            "Name": "Server",
            "UUID": "uuid-1",
            "Manufacturer": "Acme",
            "Model": "Model 1",
            "SerialNumber": "serial",
            "PowerState": "On",
            "Actions": {
                "#ComputerSystem.Reset": {
                    "target": "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
                    "ResetType@Redfish.AllowableValues": [
                        "On",
                        "ForceOff",
                        "FullPowerCycle",
                        "On",
                        "VendorReset",
                        1,
                    ],
                }
            },
        }
    ) == RedfishSystem(
        odata_id="/redfish/v1/Systems/1",
        system_id="1",
        name="Server",
        uuid="uuid-1",
        manufacturer="Acme",
        model="Model 1",
        serial_number="serial",
        power_state="On",
        reset_target="/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
        reset_types=frozenset({"On", "ForceOff", "FullPowerCycle"}),
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"Id": "1"},
        {"@odata.id": "/redfish/v1/Systems/1"},
        {"@odata.id": "", "Id": "1"},
        {"@odata.id": "/redfish/v1/Systems/1", "Id": ""},
    ],
)
def test_skip_malformed_systems(payload: dict[str, object]) -> None:
    """Test systems without stable standard identifiers are skipped."""
    assert parse_system(payload) is None
