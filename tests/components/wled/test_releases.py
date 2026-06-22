"""Tests for WLED release coordination."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from wled import Releases, WLEDError

from homeassistant.components.wled.coordinator import (
    WLEDReleasesDataUpdateCoordinator,
    normalize_repo,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


def _releases(repo: str, stable: str) -> Releases:
    """Return release data for a repo."""
    return Releases(beta=None, nightly=None, repo=repo, stable=stable)


async def _set_repos(
    coordinator: WLEDReleasesDataUpdateCoordinator, repos: dict[str, str]
) -> None:
    """Set tracked repos without refreshing releases."""
    with patch.object(coordinator, "async_request_refresh", AsyncMock()):
        for entry_id, repo in repos.items():
            await coordinator.async_set_repo(entry_id, repo)


@pytest.fixture
def releases_factory() -> Callable[[dict[str, Releases | Exception]], MagicMock]:
    """Return a WLEDReleases factory mock."""

    def _factory(results: dict[str, Releases | Exception]) -> MagicMock:
        def _create_releases(*args: object, **kwargs: object) -> MagicMock:
            repo = kwargs["repo"]
            result = results[repo]
            client = MagicMock()
            client.releases = AsyncMock()
            if isinstance(result, Exception):
                client.releases.side_effect = result
            else:
                client.releases.return_value = result
            return client

        return MagicMock(side_effect=_create_releases)

    return _factory


def test_normalize_repo() -> None:
    """Test repo normalization."""
    assert normalize_repo(None) == "wled/WLED"
    assert normalize_repo("") == "wled/WLED"
    assert normalize_repo("wled/wled") == "wled/WLED"
    assert normalize_repo("  Light-Corp/Wled  ") == "light-corp/wled"


async def test_release_coordinator_fetches_distinct_repos(
    hass: HomeAssistant,
    releases_factory: Callable[[dict[str, Releases | Exception]], MagicMock],
) -> None:
    """Test release fetches are deduplicated by repository."""
    coordinator = WLEDReleasesDataUpdateCoordinator(hass)
    await _set_repos(
        coordinator,
        {
            "entry-1": "wled/WLED",
            "entry-2": "wled/WLED",
            "entry-3": "light-corp/wled",
        },
    )
    wled_releases = releases_factory(
        {
            "wled/WLED": _releases("wled/WLED", "1.0.0"),
            "light-corp/wled": _releases("light-corp/wled", "2.0.0"),
        }
    )

    with patch("homeassistant.components.wled.coordinator.WLEDReleases", wled_releases):
        data = await coordinator._async_update_data()

    assert data == {
        "wled/WLED": _releases("wled/WLED", "1.0.0"),
        "light-corp/wled": _releases("light-corp/wled", "2.0.0"),
    }
    assert wled_releases.call_count == 2
    assert {call.kwargs["repo"] for call in wled_releases.call_args_list} == {
        "light-corp/wled",
        "wled/WLED",
    }


async def test_release_coordinator_keeps_old_data_on_partial_failure(
    hass: HomeAssistant,
    releases_factory: Callable[[dict[str, Releases | Exception]], MagicMock],
) -> None:
    """Test old release info is kept when a repo refresh fails."""
    coordinator = WLEDReleasesDataUpdateCoordinator(hass)
    await _set_repos(
        coordinator,
        {
            "entry-1": "wled/WLED",
            "entry-2": "light-corp/wled",
            "entry-3": "unused/repo",
        },
    )
    coordinator.data = {
        "wled/WLED": _releases("wled/WLED", "1.0.0"),
        "light-corp/wled": _releases("light-corp/wled", "2.0.0"),
        "old/repo": _releases("old/repo", "3.0.0"),
    }
    wled_releases = releases_factory(
        {
            "wled/WLED": WLEDError("failed"),
            "light-corp/wled": _releases("light-corp/wled", "2.1.0"),
            "unused/repo": WLEDError("failed"),
        }
    )

    with patch("homeassistant.components.wled.coordinator.WLEDReleases", wled_releases):
        data = await coordinator._async_update_data()

    assert data == {
        "wled/WLED": _releases("wled/WLED", "1.0.0"),
        "light-corp/wled": _releases("light-corp/wled", "2.1.0"),
    }


async def test_release_coordinator_raises_when_all_active_repos_fail(
    hass: HomeAssistant,
    releases_factory: Callable[[dict[str, Releases | Exception]], MagicMock],
) -> None:
    """Test all repo failures are surfaced as a coordinator update failure."""
    coordinator = WLEDReleasesDataUpdateCoordinator(hass)
    await _set_repos(
        coordinator,
        {
            "entry-1": "wled/WLED",
            "entry-2": "light-corp/wled",
        },
    )
    coordinator.data = {
        "wled/WLED": _releases("wled/WLED", "1.0.0"),
        "light-corp/wled": _releases("light-corp/wled", "2.0.0"),
    }
    wled_releases = releases_factory(
        {
            "wled/WLED": WLEDError("failed"),
            "light-corp/wled": WLEDError("failed"),
        }
    )

    with (
        patch("homeassistant.components.wled.coordinator.WLEDReleases", wled_releases),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()


async def test_release_coordinator_removes_unused_repo_data(
    hass: HomeAssistant,
) -> None:
    """Test release data is removed when no entry uses a repo anymore."""
    coordinator = WLEDReleasesDataUpdateCoordinator(hass)
    await _set_repos(
        coordinator,
        {
            "entry-1": "wled/WLED",
            "entry-2": "wled/WLED",
            "entry-3": "light-corp/wled",
        },
    )
    coordinator.data = {
        "wled/WLED": _releases("wled/WLED", "1.0.0"),
        "light-corp/wled": _releases("light-corp/wled", "2.0.0"),
    }

    coordinator.async_unset_repo("entry-1")
    assert "wled/WLED" in coordinator.data

    coordinator.async_unset_repo("entry-2")
    assert coordinator.data == {
        "light-corp/wled": _releases("light-corp/wled", "2.0.0")
    }
