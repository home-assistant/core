"""Test Wallbox Switch component."""

from unittest.mock import patch

import pytest

from homeassistant.components.input_number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.wallbox.coordinator import InsufficientRights
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import http_403_error, http_404_error, http_429_error, setup_integration
from .const import (
    MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
    MOCK_NUMBER_ENTITY_ICP_CURRENT_ID,
    MOCK_NUMBER_ENTITY_ID,
    WALLBOX_STATUS_RESPONSE_BIDIR,
)

from tests.common import MockConfigEntry


async def test_wallbox_number_power_class(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test wallbox sensor class."""
    await setup_integration(hass, entry)

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


async def test_wallbox_number_power_class_bidir(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test wallbox sensor class."""
    with patch.object(
        mock_wallbox, "getChargerStatus", return_value=WALLBOX_STATUS_RESPONSE_BIDIR
    ):
        await setup_integration(hass, entry)

        state = hass.states.get(MOCK_NUMBER_ENTITY_ID)
        assert state.attributes["min"] == -25
        assert state.attributes["max"] == 25


async def test_wallbox_number_energy_class(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
            ATTR_VALUE: 1.1,
        },
        blocking=True,
    )


async def test_wallbox_number_icp_power_class(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ICP_CURRENT_ID,
            ATTR_VALUE: 10,
        },
        blocking=True,
    )


async def test_wallbox_number_power_class_error_handling(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with (
        patch.object(mock_wallbox, "setMaxChargingCurrent", side_effect=http_404_error),
        pytest.raises(HomeAssistantError),
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

    with (
        patch.object(mock_wallbox, "setMaxChargingCurrent", side_effect=http_429_error),
        pytest.raises(HomeAssistantError),
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

    with (
        patch.object(mock_wallbox, "setMaxChargingCurrent", side_effect=http_403_error),
        pytest.raises(InsufficientRights),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: MOCK_NUMBER_ENTITY_ID,
                ATTR_VALUE: 10,
            },
            blocking=True,
        )


async def test_wallbox_number_energy_class_error_handling(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with (
        patch.object(mock_wallbox, "setEnergyCost", side_effect=http_429_error),
        pytest.raises(HomeAssistantError),
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

    with (
        patch.object(mock_wallbox, "setEnergyCost", side_effect=http_404_error),
        pytest.raises(HomeAssistantError),
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

    with (
        patch.object(mock_wallbox, "setEnergyCost", side_effect=http_429_error),
        pytest.raises(HomeAssistantError),
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


async def test_wallbox_number_icp_power_class_error_handling(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test wallbox sensor class."""

    await setup_integration(hass, entry)

    with (
        patch.object(mock_wallbox, "setIcpMaxCurrent", side_effect=http_403_error),
        pytest.raises(InsufficientRights),
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

    with (
        patch.object(mock_wallbox, "setIcpMaxCurrent", side_effect=http_404_error),
        pytest.raises(HomeAssistantError),
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

    with (
        patch.object(mock_wallbox, "setIcpMaxCurrent", side_effect=http_429_error),
        pytest.raises(HomeAssistantError),
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
