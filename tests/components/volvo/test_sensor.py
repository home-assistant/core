"""Test Volvo sensors."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import model


@pytest.mark.parametrize(
    ("expected_state"),
    [
        pytest.param(23 * 30, marks=model("xc40_electric_2024")),
        pytest.param(17, marks=model("s90_diesel_2018")),
    ],
)
async def test_time_to_service(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    model_from_marker: str,
    expected_state: int,
) -> None:
    """Test time to service."""

    entity_id = f"sensor.volvo_{model_from_marker}_time_to_service"

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await setup_integration()

        entity = hass.states.get(entity_id)
        assert entity
        assert entity.state == f"{expected_state}"
