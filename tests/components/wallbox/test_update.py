"""Test Wallbox Update component."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, HomeAssistantError

from . import (
    authorisation_response,
    http_404_error,
    setup_integration_update_available,
    test_response,
)
from .const import MOCK_UPDATE_ENTITY_ID

from tests.common import MockConfigEntry


async def test_wallbox_update_class(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox update class."""

    await setup_integration_update_available(hass, entry)

    state = hass.states.get(MOCK_UPDATE_ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "5.5.9"
    assert state.attributes[ATTR_LATEST_VERSION] == "5.5.10"

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.updateFirmware",
            new=Mock(return_value=test_response),
        ),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: MOCK_UPDATE_ENTITY_ID},
            blocking=True,
        )

        state = hass.states.get(MOCK_UPDATE_ENTITY_ID)
        assert state
        assert state.state == STATE_OFF
        assert (
            state.attributes[ATTR_INSTALLED_VERSION]
            == state.attributes[ATTR_LATEST_VERSION]
        )


async def test_wallbox_update_class_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox update class connection error."""

    await setup_integration_update_available(hass, entry)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.updateFirmware",
            new=Mock(side_effect=http_404_error),
        ),
        pytest.raises(HomeAssistantError),
    ):
        # Test behavior when a connection error occurs
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: MOCK_UPDATE_ENTITY_ID},
            blocking=True,
        )


async def test_wallbox_update_class_authentication_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox update class authentication error."""

    await setup_integration_update_available(hass, entry)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.updateFirmware",
            new=Mock(side_effect=ConnectionError),
        ),
        pytest.raises(HomeAssistantError),
    ):
        # Test behavior when a connection error occurs
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: MOCK_UPDATE_ENTITY_ID},
            blocking=True,
        )
