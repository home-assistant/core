"""Test the Elvia config flow."""
from unittest.mock import AsyncMock, patch

from elvia import error as ElviaError
import pytest

from homeassistant import config_entries
from homeassistant.components.elvia.const import CONF_METERING_POINT_ID, DOMAIN
from homeassistant.components.recorder.core import Recorder
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, UnknownFlow

from tests.common import MockConfigEntry

TEST_API_TOKEN = "xxx-xxx-xxx-xxx"


async def test_single_metering_point(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test using the config flow with a single metering point."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "elvia.meter_value.MeterValue.get_meter_values",
        return_value={"meteringpoints": [{"meteringPointId": "1234"}]},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: TEST_API_TOKEN,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "1234"
    assert result["data"] == {
        CONF_API_TOKEN: TEST_API_TOKEN,
        CONF_METERING_POINT_ID: "1234",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_multiple_metering_points(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test using the config flow with multiple metering points."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "elvia.meter_value.MeterValue.get_meter_values",
        return_value={
            "meteringpoints": [
                {"meteringPointId": "1234"},
                {"meteringPointId": "5678"},
            ]
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: TEST_API_TOKEN,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "select_meter"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_METERING_POINT_ID: "5678",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "5678"
    assert result["data"] == {
        CONF_API_TOKEN: TEST_API_TOKEN,
        CONF_METERING_POINT_ID: "5678",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_no_metering_points(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test using the config flow with no metering points."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "elvia.meter_value.MeterValue.get_meter_values",
        return_value={"meteringpoints": []},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: TEST_API_TOKEN,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_metering_points"

    assert len(mock_setup_entry.mock_calls) == 0


async def test_bad_data(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test using the config flow with no metering points."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "elvia.meter_value.MeterValue.get_meter_values",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: TEST_API_TOKEN,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_metering_points"

    assert len(mock_setup_entry.mock_calls) == 0


async def test_abort_when_metering_point_id_exist(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that we abort when the metering point ID exist."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "elvia.meter_value.MeterValue.get_meter_values",
        return_value={"meteringpoints": [{"meteringPointId": "1234"}]},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: TEST_API_TOKEN,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "metering_point_id_already_configured"

    assert len(mock_setup_entry.mock_calls) == 0


@pytest.mark.parametrize(
    ("side_effect", "base_error"),
    (
        (ElviaError.ElviaException("Boom"), "unknown"),
        (ElviaError.AuthError("Boom", 403, {}, ""), "invalid_auth"),
        (ElviaError.ElviaServerException("Boom", 500, {}, ""), "unknown"),
        (ElviaError.ElviaClientException("Boom"), "unknown"),
    ),
)
async def test_form_exceptions(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    side_effect: Exception,
    base_error: str,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "elvia.meter_value.MeterValue.get_meter_values",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: TEST_API_TOKEN,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": base_error}

    # Simulate that the user gives up and closes the window...
    hass.config_entries.flow._async_remove_flow_progress(result["flow_id"])
    await hass.async_block_till_done()

    with pytest.raises(UnknownFlow):
        hass.config_entries.flow.async_get(result["flow_id"])
