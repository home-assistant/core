"""Tests for the OpenEVSE sensor platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.openevse.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
def mock_charger():
    """Create a mock OpenEVSE charger."""
    with patch(
        "homeassistant.components.openevse.config_flow.openevsewifi.Charger"
    ) as mock:
        charger = MagicMock()
        charger.getStatus.return_value = "Charging"
        charger.getChargeTimeElapsed.return_value = 3600  # 60 minutes in seconds
        charger.getAmbientTemperature.return_value = 25.5
        charger.getIRTemperature.return_value = 30.2
        charger.getRTCTemperature.return_value = 28.7
        charger.getUsageSession.return_value = 15000  # 15 kWh in Wh
        charger.getUsageTotal.return_value = 500000  # 500 kWh in Wh
        charger.charging_current = 32.0
        mock.return_value = charger
        yield charger


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.mpd.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_user_flow(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenEVSE 10.0.0.131"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
    }


async def test_import_flow(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenEVSE 10.0.0.131"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
    }
