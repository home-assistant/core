"""Tests for the init."""
from unittest.mock import patch, Mock

from homeassistant.setup import async_setup_component
from homeassistant.components import onboarding

from tests.common import mock_coro, MockUser

from . import mock_storage

# Temporarily: if auth not active, always set onboarded=True


async def test_not_setup_views_if_onboarded(hass, hass_storage):
    """Test if onboarding is done, we don't setup views."""
    mock_storage(hass_storage, {
        'done': onboarding.STEPS
    })

    with patch(
        'homeassistant.components.onboarding.views.async_setup'
    ) as mock_setup:
        assert await async_setup_component(hass, 'onboarding', {})

    assert len(mock_setup.mock_calls) == 0
    assert onboarding.DOMAIN not in hass.data
    assert onboarding.async_is_onboarded(hass)


async def test_setup_views_if_not_onboarded(hass):
    """Test if onboarding is not done, we setup views."""
    with patch(
        'homeassistant.components.onboarding.views.async_setup',
        return_value=mock_coro()
    ) as mock_setup:
        assert await async_setup_component(hass, 'onboarding', {})

    assert len(mock_setup.mock_calls) == 1
    assert onboarding.DOMAIN in hass.data

    assert not onboarding.async_is_onboarded(hass)


async def test_is_onboarded():
    """Test the is onboarded function."""
    hass = Mock()
    hass.data = {}

    assert onboarding.async_is_onboarded(hass)

    hass.data[onboarding.DOMAIN] = True
    assert onboarding.async_is_onboarded(hass)

    hass.data[onboarding.DOMAIN] = False
    assert not onboarding.async_is_onboarded(hass)


async def test_having_owner_finishes_user_step(hass, hass_storage):
    """If owner user already exists, mark user step as complete."""
    MockUser(is_owner=True).add_to_hass(hass)

    with patch(
        'homeassistant.components.onboarding.views.async_setup'
    ) as mock_setup, patch.object(onboarding, 'STEPS', [onboarding.STEP_USER]):
        assert await async_setup_component(hass, 'onboarding', {})

    assert len(mock_setup.mock_calls) == 0
    assert onboarding.DOMAIN not in hass.data
    assert onboarding.async_is_onboarded(hass)

    done = hass_storage[onboarding.STORAGE_KEY]['data']['done']
    assert onboarding.STEP_USER in done
