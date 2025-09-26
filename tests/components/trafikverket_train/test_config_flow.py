"""Test the Trafikverket Train config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pytrafikverket import (
    InvalidAuthentication,
    NoTrainStationFound,
    StationInfoModel,
    TrainStopModel,
    UnknownError,
)

from homeassistant import config_entries
from homeassistant.components.trafikverket_train.const import (
    CONF_FILTER_PRODUCT,
    CONF_FROM,
    CONF_TIME,
    CONF_TO,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_WEEKDAY, WEEKDAYS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import ENTRY_CONFIG, OPTIONS_CONFIG

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant, get_train_stations: list[StationInfoModel]
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "initial"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_stations",
            side_effect=get_train_stations,
        ),
        patch(
            "homeassistant.components.trafikverket_train.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
                CONF_TIME: "10:00",
                CONF_WEEKDAY: ["mon", "fri"],
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Stockholm C to Uppsala C at 10:00"
    assert result["data"] == {
        "api_key": "1234567890",
        "name": "Stockholm C to Uppsala C at 10:00",
        "from": "Cst",
        "to": "U",
        "time": "10:00",
        "weekday": ["mon", "fri"],
    }
    assert result["options"] == {"filter_product": None}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_multiple_stations(
    hass: HomeAssistant, get_multiple_train_stations: list[StationInfoModel]
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_stations",
            side_effect=get_multiple_train_stations,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
                CONF_TIME: "10:00",
                CONF_WEEKDAY: ["mon", "fri"],
            },
        )
        await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_stations",
            side_effect=get_multiple_train_stations,
        ),
        patch(
            "homeassistant.components.trafikverket_train.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FROM: "Csu",
                CONF_TO: "Ups",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Stockholm C to Uppsala C at 10:00"
    assert result["data"] == {
        "api_key": "1234567890",
        "name": "Stockholm C to Uppsala C at 10:00",
        "from": "Csu",
        "to": "Ups",
        "time": "10:00",
        "weekday": ["mon", "fri"],
    }
    assert result["options"] == {"filter_product": None}


async def test_form_entry_already_exist(
    hass: HomeAssistant, get_train_stations: list[StationInfoModel]
) -> None:
    """Test flow aborts when entry already exist."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_NAME: "Stockholm C to Uppsala C at 10:00",
            CONF_FROM: "Cst",
            CONF_TO: "U",
            CONF_TIME: "10:00",
            CONF_WEEKDAY: WEEKDAYS,
            CONF_FILTER_PRODUCT: None,
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_get_train_stop",
        ),
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_stations",
            side_effect=get_train_stations,
        ),
        patch(
            "homeassistant.components.trafikverket_train.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
                CONF_TIME: "10:00",
                CONF_WEEKDAY: WEEKDAYS,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "p_error"),
    [
        (
            InvalidAuthentication,
            {"base": "invalid_auth"},
        ),
        (
            NoTrainStationFound,
            {"from": "invalid_station", "to": "invalid_station"},
        ),
        (
            Exception,
            {"base": "cannot_connect"},
        ),
    ],
)
async def test_flow_fails(
    hass: HomeAssistant, side_effect: Exception, p_error: dict[str, str]
) -> None:
    """Test config flow errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "initial"

    with (
        patch(
            "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_search_train_stations",
            side_effect=side_effect(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
            },
        )

    assert result["errors"] == p_error


@pytest.mark.parametrize(
    ("side_effect", "p_error"),
    [
        (
            NoTrainStationFound,
            {"from": "invalid_station", "to": "invalid_station"},
        ),
        (
            UnknownError,
            {"base": "cannot_connect"},
        ),
    ],
)
async def test_flow_fails_departures(
    hass: HomeAssistant, side_effect: Exception, p_error: dict[str, str]
) -> None:
    """Test config flow errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "initial"

    with (
        patch(
            "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_search_train_stations",
            side_effect=side_effect(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
            },
        )

    assert result["errors"] == p_error


async def test_reauth_flow(
    hass: HomeAssistant, get_train_stations: list[StationInfoModel]
) -> None:
    """Test a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_NAME: "Stockholm C to Uppsala C at 10:00",
            CONF_FROM: "Cst",
            CONF_TO: "U",
            CONF_TIME: "10:00",
            CONF_WEEKDAY: WEEKDAYS,
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_search_train_stations",
            side_effect=get_train_stations,
        ),
        patch(
            "homeassistant.components.trafikverket_train.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567891"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {
        "api_key": "1234567891",
        "name": "Stockholm C to Uppsala C at 10:00",
        "from": "Cst",
        "to": "U",
        "time": "10:00",
        "weekday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    }


@pytest.mark.parametrize(
    ("side_effect", "p_error"),
    [
        (
            InvalidAuthentication,
            {"base": "invalid_auth"},
        ),
        (
            NoTrainStationFound,
            {"from": "invalid_station"},
        ),
        (
            UnknownError,
            {"base": "cannot_connect"},
        ),
        (
            Exception,
            {"base": "cannot_connect"},
        ),
    ],
)
async def test_reauth_flow_error(
    hass: HomeAssistant,
    side_effect: Exception,
    p_error: dict[str, str],
    get_train_stations: list[StationInfoModel],
) -> None:
    """Test a reauthentication flow with error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_NAME: "Stockholm C to Uppsala C at 10:00",
            CONF_FROM: "Cst",
            CONF_TO: "U",
            CONF_TIME: "10:00",
            CONF_WEEKDAY: WEEKDAYS,
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with (
        patch(
            "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_search_train_stations",
            side_effect=side_effect(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567890"},
        )
        await hass.async_block_till_done()

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == p_error

    with (
        patch(
            "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_search_train_stations",
            side_effect=get_train_stations,
        ),
        patch(
            "homeassistant.components.trafikverket_train.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567891"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {
        "api_key": "1234567891",
        "name": "Stockholm C to Uppsala C at 10:00",
        "from": "Cst",
        "to": "U",
        "time": "10:00",
        "weekday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    }


@pytest.mark.parametrize(
    ("side_effect", "p_error"),
    [
        (
            NoTrainStationFound,
            {"from": "invalid_station"},
        ),
        (
            UnknownError,
            {"base": "cannot_connect"},
        ),
    ],
)
async def test_reauth_flow_error_departures(
    hass: HomeAssistant,
    side_effect: Exception,
    p_error: dict[str, str],
    get_train_stations: list[StationInfoModel],
) -> None:
    """Test a reauthentication flow with error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_NAME: "Stockholm C to Uppsala C at 10:00",
            CONF_FROM: "Cst",
            CONF_TO: "U",
            CONF_TIME: "10:00",
            CONF_WEEKDAY: WEEKDAYS,
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with (
        patch(
            "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_search_train_stations",
            side_effect=side_effect(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567890"},
        )
        await hass.async_block_till_done()

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == p_error

    with (
        patch(
            "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_search_train_stations",
            side_effect=get_train_stations,
        ),
        patch(
            "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_get_train_stop",
        ),
        patch(
            "homeassistant.components.trafikverket_train.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567891"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {
        "api_key": "1234567891",
        "name": "Stockholm C to Uppsala C at 10:00",
        "from": "Cst",
        "to": "U",
        "time": "10:00",
        "weekday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    }


async def test_options_flow(
    hass: HomeAssistant,
    get_trains: list[TrainStopModel],
    get_train_stop: TrainStopModel,
    get_train_stations: list[StationInfoModel],
) -> None:
    """Test a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_NAME: "Stockholm C to Uppsala C at 10:00",
            CONF_FROM: "Cst",
            CONF_TO: "U",
            CONF_TIME: "10:00",
            CONF_WEEKDAY: WEEKDAYS,
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_stations",
            side_effect=get_train_stations,
        ),
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_next_train_stops",
            return_value=get_trains,
        ),
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_train_station_from_signature",
        ),
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_train_stop",
            return_value=get_train_stop,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"filter_product": "SJ Regionaltåg"},
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {"filter_product": "SJ Regionaltåg"}

        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"filter_product": ""},
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {"filter_product": None}


async def test_reconfigure_flow(
    hass: HomeAssistant, get_train_stations: list[StationInfoModel]
) -> None:
    """Test reconfigure flow."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_CONFIG,
        options=OPTIONS_CONFIG,
        entry_id="1",
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "initial"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_stations",
            side_effect=get_train_stations,
        ),
        patch(
            "homeassistant.components.trafikverket_train.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
                CONF_TIME: "10:00",
                CONF_WEEKDAY: ["mon", "fri"],
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_multiple_stations(
    hass: HomeAssistant, get_multiple_train_stations: list[StationInfoModel]
) -> None:
    """Test we can reconfigure with multiple stations."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_CONFIG,
        options=OPTIONS_CONFIG,
        entry_id="1",
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "initial"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_stations",
            side_effect=get_multiple_train_stations,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
                CONF_TIME: "10:00",
                CONF_WEEKDAY: ["mon", "fri"],
            },
        )
        await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_stations",
            side_effect=get_multiple_train_stations,
        ),
        patch(
            "homeassistant.components.trafikverket_train.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FROM: "Csu",
                CONF_TO: "Ups",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_entry_already_exist(
    hass: HomeAssistant, get_train_stations: list[StationInfoModel]
) -> None:
    """Test flow aborts when entry already exist in a reconfigure flow."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_NAME: "Stockholm C to Uppsala C at 10:00",
            CONF_FROM: "Cst",
            CONF_TO: "U",
            CONF_TIME: "10:00",
            CONF_WEEKDAY: WEEKDAYS,
            CONF_FILTER_PRODUCT: None,
        },
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    config_entry2 = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_CONFIG,
        options=OPTIONS_CONFIG,
        entry_id="1",
        version=2,
        minor_version=1,
    )
    config_entry2.add_to_hass(hass)
    result = await config_entry2.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_get_train_stop",
        ),
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_stations",
            side_effect=get_train_stations,
        ),
        patch(
            "homeassistant.components.trafikverket_train.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
                CONF_TIME: "10:00",
                CONF_WEEKDAY: WEEKDAYS,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "p_error"),
    [
        (
            InvalidAuthentication,
            {"base": "invalid_auth"},
        ),
        (
            NoTrainStationFound,
            {"from": "invalid_station", "to": "invalid_station"},
        ),
        (
            Exception,
            {"base": "cannot_connect"},
        ),
    ],
)
async def test_reconfigure_flow_fails(
    hass: HomeAssistant,
    side_effect: Exception,
    p_error: dict[str, str],
    get_train_stations: list[StationInfoModel],
) -> None:
    """Test config flow errors."""
    config_entry2 = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_CONFIG,
        options=OPTIONS_CONFIG,
        entry_id="1",
        version=2,
        minor_version=1,
    )
    config_entry2.add_to_hass(hass)
    result = await config_entry2.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "initial"

    with (
        patch(
            "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_search_train_stations",
            side_effect=side_effect(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
            },
        )

    assert result["errors"] == p_error

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_stations",
            side_effect=get_train_stations,
        ),
        patch(
            "homeassistant.components.trafikverket_train.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    ("side_effect", "p_error"),
    [
        (
            NoTrainStationFound,
            {"from": "invalid_station", "to": "invalid_station"},
        ),
        (
            UnknownError,
            {"base": "cannot_connect"},
        ),
    ],
)
async def test_reconfigure_flow_fails_departures(
    hass: HomeAssistant,
    side_effect: Exception,
    p_error: dict[str, str],
    get_train_stations: list[StationInfoModel],
) -> None:
    """Test config flow errors."""
    config_entry2 = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_CONFIG,
        options=OPTIONS_CONFIG,
        entry_id="1",
        version=2,
        minor_version=1,
    )
    config_entry2.add_to_hass(hass)
    result = await config_entry2.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "initial"

    with (
        patch(
            "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_search_train_stations",
            side_effect=side_effect(),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
            },
        )

    assert result["errors"] == p_error

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_stations",
            side_effect=get_train_stations,
        ),
        patch(
            "homeassistant.components.trafikverket_train.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
