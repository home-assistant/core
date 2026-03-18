"""Common helpers for the datetime entity component tests."""

from unittest import mock

MOCK_DATA = {
    "host": "localhost",
    "port": 8125,
}

MOCK_OPTIONS = {
    "prefix": "hass",
    "rate": 1,
}

MOCK_CONFIG = {**MOCK_DATA, **MOCK_OPTIONS}

MOCK_YAML_INVALID = {
    "host": "127.0.0.1",
    "port": 65535,
    "prefix": "failtest",
    "rate": 1,
}


CONNECTION_TEST_METRIC = "connection_test"


def create_mock_state(entity_id, state, attributes=None):
    """Helper to create a mock state object."""
    mock_state = mock.MagicMock()
    mock_state.entity_id = entity_id
    mock_state.state = state
    mock_state.domain = entity_id.split(".")[0]
    mock_state.attributes = attributes or {}
    return mock_state
