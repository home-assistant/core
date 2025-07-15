"""Common helpers for the datetime entity component tests."""

from unittest import mock

# tests/components/datadog/common.py

MOCK_DATA = {
    "host": "localhost",
    "port": 8125,
}

MOCK_OPTIONS = {
    "prefix": "hass",
    "rate": 1,
}

MOCK_CONFIG = {**MOCK_DATA, **MOCK_OPTIONS}

CONNECTION_TEST_METRIC = "connection_test"


def create_mock_state(entity_id, state, attributes=None):
    """Helper to create a mock state object."""
    mock_state = mock.MagicMock()
    mock_state.entity_id = entity_id
    mock_state.state = state
    mock_state.domain = entity_id.split(".")[0]
    mock_state.attributes = attributes or {}
    return mock_state
