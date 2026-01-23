"""Fixtures for WaterFurnace tests."""

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from waterfurnace.waterfurnace import WFReading

from tests.common import load_json_object_fixture


@pytest.fixture
def mock_waterfurnace_client() -> Generator[MagicMock]:
    """Mock a WaterFurnace client."""
    client = MagicMock()
    client.gwid = "device_123"
    client.login = MagicMock()

    fixture_data = load_json_object_fixture("device_data.json", "waterfurnace")
    wf_reading = WFReading(fixture_data)

    client.read_with_retry = MagicMock(return_value=wf_reading)

    return client
