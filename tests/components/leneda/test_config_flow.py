"""Test the Leneda config flow."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from leneda.exceptions import ForbiddenException, UnauthorizedException
import pytest

from homeassistant import config_entries
from homeassistant.components.leneda.const import (
    CONF_API_TOKEN,
    CONF_ENERGY_ID,
    CONF_METERING_POINTS,
    DOMAIN,
)
from homeassistant.components.recorder.core import Recorder
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

# Mock values for testing
MOCK_API_TOKEN = "test_api_token"
MOCK_ENERGY_ID = "test_energy_id"
MOCK_METERING_POINT = "MP001"
MOCK_METERING_POINTS = [MOCK_METERING_POINT]
MOCK_OBIS_CODES = ["1.8.0", "2.8.0", "7.8.0"]  # Example OBIS codes


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
            CONF_METERING_POINTS: MOCK_METERING_POINTS,
        },
        options={},
        unique_id=MOCK_ENERGY_ID,
    )


async def test_form_user_no_existing_entries(
    hass: HomeAssistant, recorder_mock: Recorder
) -> None:
    """Test we get the form with no existing entries."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Should go directly to new credentials form
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "new_credentials"


async def test_form_user_with_existing_entries(
    hass: HomeAssistant, recorder_mock: Recorder
) -> None:
    """Test we get the form with existing entries."""
    # Add a mock existing entry
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_ENERGY_ID: MOCK_ENERGY_ID,
            CONF_METERING_POINTS: [MOCK_METERING_POINT],
        },
        options={},
        unique_id=MOCK_ENERGY_ID,
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Should show menu with options
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "user"
    assert "new_credentials" in result["menu_options"]
    assert "select_existing" in result["menu_options"]


async def test_form_new_credentials(
    hass: HomeAssistant, recorder_mock: Recorder
) -> None:
    """Test we can create a new config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "new_credentials"

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.get_supported_obis_codes",
        return_value=MOCK_OBIS_CODES,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: MOCK_API_TOKEN,
                CONF_ENERGY_ID: MOCK_ENERGY_ID,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "add_metering_point"


async def test_form_select_existing(
    hass: HomeAssistant, recorder_mock: Recorder
) -> None:
    """Test selecting an existing configuration."""
    # Add a mock existing entry
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_ENERGY_ID: MOCK_ENERGY_ID,
            CONF_METERING_POINTS: [MOCK_METERING_POINT],
        },
        options={},
        unique_id=MOCK_ENERGY_ID,
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.MENU

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "select_existing"}
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "select_existing"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], {"existing_energy_id": MOCK_ENERGY_ID}
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "add_metering_point"


async def test_form_add_metering_point(
    hass: HomeAssistant, recorder_mock: Recorder
) -> None:
    """Test adding a metering point."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.get_supported_obis_codes",
        return_value=MOCK_OBIS_CODES,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: MOCK_API_TOKEN,
                CONF_ENERGY_ID: MOCK_ENERGY_ID,
            },
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == "add_metering_point"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"metering_point": MOCK_METERING_POINT}
        )

    assert result3["type"] == FlowResultType.MENU
    assert result3["step_id"] == "setup_type"
    assert "probe" in result3["menu_options"]
    assert "manual" in result3["menu_options"]


async def test_form_probe_success(hass: HomeAssistant, recorder_mock: Recorder) -> None:
    """Test successful probing of metering point."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    future: asyncio.Future = asyncio.Future()

    with (
        patch(
            "homeassistant.components.leneda.config_flow.LenedaClient.get_supported_obis_codes",
            return_value=future,
        ),
        patch.object(hass, "async_add_executor_job", return_value=future),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: MOCK_API_TOKEN,
                CONF_ENERGY_ID: MOCK_ENERGY_ID,
            },
        )

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"metering_point": MOCK_METERING_POINT}
        )

        assert result3["type"] == FlowResultType.MENU
        assert result3["step_id"] == "setup_type"

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], {"next_step_id": "probe"}
        )

        # Should show progress
        assert result4["type"] == FlowResultType.SHOW_PROGRESS
        assert result4["progress_action"] == "fetch_obis"

        # Complete the probing
        future.set_result(MOCK_OBIS_CODES)
        await hass.async_block_till_done()
        result5 = await hass.config_entries.flow.async_configure(
            result4["flow_id"], {"next_step_id": "manual"}
        )

        # Should show manual setup with pre-selected sensors
        assert result5["type"] == FlowResultType.FORM
        assert result5["step_id"] == "manual"
        assert result5["description_placeholders"] is not None
        assert "probed_text" in result5["description_placeholders"]


async def test_form_probe_no_sensors(
    hass: HomeAssistant, recorder_mock: Recorder
) -> None:
    """Test probing with no sensors found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    future: asyncio.Future = asyncio.Future()

    with (
        patch(
            "homeassistant.components.leneda.config_flow.LenedaClient.get_supported_obis_codes",
            return_value=future,
        ),
        patch.object(hass, "async_add_executor_job", return_value=future),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: MOCK_API_TOKEN,
                CONF_ENERGY_ID: MOCK_ENERGY_ID,
            },
        )

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"metering_point": MOCK_METERING_POINT}
        )

        assert result3["type"] == FlowResultType.MENU
        assert result3["step_id"] == "setup_type"

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], {"next_step_id": "probe"}
        )

        # Should show progress
        assert result4["type"] == FlowResultType.SHOW_PROGRESS
        assert result4["progress_action"] == "fetch_obis"

        # Complete the probing
        future.set_result([])
        await hass.async_block_till_done()
        result5 = await hass.config_entries.flow.async_configure(
            result4["flow_id"], {"next_step_id": "probe_no_sensors"}
        )

        # Should show menu with manual option
        assert result5["type"] == FlowResultType.MENU
        assert result5["step_id"] == "probe_no_sensors"
        assert "manual" in result5["menu_options"]


async def test_form_manual_setup(hass: HomeAssistant, recorder_mock: Recorder) -> None:
    """Test manual sensor setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.get_supported_obis_codes",
        return_value=MOCK_OBIS_CODES,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: MOCK_API_TOKEN,
                CONF_ENERGY_ID: MOCK_ENERGY_ID,
            },
        )

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"metering_point": MOCK_METERING_POINT}
        )

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], {"next_step_id": "manual"}
        )

        # Should show manual setup form
        assert result4["type"] == FlowResultType.FORM
        assert result4["step_id"] == "manual"

        # Complete the manual setup
        result5 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            {"sensors": ["electricity_consumption_active", "gas_consumption_volume"]},
        )

        assert result5["type"] == FlowResultType.MENU
        assert result5["step_id"] == "metering_points_summary"
        assert "add_metering_point" in result5["menu_options"]
        assert "finish" in result5["menu_options"]

        # Finish the setup
        result6 = await hass.config_entries.flow.async_configure(
            result5["flow_id"], {"next_step_id": "finish"}
        )

    assert result6["type"] == FlowResultType.CREATE_ENTRY
    assert result6["title"] == MOCK_ENERGY_ID

    # Verify data only contains the required configuration
    assert result6["data"] == {
        CONF_API_TOKEN: MOCK_API_TOKEN,
        CONF_ENERGY_ID: MOCK_ENERGY_ID,
        CONF_METERING_POINTS: [MOCK_METERING_POINT],
    }

    # Verify selected sensors are stored in options
    assert result6["options"] == {
        "selected_sensors": {
            MOCK_METERING_POINT: [
                "electricity_consumption_active",
                "gas_consumption_volume",
            ]
        }
    }

    # Verify the config entry is properly set up
    config_entry = hass.config_entries.async_get_entry(result6["result"].entry_id)
    assert config_entry is not None
    assert config_entry.data == result6["data"]
    assert config_entry.options == result6["options"]


async def test_duplicate_metering_point(
    hass: HomeAssistant, recorder_mock: Recorder
) -> None:
    """Test error when adding duplicate metering point."""
    # Add a mock existing entry
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_ENERGY_ID: MOCK_ENERGY_ID,
            CONF_METERING_POINTS: [MOCK_METERING_POINT],
        },
        options={},
        unique_id=MOCK_ENERGY_ID,
    )
    mock_entry.add_to_hass(hass)

    # Try to add the same metering point
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select new_credentials option
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "new_credentials"},
    )

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.get_supported_obis_codes",
        return_value=MOCK_OBIS_CODES,
    ):
        # Enter new credentials
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_API_TOKEN: "another_token",
                CONF_ENERGY_ID: "another_energy_id",
            },
        )

        # Try to add the same metering point
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], {"metering_point": MOCK_METERING_POINT}
        )

    assert result4["type"] == FlowResultType.FORM
    assert result4["errors"] is not None
    if result4["errors"] is not None and "base" in result4["errors"]:
        assert result4["errors"]["base"] == "duplicate_metering_point"


async def test_forbidden_error(hass: HomeAssistant, recorder_mock: Recorder) -> None:
    """Test error when API returns forbidden."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.get_supported_obis_codes",
        side_effect=ForbiddenException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: MOCK_API_TOKEN,
                CONF_ENERGY_ID: MOCK_ENERGY_ID,
            },
        )

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"metering_point": MOCK_METERING_POINT}
        )

        assert result3["type"] == FlowResultType.MENU
        assert result3["step_id"] == "setup_type"

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], {"next_step_id": "probe"}
        )

        assert result4["type"] == FlowResultType.ABORT
        assert result4["reason"] == "forbidden"


async def test_unauthorized_error(hass: HomeAssistant, recorder_mock: Recorder) -> None:
    """Test error when API returns unauthorized."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.get_supported_obis_codes",
        side_effect=UnauthorizedException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: MOCK_API_TOKEN,
                CONF_ENERGY_ID: MOCK_ENERGY_ID,
            },
        )

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"metering_point": MOCK_METERING_POINT}
        )

        assert result3["type"] == FlowResultType.MENU
        assert result3["step_id"] == "setup_type"

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], {"next_step_id": "probe"}
        )

        assert result4["type"] == FlowResultType.ABORT
        assert result4["reason"] == "unauthorized"


async def test_unknown_error(hass: HomeAssistant, recorder_mock: Recorder) -> None:
    """Test error when an unknown error occurs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.get_supported_obis_codes",
        side_effect=Exception("Unknown error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: MOCK_API_TOKEN,
                CONF_ENERGY_ID: MOCK_ENERGY_ID,
            },
        )

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"metering_point": MOCK_METERING_POINT}
        )

        assert result3["type"] == FlowResultType.MENU
        assert result3["step_id"] == "setup_type"

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], {"next_step_id": "probe"}
        )

        assert result4["type"] == FlowResultType.ABORT
        assert result4["reason"] == "unknown"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    recorder_mock: Recorder,
) -> None:
    """Test reauthentication flow."""
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Test with valid API token
    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.get_aggregated_metering_data",
        return_value=MagicMock(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "new-token"},
        )
        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "reauth_successful"

        # Verify the config entry was updated
        assert mock_config_entry.data[CONF_API_TOKEN] == "new-token"


async def test_reauth_flow_forbidden(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    recorder_mock: Recorder,
) -> None:
    """Test reauthentication flow with forbidden error."""
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.get_aggregated_metering_data",
        side_effect=ForbiddenException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "invalid-token"},
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "reauth_confirm"
        assert result2["errors"] is not None
        assert "base" in result2["errors"]
        assert result2["errors"]["base"] == "forbidden"


async def test_reauth_flow_unknown_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    recorder_mock: Recorder,
) -> None:
    """Test reauthentication flow with unknown error."""
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.leneda.config_flow.LenedaClient.get_aggregated_metering_data",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "invalid-token"},
        )
        assert result2["step_id"] == "reauth_confirm"
        assert result2["errors"] is not None
        assert "base" in result2["errors"]
        assert result2["errors"]["base"] == "unknown"
