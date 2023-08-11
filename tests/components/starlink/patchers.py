"""General Starlink patchers."""
import json
from unittest.mock import patch

from tests.common import load_fixture

SETUP_ENTRY_PATCHER = patch(
    "homeassistant.components.starlink.async_setup_entry", return_value=True
)

COORDINATOR_SUCCESS_PATCHER = patch(
    "homeassistant.components.starlink.coordinator.status_data",
    return_value=json.loads(load_fixture("status_data_success.json", "starlink")),
)

DEVICE_FOUND_PATCHER = patch(
    "homeassistant.components.starlink.config_flow.get_id", return_value="some-valid-id"
)

NO_DEVICE_PATCHER = patch(
    "homeassistant.components.starlink.config_flow.get_id", return_value=None
)
