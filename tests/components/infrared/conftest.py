"""Common fixtures for the Infrared tests."""

import pytest

from .common import MockInfraredEmitterEntity, MockInfraredReceiverEntity


@pytest.fixture
def mock_infrared_emitter_entity() -> MockInfraredEmitterEntity:
    """Return a mock infrared emitter entity."""
    return MockInfraredEmitterEntity("test_ir_emitter")


@pytest.fixture
def mock_infrared_receiver_entity() -> MockInfraredReceiverEntity:
    """Return a mock infrared receiver entity."""
    return MockInfraredReceiverEntity("test_ir_receiver")
