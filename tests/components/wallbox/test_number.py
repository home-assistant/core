"""Test Wallbox Switch component."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.input_number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.wallbox.const import (
    CHARGER_ENERGY_PRICE_KEY,
    CHARGER_MAX_CHARGING_CURRENT_KEY,
    CHARGER_MAX_ICP_CURRENT_KEY,
)
from homeassistant.components.wallbox.coordinator import InvalidAuth
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from . import (
    authorisation_response,
    http_403_error,
    http_404_error,
    setup_integration,
    setup_integration_bidir,
    setup_integration_platform_not_ready,
)
from .const import (
    MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
    MOCK_NUMBER_ENTITY_ICP_CURRENT_ID,
    MOCK_NUMBER_ENTITY_ID,
)

from tests.common import MockConfigEntry

mock_wallbox = Mock()
mock_wallbox.authenticate = Mock(return_value=authorisation_response)
mock_wallbox.setEnergyCost = Mock(return_value={CHARGER_ENERGY_PRICE_KEY: 1.1})
mock_wallbox.setMaxChargingCurrent = Mock(
    return_value={CHARGER_MAX_CHARGING_CURRENT_KEY: 20}
)
mock_wallbox.setIcpMaxCurrent = Mock(return_value={CHARGER_MAX_ICP_CURRENT_KEY: 10})


async def test_wallbox_number_class(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.setMaxChargingCurrent",
            new=Mock(return_value={CHARGER_MAX_CHARGING_CURRENT_KEY: 20}),
        ),
    ):
        state = hass.states.get(MOCK_NUMBER_ENTITY_ID)
        assert state.attributes["min"] == 6
        assert state.attributes["max"] == 25

        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ID,
                ATTR_VALUE: 20,
            },
            blocking=True,
        )


async def test_wallbox_number_class_bidir(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration_bidir(hass, entry)

    state = hass.states.get(MOCK_NUMBER_ENTITY_ID)
    assert state.attributes["min"] == -25
    assert state.attributes["max"] == 25


async def test_wallbox_number_energy_class(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.setEnergyCost",
            new=Mock(return_value={CHARGER_ENERGY_PRICE_KEY: 1.1}),
        ),
    ):
        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
                ATTR_VALUE: 1.1,
            },
            blocking=True,
        )


async def test_wallbox_number_class_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.setMaxChargingCurrent",
            new=Mock(side_effect=http_404_error),
        ),
        pytest.raises(ConnectionError),
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


async def test_wallbox_number_class_energy_price_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.setEnergyCost",
            new=Mock(side_effect=http_404_error),
        ),
        pytest.raises(ConnectionError),
    ):
        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
                ATTR_VALUE: 1.1,
            },
            blocking=True,
        )


async def test_wallbox_number_class_energy_price_auth_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.setEnergyCost",
            new=Mock(side_effect=http_403_error),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
                ATTR_VALUE: 1.1,
            },
            blocking=True,
        )


async def test_wallbox_number_class_platform_not_ready(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox lock not loaded on authentication error."""

    await setup_integration_platform_not_ready(hass, entry)

    state = hass.states.get(MOCK_NUMBER_ENTITY_ID)

    assert state is None


async def test_wallbox_number_class_icp_energy(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.setIcpMaxCurrent",
            new=Mock(return_value={CHARGER_MAX_ICP_CURRENT_KEY: 10}),
        ),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ICP_CURRENT_ID,
                ATTR_VALUE: 10,
            },
            blocking=True,
        )


async def test_wallbox_number_class_icp_energy_auth_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.setIcpMaxCurrent",
            new=Mock(side_effect=http_403_error),
        ),
        pytest.raises(InvalidAuth),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ICP_CURRENT_ID,
                ATTR_VALUE: 10,
            },
            blocking=True,
        )


async def test_wallbox_number_class_icp_energy_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.setIcpMaxCurrent",
            new=Mock(side_effect=http_404_error),
        ),
        pytest.raises(ConnectionError),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ICP_CURRENT_ID,
                ATTR_VALUE: 10,
            },
            blocking=True,
        )
