"""Tests for the solax config flow."""

from unittest.mock import patch

from solax import RealTimeAPI
from solax.inverter import InverterResponse
from solax.inverters import X1MiniV34

from homeassistant import config_entries
from homeassistant.components.solax.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def __mock_real_time_api_success():
    inverters: set[X1MiniV34] = X1MiniV34.build_all_variants(
        host="solax.local",
        port=80,
    )
    return RealTimeAPI(next(iter(inverters)))


def __mock_get_data():
    return InverterResponse(
        data=None,
        dongle_serial_number="ABCDEFGHIJ",
        version="2.034.06",
        type=4,
        inverter_serial_number="XXXXXXX",
    )


async def test_form_configure_success(hass: HomeAssistant) -> None:
    """Test successful form."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert "type" in flow
    assert "errors" in flow
    assert flow["type"] is FlowResultType.FORM
    assert flow["errors"] == {}

    with (
        patch(
            "homeassistant.components.solax.config_flow.real_time_api",
            return_value=__mock_real_time_api_success(),
        ),
        patch("solax.RealTimeAPI.get_data", return_value=__mock_get_data()),
        patch(
            "homeassistant.components.solax.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        entry_result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {CONF_IP_ADDRESS: "192.168.1.87", CONF_PORT: 80, CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

    assert "type" in entry_result
    assert "title" in entry_result
    assert "data" in entry_result
    assert entry_result["type"] is FlowResultType.CREATE_ENTRY
    assert entry_result["title"] == "ABCDEFGHIJ"
    assert entry_result["data"] == {
        CONF_IP_ADDRESS: "192.168.1.87",
        CONF_PORT: 80,
        CONF_PASSWORD: "password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_reconfigure_success(hass: HomeAssistant) -> None:
    """Test successful form."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with (
        patch(
            "homeassistant.components.solax.config_flow.real_time_api",
            return_value=__mock_real_time_api_success(),
        ),
        patch("solax.RealTimeAPI.get_data", return_value=__mock_get_data()),
        patch(
            "homeassistant.components.solax.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        entry_result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {CONF_IP_ADDRESS: "192.168.1.87", CONF_PORT: 80, CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

        assert "result" in entry_result
        assert "data" in entry_result
        assert "context" in entry_result
        assert "unique_id" in entry_result["context"]
        assert entry_result["data"] == {
            CONF_IP_ADDRESS: "192.168.1.87",
            CONF_PORT: 80,
            CONF_PASSWORD: "password",
        }

        flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "entry_id": entry_result["result"].entry_id,
                "source": config_entries.SOURCE_RECONFIGURE,
            },
        )
        assert "type" in flow
        assert "errors" in flow
        assert "data_schema" in flow
        assert flow["type"] is FlowResultType.FORM
        assert flow["errors"] == {}

        await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {
                CONF_IP_ADDRESS: "192.168.1.187",
                CONF_PORT: 8080,
                CONF_PASSWORD: "password123",
            },
        )
        await hass.async_block_till_done()

    config_entry = hass.config_entries.async_entry_for_domain_unique_id(
        DOMAIN,
        entry_result["context"]["unique_id"],
    )
    assert config_entry is not None
    assert config_entry.data == {
        CONF_IP_ADDRESS: "192.168.1.187",
        CONF_PORT: 8080,
        CONF_PASSWORD: "password123",
    }
    assert len(mock_setup_entry.mock_calls) == 2


async def test_form_configure_connect_error(hass: HomeAssistant) -> None:
    """Test cannot connect form."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert "type" in flow
    assert "errors" in flow
    assert flow["type"] is FlowResultType.FORM
    assert flow["errors"] == {}

    with patch(
        "homeassistant.components.solax.config_flow.real_time_api",
        side_effect=ConnectionError,
    ):
        entry_result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {CONF_IP_ADDRESS: "192.168.1.87", CONF_PORT: 80, CONF_PASSWORD: "password"},
        )

    assert "type" in entry_result
    assert "errors" in entry_result
    assert entry_result["type"] is FlowResultType.FORM
    assert entry_result["errors"] == {"base": "cannot_connect"}


async def test_form_reconfigure_connect_error(hass: HomeAssistant) -> None:
    """Test cannot connect form."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with (
        patch(
            "homeassistant.components.solax.config_flow.real_time_api",
            return_value=__mock_real_time_api_success(),
        ),
        patch("solax.RealTimeAPI.get_data", return_value=__mock_get_data()),
        patch(
            "homeassistant.components.solax.async_setup_entry",
            return_value=True,
        ),
    ):
        entry_result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {CONF_IP_ADDRESS: "192.168.1.87", CONF_PORT: 80, CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

        flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "entry_id": entry_result["result"].entry_id,
                "source": config_entries.SOURCE_RECONFIGURE,
            },
        )
        assert "type" in flow
        assert "errors" in flow
        assert flow["type"] is FlowResultType.FORM
        assert flow["errors"] == {}

        with patch(
            "homeassistant.components.solax.config_flow.real_time_api",
            side_effect=ConnectionError,
        ):
            entry_result = await hass.config_entries.flow.async_configure(
                flow["flow_id"],
                {
                    CONF_IP_ADDRESS: "192.168.1.87",
                    CONF_PORT: 80,
                    CONF_PASSWORD: "password",
                },
            )

        assert "type" in entry_result
        assert "errors" in entry_result
        assert entry_result["type"] is FlowResultType.FORM
        assert entry_result["errors"] == {"base": "cannot_connect"}


async def test_form_configure_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown error form."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert "type" in flow
    assert "errors" in flow
    assert flow["type"] is FlowResultType.FORM
    assert flow["errors"] == {}

    with patch(
        "homeassistant.components.solax.config_flow.real_time_api",
        side_effect=Exception,
    ):
        entry_result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {CONF_IP_ADDRESS: "192.168.1.87", CONF_PORT: 80, CONF_PASSWORD: "password"},
        )

    assert "type" in entry_result
    assert "errors" in entry_result
    assert entry_result["type"] is FlowResultType.FORM
    assert entry_result["errors"] == {"base": "unknown"}


async def test_form_reconfigure_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown error form."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with (
        patch(
            "homeassistant.components.solax.config_flow.real_time_api",
            return_value=__mock_real_time_api_success(),
        ),
        patch("solax.RealTimeAPI.get_data", return_value=__mock_get_data()),
        patch(
            "homeassistant.components.solax.async_setup_entry",
            return_value=True,
        ),
    ):
        entry_result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {CONF_IP_ADDRESS: "192.168.1.87", CONF_PORT: 80, CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

        flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "entry_id": entry_result["result"].entry_id,
                "source": config_entries.SOURCE_RECONFIGURE,
            },
        )

        assert "type" in flow
        assert "errors" in flow
        assert flow["type"] is FlowResultType.FORM
        assert flow["errors"] == {}

        with patch(
            "homeassistant.components.solax.config_flow.real_time_api",
            side_effect=Exception,
        ):
            entry_result = await hass.config_entries.flow.async_configure(
                flow["flow_id"],
                {
                    CONF_IP_ADDRESS: "192.168.1.87",
                    CONF_PORT: 80,
                    CONF_PASSWORD: "password",
                },
            )

        assert "type" in entry_result
        assert "errors" in entry_result
        assert entry_result["type"] is FlowResultType.FORM
        assert entry_result["errors"] == {"base": "unknown"}
