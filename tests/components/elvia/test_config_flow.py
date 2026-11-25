"""Test the Elvia config flow."""

from typing import Any
from unittest.mock import AsyncMock, patch

from elvia import error as ElviaError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.elvia.const import CONF_METERING_POINT_ID, DOMAIN
from homeassistant.components.recorder.core import Recorder
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, UnknownFlow

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
    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1234"
    assert result["data"] == {
        CONF_API_TOKEN: TEST_API_TOKEN,
        CONF_METERING_POINT_ID: "1234",
    }
    assert result["result"].unique_id == "1234"
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
    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_meter"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_METERING_POINT_ID: "5678",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "5678"
    assert result["data"] == {
        CONF_API_TOKEN: TEST_API_TOKEN,
        CONF_METERING_POINT_ID: "5678",
    }
    assert result["result"].unique_id == "5678"
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
    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.ABORT
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
    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.ABORT
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
    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "metering_point_id_already_configured"

    assert len(mock_setup_entry.mock_calls) == 0


@pytest.mark.parametrize(
    ("side_effect", "base_error"),
    [
        (ElviaError.ElviaException("Boom"), "unknown"),
        (ElviaError.AuthError("Boom", 403, {}, ""), "invalid_auth"),
        (ElviaError.ElviaServerException("Boom", 500, {}, ""), "unknown"),
        (ElviaError.ElviaClientException("Boom"), "unknown"),
    ],
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

    assert result["type"] is FlowResultType.FORM
    # pylint: disable-next=home-assistant-tests-config-flow-error-recovery
    assert result["errors"] == {"base": base_error}

    # Simulate that the user gives up and closes the window...
    hass.config_entries.flow._async_remove_flow_progress(result["flow_id"])
    await hass.async_block_till_done()

    with pytest.raises(UnknownFlow):
        hass.config_entries.flow.async_get(result["flow_id"])


@pytest.mark.usefixtures("recorder_mock")
async def test_reauth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a successful reauthentication."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={CONF_API_TOKEN: "old-token", CONF_METERING_POINT_ID: "1234"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "elvia.meter_value.MeterValue.get_meter_values",
        return_value={
            "meteringpoints": [
                {"meteringPointId": "5678"},
                {"meteringPointId": "1234"},
            ]
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: TEST_API_TOKEN},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {
        CONF_API_TOKEN: TEST_API_TOKEN,
        CONF_METERING_POINT_ID: "1234",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "base_error"),
    [
        pytest.param(
            ElviaError.AuthError("Boom", 403, {}, ""), "invalid_auth", id="auth"
        ),
        pytest.param(
            ElviaError.ElviaServerException("Boom", 500, {}, ""),
            "unknown",
            id="server",
        ),
        pytest.param(ElviaError.ElviaClientException("Boom"), "unknown", id="client"),
    ],
)
@pytest.mark.usefixtures("recorder_mock")
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    base_error: str,
) -> None:
    """Test reauthentication errors and a successful retry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={CONF_API_TOKEN: "old-token", CONF_METERING_POINT_ID: "1234"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "elvia.meter_value.MeterValue.get_meter_values",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "bad-token"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": base_error}

    with patch(
        "elvia.meter_value.MeterValue.get_meter_values",
        return_value={"meteringpoints": [{"meteringPointId": "1234"}]},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: TEST_API_TOKEN},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_TOKEN] == TEST_API_TOKEN
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "meter_values",
    [
        pytest.param(
            {"meteringpoints": [{"meteringPointId": "5678"}]}, id="other_point"
        ),
        pytest.param({"meteringpoints": []}, id="no_points"),
        pytest.param({}, id="bad_data"),
    ],
)
@pytest.mark.usefixtures("recorder_mock")
async def test_reauth_wrong_account(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    meter_values: dict[str, Any],
) -> None:
    """Test reauthentication aborts when the token cannot read the metering point."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={CONF_API_TOKEN: "old-token", CONF_METERING_POINT_ID: "1234"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "elvia.meter_value.MeterValue.get_meter_values",
        return_value=meter_values,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: TEST_API_TOKEN},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert entry.data[CONF_API_TOKEN] == "old-token"
    assert len(mock_setup_entry.mock_calls) == 0
