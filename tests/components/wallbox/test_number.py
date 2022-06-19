"""Test Wallbox Switch component."""
from http import HTTPStatus
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import HTTPError

from homeassistant.components.input_number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.config_entries import UnknownEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import entry, setup_integration, setup_integration_no_set_charger_auth
from .const import MOCK_NUMBER_ENTITY_ID


async def test_wallbox_number_class(hass: HomeAssistant) -> None:
    """Test wallbox number class."""

    try:
        assert await hass.config_entries.async_unload(entry.entry_id)
    except (UnknownEntry):
        pass

    await setup_integration(hass)

    with patch("wallbox.Wallbox.authenticate", return_value=None,), patch(
        "wallbox.Wallbox.lockCharger",
        return_value=None,
    ), patch(
        "wallbox.Wallbox.setMaxChargingCurrent",
        return_value=None,
    ):

        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ID,
                ATTR_VALUE: 20,
            },
            blocking=True,
        )
    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_number_class_connection_error(hass: HomeAssistant) -> None:
    """Test wallbox number class connection error."""

    try:
        assert await hass.config_entries.async_unload(entry.entry_id)
    except (UnknownEntry):
        pass

    await setup_integration(hass)

    with patch("wallbox.Wallbox.authenticate", return_value=None,), patch(
        "wallbox.Wallbox.lockCharger",
        return_value=None,
    ), patch(
        "wallbox.Wallbox.setMaxChargingCurrent",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.NOT_FOUND),
            response=Mock(status_code=HTTPStatus.NOT_FOUND),
        ),
    ):

        with pytest.raises(ConnectionError):

            await hass.services.async_call(
                "number",
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ID,
                    ATTR_VALUE: 20,
                },
                blocking=True,
            )
    await hass.config_entries.async_unload(entry.entry_id)


async def test_wallbox_number_class_authentication_error(hass: HomeAssistant) -> None:
    """Test wallbox number not loaded on authentication error."""

    try:
        assert await hass.config_entries.async_unload(entry.entry_id)
    except (UnknownEntry):
        pass

    await setup_integration_no_set_charger_auth(hass)

    state = hass.states.get(MOCK_NUMBER_ENTITY_ID)

    assert state is None

    await hass.config_entries.async_unload(entry.entry_id)
