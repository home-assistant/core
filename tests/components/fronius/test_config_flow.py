"""Test the Fronius config flow."""
from unittest.mock import patch

from pyfronius import FroniusError
import pytest

from homeassistant import config_entries
from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.components.fronius.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import mock_responses

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def no_setup():
    """Disable setting up the whole integration in config_flow tests."""
    with patch(
        "homeassistant.components.fronius.async_setup_entry",
        return_value=True,
    ):
        yield


INVERTER_INFO_RETURN_VALUE = {
    "inverters": [
        {
            "device_id": {"value": "1"},
            "unique_id": {"value": "1234567"},
        }
    ]
}
LOGGER_INFO_RETURN_VALUE = {"unique_identifier": {"value": "123.4567"}}
MOCK_DHCP_DATA = DhcpServiceInfo(
    hostname="fronius",
    ip="10.2.3.4",
    macaddress="00:03:ac:11:22:33",
)


async def test_form_with_logger(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
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

    assert result2["type"] == FlowResultType.CREATE_ENTRY
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
    assert result["type"] == FlowResultType.FORM
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

    assert result2["type"] == FlowResultType.CREATE_ENTRY
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

    assert result2["type"] == FlowResultType.FORM
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

    assert result2["type"] == FlowResultType.FORM
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

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_existing(hass: HomeAssistant) -> None:
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

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_updates_host(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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
    with patch(
        "homeassistant.components.fronius.async_unload_entry",
        return_value=True,
    ) as mock_unload_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": new_host,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"

    mock_unload_entry.assert_called_with(hass, entry)
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {
        "host": new_host,
        "is_logger": True,
    }


async def test_dhcp(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test starting a flow from discovery."""
    with patch(
        "homeassistant.components.fronius.config_flow.DHCP_REQUEST_DELAY", 0
    ), patch(
        "pyfronius.Fronius.current_logger_info",
        return_value=LOGGER_INFO_RETURN_VALUE,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=MOCK_DHCP_DATA
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm_discovery"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"SolarNet Datalogger at {MOCK_DHCP_DATA.ip}"
    assert result["data"] == {
        "host": MOCK_DHCP_DATA.ip,
        "is_logger": True,
    }


async def test_dhcp_already_configured(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test starting a flow from discovery."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123.4567890",
        data={
            CONF_HOST: f"http://{MOCK_DHCP_DATA.ip}/",
            "is_logger": True,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=MOCK_DHCP_DATA
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_invalid(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test starting a flow from discovery."""
    with patch(
        "homeassistant.components.fronius.config_flow.DHCP_REQUEST_DELAY", 0
    ), patch(
        "pyfronius.Fronius.current_logger_info",
        side_effect=FroniusError,
    ), patch(
        "pyfronius.Fronius.inverter_info",
        side_effect=FroniusError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=MOCK_DHCP_DATA
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "invalid_host"
