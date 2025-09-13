"""Test the Leneda config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from leneda.exceptions import ForbiddenException, UnauthorizedException
from leneda.obis_codes import ObisCode
import pytest

from homeassistant import config_entries
from homeassistant.components.leneda.const import CONF_API_TOKEN, CONF_ENERGY_ID, DOMAIN
from homeassistant.components.recorder.core import Recorder
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

# Mock values for testing
MOCK_API_TOKEN = "test_api_token"
MOCK_ENERGY_ID = "test_energy_id"
MOCK_METERING_POINT = "MP001"
MOCK_OBIS_CODES = [ObisCode.ELEC_CONSUMPTION_ACTIVE, ObisCode.GAS_CONSUMPTION_VOLUME]
MOCK_NEW_API_TOKEN = "new_test_api_token"


@pytest.fixture(autouse=True)
async def recorder_mock(
    recorder_mock: Recorder,
    hass: HomeAssistant,
) -> None:
    """Set up the recorder with a temporary SQLite database."""
    await hass.async_block_till_done()


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_ENERGY_ID: MOCK_ENERGY_ID,
        },
        options={},
        unique_id=MOCK_ENERGY_ID,
    )


async def test_form_user_success(hass: HomeAssistant, recorder_mock: Recorder) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.probe_metering_point_obis_code",
        new_callable=AsyncMock,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: MOCK_API_TOKEN,
                CONF_ENERGY_ID: MOCK_ENERGY_ID,
            },
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == MOCK_ENERGY_ID
    assert result2["data"] == {
        CONF_API_TOKEN: MOCK_API_TOKEN,
        CONF_ENERGY_ID: MOCK_ENERGY_ID,
    }


async def test_form_user_unauthorized(
    hass: HomeAssistant, recorder_mock: Recorder
) -> None:
    """Test user flow with unauthorized error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.probe_metering_point_obis_code",
        new_callable=AsyncMock,
        side_effect=UnauthorizedException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: MOCK_API_TOKEN,
                CONF_ENERGY_ID: MOCK_ENERGY_ID,
            },
        )

        assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unauthorized"}


async def test_form_user_forbidden(
    hass: HomeAssistant, recorder_mock: Recorder
) -> None:
    """Test user flow with forbidden error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.probe_metering_point_obis_code",
        new_callable=AsyncMock,
        side_effect=ForbiddenException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: MOCK_API_TOKEN,
                CONF_ENERGY_ID: MOCK_ENERGY_ID,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "forbidden"}


async def test_form_user_duplicate(
    hass: HomeAssistant, recorder_mock: Recorder, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow with duplicate entry."""
    # Add a mock existing entry
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.probe_metering_point_obis_code",
        new_callable=AsyncMock,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: MOCK_API_TOKEN,
                CONF_ENERGY_ID: MOCK_ENERGY_ID,
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reauth_success(
    hass: HomeAssistant, recorder_mock: Recorder, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful reauthentication flow."""
    # Add a mock existing entry
    mock_config_entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.probe_metering_point_obis_code",
        new_callable=AsyncMock,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: MOCK_NEW_API_TOKEN,
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    # Verify the config entry was updated with the new token
    assert mock_config_entry.data[CONF_API_TOKEN] == MOCK_NEW_API_TOKEN


async def test_reauth_unauthorized(
    hass: HomeAssistant, recorder_mock: Recorder, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauthentication flow with unauthorized error."""
    # Add a mock existing entry
    mock_config_entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.probe_metering_point_obis_code",
        new_callable=AsyncMock,
        side_effect=UnauthorizedException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: MOCK_NEW_API_TOKEN,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"] == {"base": "unauthorized"}

    # Verify the config entry was not updated
    assert mock_config_entry.data[CONF_API_TOKEN] == MOCK_API_TOKEN


async def test_reauth_forbidden(
    hass: HomeAssistant, recorder_mock: Recorder, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauthentication flow with forbidden error."""
    # Add a mock existing entry
    mock_config_entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.probe_metering_point_obis_code",
        new_callable=AsyncMock,
        side_effect=ForbiddenException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: MOCK_NEW_API_TOKEN,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"] == {"base": "forbidden"}

    # Verify the config entry was not updated
    assert mock_config_entry.data[CONF_API_TOKEN] == MOCK_API_TOKEN


async def test_reauth_flow_description(
    hass: HomeAssistant, recorder_mock: Recorder, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauthentication flow description contains energy ID."""
    # Add a mock existing entry
    mock_config_entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert "energy_id" in result["description_placeholders"]
    assert result["description_placeholders"]["energy_id"] == MOCK_ENERGY_ID
