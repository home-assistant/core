"""Test the Awattar config flow and options flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.smartenergy_awattar.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from tests.common import MockConfigEntry


async def _initialize_and_assert_flow(hass: HomeAssistant) -> FlowResult:
    """Initialize the config flow and do basic checks."""
    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result_init["type"] == FlowResultType.FORM
    assert result_init["errors"] is None

    return result_init


async def _initialize_and_assert_options(hass: HomeAssistant, data: dict) -> FlowResult:
    """Initialize the config flow with options and do basic checks."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="awattar", data=data, entry_id="test"
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result_init = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result_init["type"] == FlowResultType.FORM
    assert result_init["errors"] is None

    return result_init


async def _assert_invalid_scan_interval(
    flow_id: str,
    data: dict,
    configure_fn,
    err_msg: str,
) -> None:
    """Test an error is created when scan interval is invalid."""
    with pytest.raises(Exception) as exception_info:
        await configure_fn(
            flow_id,
            data,
        )
    assert str(exception_info.value) == err_msg


async def test_config_flow_init(hass: HomeAssistant, config_1) -> None:
    """Test we can configure the integration via config flow."""
    with patch(
        f"homeassistant.components.{DOMAIN}.state.AwattarApi.get_electricity_price",
        return_value={"data": []},
    ), patch(
        f"homeassistant.components.{DOMAIN}.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result_init = await _initialize_and_assert_flow(hass)
        result_configure = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            config_1,
        )
        await hass.async_block_till_done()

    assert result_configure["type"] == FlowResultType.CREATE_ENTRY
    assert result_configure["title"] == "Awattar"
    assert result_configure["data"] == config_1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_invalid_scan_interval(
    hass: HomeAssistant, config_interval_min, config_interval_max
) -> None:
    """Test an error is created when scan interval is invalid."""
    with patch(
        f"homeassistant.components.{DOMAIN}.state.AwattarApi.get_electricity_price",
        return_value={"data": []},
    ):
        result_init = await _initialize_and_assert_flow(hass)
    # min is 1
    await _assert_invalid_scan_interval(
        result_init["flow_id"],
        config_interval_min,
        hass.config_entries.flow.async_configure,
        "value must be at least 10 for dictionary value @ data['scan_interval']",
    )
    # max is 60000
    await _assert_invalid_scan_interval(
        result_init["flow_id"],
        config_interval_max,
        hass.config_entries.flow.async_configure,
        "value must be at most 60000 for dictionary value @ data['scan_interval']",
    )


async def test_options_flow_init(hass, config_1, config_2) -> None:
    """Test we can configure the integration via options flow."""
    with patch(
        f"homeassistant.components.{DOMAIN}.state.AwattarApi.get_electricity_price",
        return_value={"data": []},
    ):
        result_init = await _initialize_and_assert_options(hass, config_1)

        result_configure = await hass.config_entries.options.async_configure(
            result_init["flow_id"],
            config_2,
        )

    assert result_configure["type"] == FlowResultType.CREATE_ENTRY
    assert result_configure["title"] == ""
    assert result_configure["result"] is True
    assert result_configure["data"] == config_2


async def test_options_flow_invalid_scan_interval(
    hass: HomeAssistant, config_1, config_interval_min, config_interval_max
) -> None:
    """Test an error is created when scan interval is invalid."""
    with patch(
        f"homeassistant.components.{DOMAIN}.state.AwattarApi.get_electricity_price",
        return_value={"data": []},
    ):
        result_init = await _initialize_and_assert_options(hass, config_1)
    # min is 1
    await _assert_invalid_scan_interval(
        result_init["flow_id"],
        config_interval_min,
        hass.config_entries.options.async_configure,
        "value must be at least 10 for dictionary value @ data['scan_interval']",
    )
    # max is 60000
    await _assert_invalid_scan_interval(
        result_init["flow_id"],
        config_interval_max,
        hass.config_entries.options.async_configure,
        "value must be at most 60000 for dictionary value @ data['scan_interval']",
    )
