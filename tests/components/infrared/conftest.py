"""Common fixtures for the Infrared tests."""

import pytest

from .common import (
    MockInfraredEmitterEntity,
    MockInfraredEntity,
    MockInfraredReceiverEntity,
)


@pytest.fixture(params=[MockInfraredEntity, MockInfraredEmitterEntity])
def mock_infrared_emitter_entity(
    request: pytest.FixtureRequest,
) -> MockInfraredEntity | MockInfraredEmitterEntity:
    """Return a mock infrared emitter entity."""
    return request.param("test_ir_emitter")


@pytest.fixture
def mock_infrared_receiver_entity() -> MockInfraredReceiverEntity:
    """Return a mock infrared receiver entity."""
    return MockInfraredReceiverEntity("test_ir_receiver")
