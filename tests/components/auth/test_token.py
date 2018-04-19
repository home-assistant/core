"""Tests for the auth token helpers."""
from homeassistant.components import auth

from tests.common import MockUser


SECRET = 'bla'


async def test_decline_access_token_no_longer_exists(hass):
    """Decline access tokens if issued before user.token_min_issued."""
    user = MockUser().add_to_hass(hass)
    token = await hass.auth.async_create_token(user, 'mock-client-id')
    access_token = auth.token.async_access_token(hass, SECRET, token)

    info = await auth.token.async_resolve_token(
        hass, SECRET, access_token, 'mock-client-id')
    assert info is not None

    user.tokens.remove(token)

    info = await auth.token.async_resolve_token(
        hass, SECRET, access_token, 'mock-client-id')
    assert info is None


async def test_decline_access_token_user_not_active(hass):
    """Decline access tokens if user is not marked as active."""
    user = MockUser().add_to_hass(hass)
    token = await hass.auth.async_create_token(user, 'mock-client-id')
    access_token = auth.token.async_access_token(hass, SECRET, token)

    info = await auth.token.async_resolve_token(
        hass, SECRET, access_token, 'mock-client-id')
    assert info is not None

    user.is_active = False

    info = await auth.token.async_resolve_token(
        hass, SECRET, access_token, 'mock-client-id')
    assert info is None


async def test_decline_access_token_user_no_longer_exists(hass):
    """Decline access tokens if user no longer exists."""
    user = MockUser().add_to_hass(hass)
    token = await hass.auth.async_create_token(user, 'mock-client-id')
    access_token = auth.token.async_access_token(hass, SECRET, token)

    info = await auth.token.async_resolve_token(
        hass, SECRET, access_token, 'mock-client-id')
    assert info is not None

    await hass.auth.async_remove_user(user)

    info = await auth.token.async_resolve_token(
        hass, access_token, 'mock-client-id')
    assert info is None


async def test_decline_refresh_token_no_longer_exists(hass):
    """Decline refresh tokens if issued before user.token_min_issued."""
    user = MockUser().add_to_hass(hass)
    token = await hass.auth.async_create_token(user, 'mock-client-id')
    refresh_token = auth.token.async_refresh_token(hass, SECRET, token)

    info = await auth.token.async_resolve_token(
        hass, SECRET, refresh_token, 'mock-client-id')
    assert info is not None

    user.tokens.remove(token)

    info = await auth.token.async_resolve_token(
        hass, SECRET, refresh_token, 'mock-client-id')
    assert info is None


async def test_decline_refresh_token_user_not_active(hass):
    """Decline refresh tokens if user is not marked as active."""
    user = MockUser().add_to_hass(hass)
    token = await hass.auth.async_create_token(user, 'mock-client-id')
    refresh_token = auth.token.async_refresh_token(hass, SECRET, token)

    info = await auth.token.async_resolve_token(
        hass, SECRET, refresh_token, 'mock-client-id')
    assert info is not None

    user.is_active = False

    info = await auth.token.async_resolve_token(
        hass, SECRET, refresh_token, 'mock-client-id')
    assert info is None


async def test_decline_refresh_token_user_no_longer_exists(hass):
    """Decline refresh tokens if user no longer exists."""
    user = MockUser().add_to_hass(hass)
    token = await hass.auth.async_create_token(user, 'mock-client-id')
    refresh_token = auth.token.async_refresh_token(hass, SECRET, token)

    info = await auth.token.async_resolve_token(
        hass, SECRET, refresh_token, 'mock-client-id')
    assert info is not None

    await hass.auth.async_remove_user(user)

    info = await auth.token.async_resolve_token(
        hass, SECRET, refresh_token, 'mock-client-id')
    assert info is None
