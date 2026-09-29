"""General Starlink patchers."""

from collections.abc import Callable
from unittest.mock import patch

import grpc
from starlink_grpc import GrpcError

from tests.common import load_json_array_fixture, load_json_object_fixture

SETUP_ENTRY_PATCHER = patch(
    "homeassistant.components.starlink.async_setup_entry", return_value=True
)


class _FakeRpcError(grpc.RpcError, grpc.Call):
    """A concrete grpc.Call double carrying a specific status code."""

    def __init__(self, code: grpc.StatusCode) -> None:
        """Set up the fake error with the given status code."""
        self._code = code

    def code(self) -> grpc.StatusCode:
        """Return the configured status code."""
        return self._code

    def details(self) -> str:
        """Return fake details."""
        return "fake grpc error for tests"

    def cancel(self) -> bool:
        """Return that cancellation is a no-op for this fake."""
        return False

    def is_active(self) -> bool:
        """Return that this fake call is not active."""
        return False

    def time_remaining(self) -> float | None:
        """Return that this fake call has no deadline."""
        return None

    def add_callback(self, callback: Callable[[], None]) -> bool:
        """Return that callback registration is a no-op for this fake."""
        return False

    def initial_metadata(self) -> tuple:
        """Return empty initial metadata."""
        return ()

    def trailing_metadata(self) -> tuple:
        """Return empty trailing metadata."""
        return ()


def _raise_grpc_error(code: grpc.StatusCode):
    """Build a side_effect that raises GrpcError chained to a given status code.

    Mirrors how starlink_grpc itself raises: `raise GrpcError(e) from e`, so
    exc.__cause__ is a real grpc.Call with a real .code().
    """

    def _raiser(*args, **kwargs):
        cause = _FakeRpcError(code)
        raise GrpcError(cause) from cause

    return _raiser


LOCATION_DATA_SUCCESS_PATCHER = patch(
    "homeassistant.components.starlink.coordinator.location_data",
    return_value=load_json_object_fixture("location_data_success.json", "starlink"),
)

LOCATION_DATA_UNIMPLEMENTED_PATCHER = patch(
    "homeassistant.components.starlink.coordinator.location_data",
    side_effect=_raise_grpc_error(grpc.StatusCode.UNIMPLEMENTED),
)

LOCATION_DATA_UNAVAILABLE_PATCHER = patch(
    "homeassistant.components.starlink.coordinator.location_data",
    side_effect=_raise_grpc_error(grpc.StatusCode.UNAVAILABLE),
)

SLEEP_DATA_SUCCESS_PATCHER = patch(
    "homeassistant.components.starlink.coordinator.get_sleep_config",
    return_value=load_json_array_fixture("sleep_data_success.json", "starlink"),
)

SLEEP_DATA_UNIMPLEMENTED_PATCHER = patch(
    "homeassistant.components.starlink.coordinator.get_sleep_config",
    side_effect=_raise_grpc_error(grpc.StatusCode.UNIMPLEMENTED),
)

SLEEP_DATA_UNAVAILABLE_PATCHER = patch(
    "homeassistant.components.starlink.coordinator.get_sleep_config",
    side_effect=_raise_grpc_error(grpc.StatusCode.UNAVAILABLE),
)

STATUS_DATA_TARGET = "homeassistant.components.starlink.coordinator.status_data"
STATUS_DATA_FIXTURE = load_json_array_fixture("status_data_success.json", "starlink")
STATUS_DATA_SUCCESS_PATCHER = patch(
    STATUS_DATA_TARGET, return_value=STATUS_DATA_FIXTURE
)

HISTORY_STATS_SUCCESS_PATCHER = patch(
    "homeassistant.components.starlink.coordinator.history_stats",
    return_value=load_json_array_fixture("history_stats_success.json", "starlink"),
)

DEVICE_FOUND_PATCHER = patch(
    "homeassistant.components.starlink.config_flow.get_id", return_value="some-valid-id"
)

NO_DEVICE_PATCHER = patch(
    "homeassistant.components.starlink.config_flow.get_id", return_value=None
)
