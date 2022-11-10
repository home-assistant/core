"""Tests for setup and unload of component."""
from __future__ import annotations

from unittest.mock import ANY, AsyncMock, Mock

from combined_energy.exceptions import CombinedEnergyAuthError, CombinedEnergyError
import pytest

from homeassistant.components import combined_energy
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady


@pytest.fixture
def config_entry():
    """Generate a config entry for tests."""
    return ConfigEntry(
        1,
        combined_energy.DOMAIN,
        "Test",
        data={
            combined_energy.CONF_USERNAME: "user@example.test",
            combined_energy.CONF_PASSWORD: "1234luggage",
            combined_energy.CONF_INSTALLATION_ID: 999999999,
        },
        source="TestSource",
        entry_id="beef",
    )


@pytest.fixture
def mock_api_instance(monkeypatch):
    """Generate a mock CombinedEnergy API."""
    mock_api_instance = AsyncMock(combined_energy.CombinedEnergy)
    mock_api_type = Mock(return_value=mock_api_instance)
    monkeypatch.setattr(combined_energy, "CombinedEnergy", mock_api_type)
    return mock_api_instance


async def test_async_setup_entry__where_component_is_successfully_registered(
    hass: HomeAssistant, config_entry: ConfigEntry, monkeypatch
):
    """Check that component is successfully configured and registered."""
    mock_api_instance = AsyncMock(
        combined_energy.CombinedEnergy,
        installation=AsyncMock(return_value="AnInstallation"),
    )
    mock_api_type = Mock(return_value=mock_api_instance)
    monkeypatch.setattr(combined_energy, "CombinedEnergy", mock_api_type)

    actual = await combined_energy.async_setup_entry(hass, config_entry)

    assert actual is True
    mock_api_type.assert_called_with(
        mobile_or_email="user@example.test",
        password="1234luggage",
        installation_id=999999999,
        session=ANY,
    )
    assert (
        hass.data["combined_energy"]["beef"][combined_energy.DATA_API_CLIENT]
        == mock_api_instance
    )
    assert (
        hass.data["combined_energy"]["beef"][combined_energy.DATA_INSTALLATION]
        == "AnInstallation"
    )


async def test_async_setup_entry__where_authentication_fails(
    hass: HomeAssistant, config_entry: ConfigEntry, mock_api_instance
) -> None:
    """If an api auth error triggers a ConfigEntryAuthFailed exception to be raised."""

    mock_api_instance.installation = AsyncMock(side_effect=CombinedEnergyAuthError)

    with pytest.raises(ConfigEntryAuthFailed):
        await combined_energy.async_setup_entry(hass, config_entry)


async def test_async_setup_entry__where_connection_fails(
    hass: HomeAssistant, config_entry: ConfigEntry, mock_api_instance
):
    """If an api error triggers a ConfigEntryNotReady exception to be raised."""
    mock_api_instance.installation = AsyncMock(side_effect=CombinedEnergyError)

    with pytest.raises(ConfigEntryNotReady):
        await combined_energy.async_setup_entry(hass, config_entry)


async def test_async_unload_entry__where_component_is_successfully_unloaded(
    hass: HomeAssistant, config_entry: ConfigEntry
):
    """Check that component is successfully unloaded."""
    hass.data["combined_energy"] = {
        config_entry.entry_id: {combined_energy.DATA_API_CLIENT: "API_CLIENT"}
    }

    actual = await combined_energy.async_unload_entry(hass, config_entry)

    assert actual is not None
    assert hass.data["combined_energy"] == {}
