"""Tests for the Bizkaibus config flow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bizkaibus.bizkaibusAPI import BizkaibusLanguages

from homeassistant.components.bizkaibus.const import (
    CONF_LINE_IDS,
    CONF_LINES,
    CONF_STOP_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_displays_form(hass: HomeAssistant) -> None:
    """Test the user step displays the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_flow_with_valid_stop_id(hass: HomeAssistant) -> None:
    """Test the user flow with a valid stop ID transitions to lines step."""
    stop_id = "1234"
    line1 = SimpleNamespace(id="A", route="Route A")
    line2 = SimpleNamespace(id="B", route="Route B")
    timetable = SimpleNamespace(id="stop_1234", name="Central Station")

    with patch(
        "homeassistant.components.bizkaibus.config_flow.BizkaibusAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.TestConnection = AsyncMock(return_value=True)
        mock_api.GetLinesOnStop = AsyncMock(return_value=[line1, line2])
        mock_api.GetTimetable = AsyncMock(return_value=timetable)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STOP_ID: stop_id}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "lines"
        mock_api_class.assert_called_once_with(BizkaibusLanguages.ES, stop_id)


async def test_user_flow_with_offline_stop(hass: HomeAssistant) -> None:
    """Test the user flow when the stop is offline."""
    stop_id = "9999"

    with patch(
        "homeassistant.components.bizkaibus.config_flow.BizkaibusAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.TestConnection = AsyncMock(return_value=False)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STOP_ID: stop_id}
        )

        # Should return to user form when offline
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"


async def test_user_flow_with_timetable_none(hass: HomeAssistant) -> None:
    """Test the user flow when timetable is None."""
    stop_id = "5678"
    line = SimpleNamespace(id="C", route="Route C")

    with patch(
        "homeassistant.components.bizkaibus.config_flow.BizkaibusAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.TestConnection = AsyncMock(return_value=True)
        mock_api.GetLinesOnStop = AsyncMock(return_value=[line])
        mock_api.GetTimetable = AsyncMock(return_value=None)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STOP_ID: stop_id}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "lines"


async def test_lines_flow_creates_entry(hass: HomeAssistant) -> None:
    """Test the lines step creates an entry with selected lines."""
    stop_id = "1234"
    line1 = SimpleNamespace(id="A", route="Route A")
    line2 = SimpleNamespace(id="B", route="Route B")
    timetable = SimpleNamespace(id="stop_1234", name="Central Station")

    with (
        patch(
            "homeassistant.components.bizkaibus.config_flow.BizkaibusAPI"
        ) as mock_api_class,
        patch("homeassistant.components.bizkaibus.async_setup_entry") as mock_setup,
    ):
        mock_setup.return_value = True
        mock_api = mock_api_class.return_value
        mock_api.TestConnection = AsyncMock(return_value=True)
        mock_api.GetLinesOnStop = AsyncMock(return_value=[line1, line2])
        mock_api.GetTimetable = AsyncMock(return_value=timetable)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STOP_ID: stop_id}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STOP_ID: stop_id, CONF_LINE_IDS: ["A", "B"]}
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "1234 Central Station"
        assert result["data"] == {CONF_STOP_ID: stop_id}
        assert result["options"][CONF_LINE_IDS] == ["A", "B"]
        assert result["options"][CONF_LINES] == {"A": "Route A", "B": "Route B"}


async def test_lines_flow_with_single_line(hass: HomeAssistant) -> None:
    """Test the lines step with a single line."""
    stop_id = "2345"
    line = SimpleNamespace(id="X", route="Express Route")
    timetable = SimpleNamespace(id="stop_2345", name="Main Street")

    with (
        patch(
            "homeassistant.components.bizkaibus.config_flow.BizkaibusAPI"
        ) as mock_api_class,
        patch("homeassistant.components.bizkaibus.async_setup_entry") as mock_setup,
    ):
        mock_setup.return_value = True
        mock_api = mock_api_class.return_value
        mock_api.TestConnection = AsyncMock(return_value=True)
        mock_api.GetLinesOnStop = AsyncMock(return_value=[line])
        mock_api.GetTimetable = AsyncMock(return_value=timetable)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STOP_ID: stop_id}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STOP_ID: stop_id, CONF_LINE_IDS: ["X"]}
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {CONF_STOP_ID: stop_id}
        assert result["options"][CONF_LINE_IDS] == ["X"]


async def test_lines_flow_displays_form(hass: HomeAssistant) -> None:
    """Test the lines step displays a form with options."""
    stop_id = "3456"
    line1 = SimpleNamespace(id="L1", route="Line 1")
    line2 = SimpleNamespace(id="L2", route="Line 2")
    timetable = SimpleNamespace(id="stop_3456", name=None)

    with patch(
        "homeassistant.components.bizkaibus.config_flow.BizkaibusAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.TestConnection = AsyncMock(return_value=True)
        mock_api.GetLinesOnStop = AsyncMock(return_value=[line1, line2])
        mock_api.GetTimetable = AsyncMock(return_value=timetable)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STOP_ID: stop_id}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "lines"
        # Verify the form has the stop_id field
        assert CONF_STOP_ID in result["data_schema"].schema


async def test_reconfigure_step(hass: HomeAssistant) -> None:
    """Test the reconfigure step."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STOP_ID: "1234"},
        options={CONF_LINE_IDS: ["A"]},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reconfigure", "entry_id": config_entry.entry_id}
    )

    # The reconfigure step should show the user form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
