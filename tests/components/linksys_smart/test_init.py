"""Test the linksys init."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import linksys_smart
from homeassistant.components.linksys_smart.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("entry_data", "expected_kwargs"),
    [
        pytest.param(
            {
                CONF_HOST: "192.168.1.1",
                CONF_PASSWORD: "password",
            },
            {},
            id="without_username",
        ),
        pytest.param(
            {
                CONF_HOST: "192.168.1.1",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password",
            },
            {"username": "admin"},
            id="with_username",
        ),
    ],
)
async def test_async_setup_entry(
    hass: HomeAssistant,
    entry_data: dict[str, str],
    expected_kwargs: dict[str, str],
) -> None:
    """Test setting up the integration."""
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    entry.add_to_hass(hass)

    session = object()
    coordinator = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch.object(linksys_smart, "async_get_clientsession", return_value=session),
        patch.object(linksys_smart, "JNAPClient") as mock_client,
        patch.object(
            linksys_smart, "LinksysDataUpdateCoordinator", return_value=coordinator
        ) as mock_coordinator,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(return_value=True),
        ) as mock_forward_entry_setups,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    mock_client.assert_called_once_with(
        entry_data[CONF_HOST], session, entry_data[CONF_PASSWORD], **expected_kwargs
    )
    mock_coordinator.assert_called_once_with(hass, entry, mock_client.return_value)
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    mock_forward_entry_setups.assert_awaited_once_with(entry, [Platform.DEVICE_TRACKER])
    assert entry.runtime_data is coordinator


async def test_async_unload_entry(
    hass: HomeAssistant,
) -> None:
    """Test unloading the integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.1",
            CONF_PASSWORD: "password",
        },
    )
    entry.add_to_hass(hass)

    coordinator = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch.object(linksys_smart, "async_get_clientsession", return_value=object()),
        patch.object(linksys_smart, "JNAPClient"),
        patch.object(
            linksys_smart, "LinksysDataUpdateCoordinator", return_value=coordinator
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new=AsyncMock(return_value=True),
    ) as mock_unload_platforms:
        assert await hass.config_entries.async_unload(entry.entry_id)

    mock_unload_platforms.assert_awaited_once_with(entry, [Platform.DEVICE_TRACKER])
