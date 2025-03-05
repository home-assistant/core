from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.adax.const import (
    ACCOUNT_ID,
    CLOUD,
    CONNECTION_TYPE,
    LOCAL,
)
from homeassistant.components.adax.coordinator import (
    AdaxCloudCoordinator,
    AdaxLocalCoordinator,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_adax_cloud_coordinator(hass: HomeAssistant) -> None:
    """Test AdaxCloudCoordinator."""
    mock_config_entry = MockConfigEntry(
        domain="adax",
        data={
            CONNECTION_TYPE: CLOUD,
            ACCOUNT_ID: "test_account_id",
            CONF_PASSWORD: "test_password",
        },
    )
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.adax.coordinator.Adax",
    ) as mock_adax_class:
        mock_adax = mock_adax_class.return_value
        mock_adax.get_rooms = AsyncMock(return_value=[{"id": 1, "name": "Room 1"}])

        coordinator = AdaxCloudCoordinator(hass, mock_config_entry)
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.data == [{"id": 1, "name": "Room 1"}]
        mock_adax_class.assert_called_once_with(
            "test_account_id",
            "test_password",
            websession=async_get_clientsession(hass),
        )
        mock_adax.get_rooms.assert_called_once()

        room = coordinator.get_room(1)
        assert room == {"id": 1, "name": "Room 1"}

        room = coordinator.get_room(2)
        assert room is None

        mock_adax.get_rooms = AsyncMock(side_effect=Exception)
        with pytest.raises(UpdateFailed):
            await coordinator.async_refresh()


async def test_adax_local_coordinator(hass: HomeAssistant) -> None:
    """Test AdaxLocalCoordinator."""
    mock_config_entry = MockConfigEntry(
        domain="adax",
        data={
            CONNECTION_TYPE: LOCAL,
            CONF_IP_ADDRESS: "192.168.1.101",
            CONF_TOKEN: "test_token",
        },
    )
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.adax.coordinator.AdaxLocal",
    ) as mock_adax_class:
        mock_adax = mock_adax_class.return_value
        mock_adax.get_status = AsyncMock(return_value={"id": 1, "name": "Room 1"})

        coordinator = AdaxLocalCoordinator(hass, mock_config_entry)
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.data == {"id": 1, "name": "Room 1"}
        mock_adax_class.assert_called_once_with(
            "192.168.1.101",
            "test_token",
            websession=async_get_clientsession(hass, verify_ssl=False),
        )
        mock_adax.get_status.assert_called_once()

        mock_adax.get_status = AsyncMock(return_value=None)
        await coordinator.async_refresh()
        assert coordinator.data is None

        mock_adax.get_status = AsyncMock(side_effect=Exception)
        with pytest.raises(UpdateFailed):
            await coordinator.async_refresh()
