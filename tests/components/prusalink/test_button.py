"""Test Prusalink buttons."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

from pyprusalink.types import Conflict
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def setup_button_platform_only():
    """Only setup button platform."""
    with patch("homeassistant.components.prusalink.PLATFORMS", [Platform.BUTTON]):
        yield


@pytest.fixture
def press_button_and_verify(
    hass: HomeAssistant,
) -> Callable[[str, str], Awaitable[None]]:
    """Return a helper that asserts the press path for a PrusaLink button.

    The helper verifies the entity is in the `unknown` state, that pressing it
    invokes the matching pyprusalink method once, and that a `Conflict` from
    the API surfaces as `HomeAssistantError`.
    """

    async def _press_and_verify(entity_id: str, method: str) -> None:
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
        mock_meth.assert_awaited_once()

        with (
            pytest.raises(HomeAssistantError),
            patch(f"pyprusalink.PrusaLink.{method}", side_effect=Conflict),
        ):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": entity_id},
                blocking=True,
            )

    return _press_and_verify


@pytest.mark.parametrize(
    ("object_id", "method"),
    [
        ("workshop_mock_title_cancel_job", "cancel_job"),
        ("workshop_mock_title_pause_job", "pause_job"),
    ],
)
async def test_button_pause_cancel(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api,
    mock_job_api_printing,
    mock_get_status_printing,
    press_button_and_verify,
    object_id: str,
    method: str,
) -> None:
    """Test cancel and pause buttons in PRINTING state."""
    assert await async_setup_component(hass, "prusalink", {})
    await press_button_and_verify(f"button.{object_id}", method)


@pytest.mark.parametrize(
    ("object_id", "method"),
    [
        ("workshop_mock_title_cancel_job", "cancel_job"),
        ("workshop_mock_title_resume_job", "resume_job"),
    ],
)
async def test_button_resume_cancel(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api,
    mock_job_api_paused,
    press_button_and_verify,
    object_id: str,
    method: str,
) -> None:
    """Test cancel and resume buttons in PAUSED state."""
    assert await async_setup_component(hass, "prusalink", {})
    await press_button_and_verify(f"button.{object_id}", method)


async def test_button_continue(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api,
    mock_job_api_attention,
    press_button_and_verify,
) -> None:
    """Test continue button is enabled in ATTENTION state and calls continue_job."""
    assert await async_setup_component(hass, "prusalink", {})
    await press_button_and_verify(
        "button.workshop_mock_title_continue_job", "continue_job"
    )


async def test_button_continue_unavailable_when_printing(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api,
    mock_job_api_printing,
    mock_get_status_printing,
) -> None:
    """Continue button is unavailable when printer is not in ATTENTION state."""
    assert await async_setup_component(hass, "prusalink", {})
    state = hass.states.get("button.workshop_mock_title_continue_job")
    assert state is not None
    assert state.state == "unavailable"
