"""Test Linksys Smart Wi-Fi integration setup."""

from unittest.mock import ANY, AsyncMock, patch

from jnap import GetDevicesResponse
import pytest

from homeassistant.components.linksys_smart.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
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

    with patch("homeassistant.components.linksys_smart.JNAPClient") as mock_client_cls:
        mock_client_cls.return_value.get_devices = AsyncMock(
            return_value=GetDevicesResponse(devices=[])
        )
        assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == ConfigEntryState.LOADED
    mock_client_cls.assert_called_once_with(
        entry_data[CONF_HOST], ANY, entry_data[CONF_PASSWORD], **expected_kwargs
    )


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

    with patch("homeassistant.components.linksys_smart.JNAPClient") as mock_client_cls:
        mock_client_cls.return_value.get_devices = AsyncMock(
            return_value=GetDevicesResponse(devices=[])
        )
        assert await hass.config_entries.async_setup(entry.entry_id)

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED
