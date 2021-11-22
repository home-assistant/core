"""Test the Fronius config flow."""
from unittest.mock import patch

from pyfronius import FroniusError

from homeassistant import config_entries
from homeassistant.components.fronius.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_HOST, CONF_RESOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.setup import async_setup_component

from . import MOCK_HOST, mock_responses

from tests.common import MockConfigEntry

INVERTER_INFO_RETURN_VALUE = {
    "inverters": [
        {
            "device_id": {"value": "1"},
            "unique_id": {"value": "1234567"},
        }
    ]
}
LOGGER_INFO_RETURN_VALUE = {"unique_identifier": {"value": "123.4567"}}


async def test_form_with_logger(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "pyfronius.Fronius.current_logger_info",
        return_value=LOGGER_INFO_RETURN_VALUE,
    ), patch(
        "homeassistant.components.fronius.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "10.9.8.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "SolarNet Datalogger at 10.9.8.1"
    assert result2["data"] == {
        "host": "10.9.8.1",
        "is_logger": True,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_with_inverter(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "pyfronius.Fronius.current_logger_info",
        side_effect=FroniusError,
    ), patch(
        "pyfronius.Fronius.inverter_info",
        return_value=INVERTER_INFO_RETURN_VALUE,
    ), patch(
        "homeassistant.components.fronius.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "10.9.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "SolarNet Inverter at 10.9.1.1"
    assert result2["data"] == {
        "host": "10.9.1.1",
        "is_logger": False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyfronius.Fronius.current_logger_info",
        side_effect=FroniusError,
    ), patch(
        "pyfronius.Fronius.inverter_info",
        side_effect=FroniusError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_no_device(hass: HomeAssistant) -> None:
    """Test we handle no device found error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyfronius.Fronius.current_logger_info",
        side_effect=FroniusError,
    ), patch(
        "pyfronius.Fronius.inverter_info",
        return_value={"inverters": []},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unexpected(hass: HomeAssistant) -> None:
    """Test we handle unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyfronius.Fronius.current_logger_info",
        side_effect=KeyError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_existing(hass):
    """Test existing entry."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="123.4567",
        data={CONF_HOST: "10.9.8.1", "is_logger": True},
    ).add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "pyfronius.Fronius.current_logger_info",
        return_value=LOGGER_INFO_RETURN_VALUE,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "10.9.8.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "already_configured"


async def test_form_updates_host(hass, aioclient_mock):
    """Test existing entry gets updated."""
    old_host = "http://10.1.0.1"
    new_host = "http://10.1.0.2"
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123.4567890",  # has to match mocked logger unique_id
        data={
            CONF_HOST: old_host,
            "is_logger": True,
        },
    )
    entry.add_to_hass(hass)
    mock_responses(aioclient_mock, host=old_host)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_responses(aioclient_mock, host=new_host)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": new_host,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "already_configured"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {
        "host": new_host,
        "is_logger": True,
    }


async def test_import(hass, aioclient_mock):
    """Test import step."""
    mock_responses(aioclient_mock)
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                CONF_RESOURCE: MOCK_HOST,
            }
        },
    )
    await hass.async_block_till_done()

    fronius_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(fronius_entries) == 1

    test_entry = fronius_entries[0]
    assert test_entry.unique_id == "123.4567890"  # has to match mocked logger unique_id
    assert test_entry.data == {
        "host": MOCK_HOST,
        "is_logger": True,
    }
