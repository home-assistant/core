"""Tests for WLED release coordination."""

from unittest.mock import AsyncMock, MagicMock, call, patch

from homeassistant.components.wled import WLED_KEY, async_get_releases_coordinator
from homeassistant.components.wled.coordinator import normalize_repo
from homeassistant.core import HomeAssistant


def test_normalize_repo() -> None:
    """Test repo normalization."""
    assert normalize_repo(None) == "wled/WLED"
    assert normalize_repo("") == "wled/WLED"
    assert normalize_repo("  LordMike/Wled  ") == "LordMike/Wled"


async def test_release_coordinator_is_cached_per_repo(hass: HomeAssistant) -> None:
    """Test release coordinators are deduplicated by repository."""
    hass.data[WLED_KEY] = {}

    created: list[MagicMock] = []

    def _create_coordinator(*args: object, **kwargs: object) -> MagicMock:
        coordinator = MagicMock()
        coordinator.async_request_refresh = AsyncMock()
        created.append(coordinator)
        return coordinator

    with patch(
        "homeassistant.components.wled.WLEDReleasesDataUpdateCoordinator",
        autospec=True,
        side_effect=_create_coordinator,
    ) as mock_coordinator:
        first = await async_get_releases_coordinator(hass, "LordMike/Wled")
        second = await async_get_releases_coordinator(hass, "LordMike/Wled")
        default = await async_get_releases_coordinator(hass, None)

    assert first is second
    assert first is not default
    assert created == [first, default]
    assert mock_coordinator.call_args_list == [
        call(hass, repo="LordMike/Wled"),
        call(hass, repo="wled/WLED"),
    ]
    assert first.async_request_refresh.await_count == 1
    assert default.async_request_refresh.await_count == 1
