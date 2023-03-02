"""General Starlink patchers."""
from unittest.mock import patch

from starlink_grpc import StatusDict

SETUP_ENTRY_PATCHER = patch(
    "homeassistant.components.starlink.async_setup_entry", return_value=True
)

COORDINATOR_SUCCESS_PATCHER = patch(
    "homeassistant.components.starlink.coordinator.status_data",
    return_value=[
        StatusDict(id="1", software_version="1", hardware_version="1"),
        {},
        {},
    ],
)

DEVICE_FOUND_PATCHER = patch(
    "homeassistant.components.starlink.config_flow.get_id", return_value="some-valid-id"
)

NO_DEVICE_PATCHER = patch(
    "homeassistant.components.starlink.config_flow.get_id", return_value=None
)
