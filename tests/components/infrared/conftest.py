"""Common fixtures for the Infrared tests."""

import pytest
from pytest_homeassistant.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredEntity,
)

from homeassistant.components.infrared import DATA_COMPONENT
from homeassistant.core import HomeAssistant


@pytest.fixture(params=[MockInfraredEntity, MockInfraredEmitterEntity])
async def mock_infrared_emitter_entity(
    hass: HomeAssistant,
    init_infrared: None,
    request: pytest.FixtureRequest,
) -> MockInfraredEntity | MockInfraredEmitterEntity:
    """Return a mock infrared emitter entity.

    This overrides the default common fixture to also test the deprecated
    MockInfraredEntity.
    """
    entity = request.param("test_ir_emitter")
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([entity])
    return entity
