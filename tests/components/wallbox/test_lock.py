"""Test Wallbox Lock component."""
from http import HTTPStatus
from unittest.mock import Mock, patch

import pytest
from requests import HTTPError

from homeassistant.components.lock import SERVICE_LOCK, SERVICE_UNLOCK
from homeassistant.components.wallbox import InvalidAuth
from homeassistant.config_entries import UnknownEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import entry, setup_integration, setup_integration_no_lock_auth
from .const import MOCK_LOCK_ENTITY_ID


async def test_wallbox_lock_class(hass: HomeAssistant) -> None:
    """Test wallbox lock class."""

    try:
        assert await hass.config_entries.async_unload(entry.entry_id)
    except (UnknownEntry):
        pass

    await setup_integration(hass)

    state = hass.states.get(MOCK_LOCK_ENTITY_ID)
    assert state
    assert state.state == "unlocked"

    with patch("wallbox.Wallbox.authenticate", return_value=None,), patch(
        "wallbox.Wallbox.lockCharger",
        return_value=None,
    ), patch(
        "wallbox.Wallbox.unlockCharger",
        return_value=None,
    ):
        await hass.services.async_call(
            "lock",
            SERVICE_LOCK,
            {
                ATTR_ENTITY_ID: MOCK_LOCK_ENTITY_ID,
            },
            blocking=True,
        )

        await hass.services.async_call(
            "lock",
            SERVICE_UNLOCK,
            {
                ATTR_ENTITY_ID: MOCK_LOCK_ENTITY_ID,
            },
            blocking=True,
        )

    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_lock_class_connection_error(hass: HomeAssistant) -> None:
    """Test wallbox lock class connection error."""

    try:
        assert await hass.config_entries.async_unload(entry.entry_id)
    except (UnknownEntry):
        pass

    await setup_integration(hass)

    with patch("wallbox.Wallbox.authenticate", return_value=None,), patch(
        "wallbox.Wallbox.lockCharger",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.NOT_FOUND),
            response=Mock(status_code=HTTPStatus.NOT_FOUND),
        ),
    ), patch(
        "wallbox.Wallbox.unlockCharger",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.NOT_FOUND),
            response=Mock(status_code=HTTPStatus.NOT_FOUND),
        ),
    ):

        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                "lock",
                SERVICE_LOCK,
                {
                    ATTR_ENTITY_ID: MOCK_LOCK_ENTITY_ID,
                },
                blocking=True,
            )
        with pytest.raises(ConnectionError):
            await hass.services.async_call(
                "lock",
                SERVICE_UNLOCK,
                {
                    ATTR_ENTITY_ID: MOCK_LOCK_ENTITY_ID,
                },
                blocking=True,
            )

    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_lock_class_unauthorized_error(hass: HomeAssistant) -> None:
    """Test wallbox lock class unauthorized error."""

    try:
        assert await hass.config_entries.async_unload(entry.entry_id)
    except (UnknownEntry):
        pass

    await setup_integration(hass)

    with patch("wallbox.Wallbox.authenticate", return_value=None,), patch(
        "wallbox.Wallbox.lockCharger",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.FORBIDDEN),
            response=Mock(status_code=HTTPStatus.FORBIDDEN),
        ),
    ), patch(
        "wallbox.Wallbox.unlockCharger",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.FORBIDDEN),
            response=Mock(status_code=HTTPStatus.FORBIDDEN),
        ),
    ):

        with pytest.raises(InvalidAuth):
            await hass.services.async_call(
                "lock",
                SERVICE_LOCK,
                {
                    ATTR_ENTITY_ID: MOCK_LOCK_ENTITY_ID,
                },
                blocking=True,
            )
        with pytest.raises(InvalidAuth):
            await hass.services.async_call(
                "lock",
                SERVICE_UNLOCK,
                {
                    ATTR_ENTITY_ID: MOCK_LOCK_ENTITY_ID,
                },
                blocking=True,
            )

    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_lock_class_authentication_error(hass: HomeAssistant) -> None:
    """Test wallbox lock not loaded on authentication error."""

    try:
        assert await hass.config_entries.async_unload(entry.entry_id)
    except (UnknownEntry):
        pass

    await setup_integration_no_lock_auth(hass)

    state = hass.states.get(MOCK_LOCK_ENTITY_ID)

    assert state is None

    await hass.config_entries.async_unload(entry.entry_id)
