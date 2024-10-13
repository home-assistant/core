"""Tests for the init."""

from typing import Any
from unittest.mock import Mock, patch

from homeassistant.components import onboarding
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import mock_storage

from tests.common import MockUser

# Temporarily: if auth not active, always set onboarded=True


async def test_not_setup_views_if_onboarded(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test if onboarding is done, we don't setup views."""
    mock_storage(hass_storage, {"done": onboarding.STEPS})

    with patch("homeassistant.components.onboarding.views.async_setup") as mock_setup:
        assert await async_setup_component(hass, "onboarding", {})

    assert len(mock_setup.mock_calls) == 0
    assert onboarding.DOMAIN not in hass.data
    assert onboarding.async_is_onboarded(hass)


async def test_setup_views_if_not_onboarded(hass: HomeAssistant) -> None:
    """Test if onboarding is not done, we setup views."""
    with patch(
        "homeassistant.components.onboarding.views.async_setup",
    ) as mock_setup:
        assert await async_setup_component(hass, "onboarding", {})

    assert len(mock_setup.mock_calls) == 1
    assert onboarding.DOMAIN in hass.data

    assert not onboarding.async_is_onboarded(hass)


async def test_is_onboarded() -> None:
    """Test the is onboarded function."""
    hass = Mock()
    hass.data = {}

    assert onboarding.async_is_onboarded(hass)

    hass.data[onboarding.DOMAIN] = onboarding.OnboardingData([], True, {"done": []})
    assert onboarding.async_is_onboarded(hass)

    hass.data[onboarding.DOMAIN] = onboarding.OnboardingData([], False, {"done": []})
    assert not onboarding.async_is_onboarded(hass)


async def test_is_user_onboarded() -> None:
    """Test the is onboarded function."""
    hass = Mock()
    hass.data = {}

    assert onboarding.async_is_user_onboarded(hass)

    hass.data[onboarding.DOMAIN] = onboarding.OnboardingData([], True, {"done": []})
    assert onboarding.async_is_user_onboarded(hass)

    hass.data[onboarding.DOMAIN] = onboarding.OnboardingData(
        [], False, {"done": ["user"]}
    )
    assert onboarding.async_is_user_onboarded(hass)

    hass.data[onboarding.DOMAIN] = onboarding.OnboardingData([], False, {"done": []})
    assert not onboarding.async_is_user_onboarded(hass)


async def test_having_owner_finishes_user_step(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """If owner user already exists, mark user step as complete."""
    MockUser(is_owner=True).add_to_hass(hass)

    with (
        patch("homeassistant.components.onboarding.views.async_setup") as mock_setup,
        patch.object(onboarding, "STEPS", [onboarding.STEP_USER]),
    ):
        assert await async_setup_component(hass, "onboarding", {})

    assert len(mock_setup.mock_calls) == 0
    assert onboarding.DOMAIN not in hass.data
    assert onboarding.async_is_onboarded(hass)

    done = hass_storage[onboarding.STORAGE_KEY]["data"]["done"]
    assert onboarding.STEP_USER in done


async def test_migration(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test migrating onboarding to new version."""
    hass_storage[onboarding.STORAGE_KEY] = {"version": 1, "data": {"done": ["user"]}}
    assert await async_setup_component(hass, "onboarding", {})
    assert onboarding.async_is_onboarded(hass)
