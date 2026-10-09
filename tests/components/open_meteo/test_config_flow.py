"""Tests for the Open-Meteo config flow."""

from unittest.mock import MagicMock

from open_meteo import OpenMeteoConnectionError
import pytest

from homeassistant.components.open_meteo.const import DOMAIN
from homeassistant.components.zone import ENTITY_ID_HOME
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_user_flow(hass: HomeAssistant, mock_open_meteo: MagicMock) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ZONE: ENTITY_ID_HOME},
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "test home"
    assert result2.get("data") == {CONF_ZONE: ENTITY_ID_HOME}

    assert len(mock_open_meteo.forecast.mock_calls) == 1
    _, _, kwargs = mock_open_meteo.forecast.mock_calls[0]
    zone = hass.states.get(ENTITY_ID_HOME)
    assert zone is not None
    assert kwargs["latitude"] == zone.attributes["latitude"]
    assert kwargs["longitude"] == zone.attributes["longitude"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_cannot_connect(
    hass: HomeAssistant, mock_open_meteo: MagicMock
) -> None:
    """Test the flow shows an error when Open-Meteo can't be reached, and recovers."""
    mock_open_meteo.forecast.side_effect = OpenMeteoConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_ZONE: ENTITY_ID_HOME},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}

    mock_open_meteo.forecast.side_effect = None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ZONE: ENTITY_ID_HOME},
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "test home"


@pytest.mark.usefixtures("mock_setup_entry", "mock_open_meteo")
async def test_flow_zone_not_found(hass: HomeAssistant) -> None:
    """Test the flow shows an error for a zone that does not exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_ZONE: "zone.gone"},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {CONF_ZONE: "zone_not_found"}


@pytest.mark.usefixtures("mock_setup_entry", "mock_open_meteo")
async def test_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts for a zone that is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_ZONE: ENTITY_ID_HOME},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
