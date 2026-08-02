"""Tests for Redfish data models."""

import pytest

from homeassistant.components.redfish.models import RedfishSystem, parse_system


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
