"""General Starlink patchers."""

import json
from unittest.mock import patch

from tests.common import load_fixture

SETUP_ENTRY_PATCHER = patch(
    "homeassistant.components.starlink.async_setup_entry", return_value=True
)

STATUS_DATA_SUCCESS_PATCHER = patch(
    "homeassistant.components.starlink.coordinator.status_data",
    return_value=json.loads(load_fixture("status_data_success.json", "starlink")),
)

LOCATION_DATA_SUCCESS_PATCHER = patch(
    "homeassistant.components.starlink.coordinator.location_data",
    return_value=json.loads(load_fixture("location_data_success.json", "starlink")),
)

SLEEP_DATA_SUCCESS_PATCHER = patch(
    "homeassistant.components.starlink.coordinator.get_sleep_config",
    return_value=json.loads(load_fixture("sleep_data_success.json", "starlink")),
)

HISTORY_STATS_SUCCESS_PATCHER = patch(
    "homeassistant.components.starlink.coordinator.history_stats",
    return_value=json.loads(load_fixture("history_stats_success.json", "starlink")),
)

DEVICE_FOUND_PATCHER = patch(
    "homeassistant.components.starlink.config_flow.get_id", return_value="some-valid-id"
)

NO_DEVICE_PATCHER = patch(
    "homeassistant.components.starlink.config_flow.get_id", return_value=None
)
