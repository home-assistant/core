"""Test Prusalink buttons."""
from unittest.mock import patch

from pyprusalink import Conflict
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def setup_button_platform_only():
    """Only setup button platform."""
    with patch("homeassistant.components.prusalink.PLATFORMS", [Platform.BUTTON]):
        yield


@pytest.mark.parametrize(
    ("object_id", "method"),
    (
        ("mock_title_cancel_job", "cancel_job"),
        ("mock_title_pause_job", "pause_job"),
    ),
)
async def test_button_pause_cancel(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api,
    hass_client: ClientSessionGenerator,
    mock_job_api_printing,
    object_id,
    method,
) -> None:
    """Test cancel and pause button."""
    entity_id = f"button.{object_id}"
    assert await async_setup_component(hass, "prusalink", {})
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"

    with patch(f"pyprusalink.PrusaLink.{method}") as mock_meth:
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id},
            blocking=True,
        )

    assert len(mock_meth.mock_calls) == 1

    # Verify it calls correct method + does error handling
    with pytest.raises(HomeAssistantError), patch(
        f"pyprusalink.PrusaLink.{method}", side_effect=Conflict
    ):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("object_id", "method"),
    (("mock_title_resume_job", "resume_job"),),
)
async def test_button_resume(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api,
    hass_client: ClientSessionGenerator,
    mock_job_api_paused,
    object_id,
    method,
) -> None:
    """Test resume button."""
    entity_id = f"button.{object_id}"
    assert await async_setup_component(hass, "prusalink", {})
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"

    with patch(f"pyprusalink.PrusaLink.{method}") as mock_meth, patch(
        "homeassistant.components.prusalink.PrusaLinkUpdateCoordinator._fetch_data"
    ):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id},
            blocking=True,
        )

    assert len(mock_meth.mock_calls) == 1

    # Verify it calls correct method + does error handling
    with pytest.raises(HomeAssistantError), patch(
        f"pyprusalink.PrusaLink.{method}", side_effect=Conflict
    ):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id},
            blocking=True,
        )
