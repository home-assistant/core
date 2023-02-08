"""Test the go-e Charger Cloud config flow and options flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.smartenergy_goecharger.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from tests.common import MockConfigEntry


async def _initialize_and_assert_flow(hass: HomeAssistant) -> FlowResult:
    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result_init["type"] == FlowResultType.FORM
    assert result_init["errors"] is None

    return result_init


async def _initialize_and_assert_options(hass: HomeAssistant, data: dict) -> FlowResult:
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="added_charger",
        data=data,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result_init = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result_init["type"] == FlowResultType.FORM
    assert result_init["errors"] is None

    return result_init


async def _assert_invalid_host(flow_id: str, data: dict, configure_fn) -> None:
    """Test an error is created when host is invalid."""
    # wrong protocol
    result_configure = await configure_fn(
        flow_id,
        data,
    )

    assert result_configure["type"] == FlowResultType.FORM
    assert result_configure["errors"] == {"base": "invalid_host"}


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


async def _assert_invalid_auth(flow_id: str, data: dict, configure_fn) -> None:
    """Test an error is created when host and token failed to authenticate."""
    # invalid auth credentials

    result_configure = await configure_fn(
        flow_id,
        data,
    )

    assert result_configure["type"] == FlowResultType.FORM
    assert result_configure["errors"] == {"base": "invalid_auth"}


async def test_config_flow_init(hass: HomeAssistant, charger_1) -> None:
    """Test we can configure the integration via config flow."""
    result_init = await _initialize_and_assert_flow(hass)

    with patch(
        f"homeassistant.components.{DOMAIN}.config_flow.GoeChargerApi.request_status",
        return_value={},
    ), patch(
        f"homeassistant.components.{DOMAIN}.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result_configure = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            charger_1,
        )
        await hass.async_block_till_done()

    assert result_configure["type"] == FlowResultType.CREATE_ENTRY
    assert result_configure["title"] == "charger1"
    assert result_configure["data"] == charger_1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_invalid_host(
    hass: HomeAssistant, charger_host_prefix, charger_host_suffix
) -> None:
    """Test an error is created when host is invalid."""
    result_init = await _initialize_and_assert_flow(hass)
    # wrong protocol
    await _assert_invalid_host(
        result_init["flow_id"],
        charger_host_prefix,
        hass.config_entries.flow.async_configure,
    )
    # extra trailing slash
    await _assert_invalid_host(
        result_init["flow_id"],
        charger_host_suffix,
        hass.config_entries.flow.async_configure,
    )


async def test_config_flow_invalid_scan_interval(
    hass: HomeAssistant, charger_interval_min, charger_interval_max
) -> None:
    """Test an error is created when scan interval is invalid."""
    result_init = await _initialize_and_assert_flow(hass)
    # min is 1
    await _assert_invalid_scan_interval(
        result_init["flow_id"],
        charger_interval_min,
        hass.config_entries.flow.async_configure,
        "value must be at least 10 for dictionary value @ data['scan_interval']",
    )
    # max is 60000
    await _assert_invalid_scan_interval(
        result_init["flow_id"],
        charger_interval_max,
        hass.config_entries.flow.async_configure,
        "value must be at most 60000 for dictionary value @ data['scan_interval']",
    )


async def test_config_flow_invalid_auth(
    hass: HomeAssistant, charger_auth_failed
) -> None:
    """Test an error is created when host and token failed to authenticate."""
    result_init = await _initialize_and_assert_flow(hass)
    await _assert_invalid_auth(
        result_init["flow_id"],
        charger_auth_failed,
        hass.config_entries.flow.async_configure,
    )


async def test_options_flow_init(hass, charger_2, charger_3) -> None:
    """Test we can configure the integration via options flow."""
    result_init = await _initialize_and_assert_options(hass, charger_2)

    with patch(
        f"homeassistant.components.{DOMAIN}.config_flow.GoeChargerApi.request_status",
        return_value={},
    ):
        result_configure = await hass.config_entries.options.async_configure(
            result_init["flow_id"],
            charger_3,
        )

    assert result_configure["type"] == FlowResultType.CREATE_ENTRY
    assert result_configure["title"] == ""
    assert result_configure["result"] is True
    assert result_configure["data"] == charger_3


async def test_options_flow_invalid_host(
    hass: HomeAssistant, charger_2, charger_host_prefix, charger_host_suffix
) -> None:
    """Test an error is created when host is invalid."""
    result_init = await _initialize_and_assert_options(hass, charger_2)
    # wrong protocol
    await _assert_invalid_host(
        result_init["flow_id"],
        charger_host_prefix,
        hass.config_entries.options.async_configure,
    )
    # extra trailing slash
    await _assert_invalid_host(
        result_init["flow_id"],
        charger_host_suffix,
        hass.config_entries.options.async_configure,
    )


async def test_options_flow_invalid_scan_interval(
    hass: HomeAssistant, charger_2, charger_interval_min, charger_interval_max
) -> None:
    """Test an error is created when scan interval is invalid."""
    result_init = await _initialize_and_assert_options(hass, charger_2)
    # min is 1
    await _assert_invalid_scan_interval(
        result_init["flow_id"],
        charger_interval_min,
        hass.config_entries.options.async_configure,
        "value must be at least 10 for dictionary value @ data['scan_interval']",
    )
    # max is 60000
    await _assert_invalid_scan_interval(
        result_init["flow_id"],
        charger_interval_max,
        hass.config_entries.options.async_configure,
        "value must be at most 60000 for dictionary value @ data['scan_interval']",
    )


async def test_options_flow_invalid_auth(
    hass: HomeAssistant, charger_2, charger_auth_failed
) -> None:
    """Test an error is created when host and token failed to authenticate."""
    result_init = await _initialize_and_assert_options(hass, charger_2)
    await _assert_invalid_auth(
        result_init["flow_id"],
        charger_auth_failed,
        hass.config_entries.options.async_configure,
    )
