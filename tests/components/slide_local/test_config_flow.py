"""Test the slide_local config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from goslideapi.goslideapi import (
    AuthenticationFailed,
    ClientConnectionError,
    ClientTimeoutError,
    DigestAuthCalcError,
)
import pytest

from homeassistant.components.slide_local.const import CONF_INVERT_POSITION, DOMAIN
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_API_VERSION, CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_platform
from .const import HOST, SLIDE_INFO_DATA

from tests.common import MockConfigEntry

MOCK_ZEROCONF_DATA = ZeroconfServiceInfo(
    ip_address=ip_address("127.0.0.2"),
    ip_addresses=[ip_address("127.0.0.2")],
    hostname="Slide-1234567890AB.local.",
    name="Slide-1234567890AB._http._tcp.local.",
    port=80,
    properties={
        "id": "slide-1234567890AB",
        "arch": "esp32",
        "app": "slide",
        "fw_version": "2.0.0-1683059251",
        "fw_id": "20230502-202745",
    },
    type="mock_type",
)


async def test_user(
    hass: HomeAssistant, mock_slide_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PASSWORD: "pwd",
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == HOST
    assert result2["data"][CONF_HOST] == HOST
    assert result2["data"][CONF_PASSWORD] == "pwd"
    assert result2["data"][CONF_API_VERSION] == 2
    assert result2["result"].unique_id == "12:34:56:78:90:ab"
    assert not result2["options"][CONF_INVERT_POSITION]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_api_1(
    hass: HomeAssistant,
    mock_slide_api: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_slide_api.slide_info.side_effect = [None, SLIDE_INFO_DATA]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PASSWORD: "pwd",
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == HOST
    assert result2["data"][CONF_HOST] == HOST
    assert result2["data"][CONF_PASSWORD] == "pwd"
    assert result2["data"][CONF_API_VERSION] == 1
    assert result2["result"].unique_id == "12:34:56:78:90:ab"
    assert not result2["options"][CONF_INVERT_POSITION]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_api_error(
    hass: HomeAssistant,
    mock_slide_api: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_slide_api.slide_info.side_effect = [None, None]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PASSWORD: "pwd",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "unknown"

    mock_slide_api.slide_info.side_effect = [None, SLIDE_INFO_DATA]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PASSWORD: "pwd",
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == HOST
    assert result2["data"][CONF_HOST] == HOST
    assert result2["data"][CONF_PASSWORD] == "pwd"
    assert result2["data"][CONF_API_VERSION] == 1
    assert result2["result"].unique_id == "12:34:56:78:90:ab"
    assert not result2["options"][CONF_INVERT_POSITION]
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ClientConnectionError, "cannot_connect"),
        (ClientTimeoutError, "cannot_connect"),
        (AuthenticationFailed, "invalid_auth"),
        (DigestAuthCalcError, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_api_1_exceptions(
    hass: HomeAssistant,
    exception: Exception,
    error: str,
    mock_slide_api: AsyncMock,
) -> None:
    """Test we can handle Form exceptions for api 1."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_slide_api.slide_info.side_effect = [None, exception]

    # tests with connection error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PASSWORD: "pwd",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == error

    # tests with all provided
    mock_slide_api.slide_info.side_effect = [None, SLIDE_INFO_DATA]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PASSWORD: "pwd",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ClientConnectionError, "cannot_connect"),
        (ClientTimeoutError, "cannot_connect"),
        (AuthenticationFailed, "invalid_auth"),
        (DigestAuthCalcError, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_api_2_exceptions(
    hass: HomeAssistant,
    exception: Exception,
    error: str,
    mock_slide_api: AsyncMock,
) -> None:
    """Test we can handle Form exceptions for api 2."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_slide_api.slide_info.side_effect = exception

    # tests with connection error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PASSWORD: "pwd",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == error

    # tests with all provided
    mock_slide_api.slide_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PASSWORD: "pwd",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_abort_if_already_setup(
    hass: HomeAssistant,
    mock_slide_api: AsyncMock,
) -> None:
    """Test we abort if the device is already setup."""

    MockConfigEntry(domain=DOMAIN, unique_id="12:34:56:78:90:ab").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PASSWORD: "pwd",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure(
    hass: HomeAssistant,
    mock_slide_api: AsyncMock,
    mock_config_entry: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfigure flow options."""

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.3",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert len(mock_setup_entry.mock_calls) == 1

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry
    assert entry.data[CONF_HOST] == "127.0.0.3"


async def test_zeroconf(
    hass: HomeAssistant, mock_slide_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test starting a flow from discovery."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=MOCK_ZEROCONF_DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "127.0.0.2"
    assert result["data"][CONF_HOST] == "127.0.0.2"
    assert not result["options"][CONF_INVERT_POSITION]
    assert result["result"].unique_id == "12:34:56:78:90:ab"


async def test_zeroconf_duplicate_entry(
    hass: HomeAssistant, mock_slide_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test starting a flow from discovery."""

    MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: HOST}, unique_id="12:34:56:78:90:ab"
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=MOCK_ZEROCONF_DATA
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].data[CONF_HOST] == HOST


async def test_zeroconf_update_duplicate_entry(
    hass: HomeAssistant, mock_slide_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test updating an existing entry from discovery."""

    MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.3"}, unique_id="12:34:56:78:90:ab"
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=MOCK_ZEROCONF_DATA
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].data[CONF_HOST] == HOST


@pytest.mark.parametrize(
    ("exception"),
    [
        (ClientConnectionError),
        (ClientTimeoutError),
        (AuthenticationFailed),
        (DigestAuthCalcError),
        (Exception),
    ],
)
async def test_zeroconf_connection_error(
    hass: HomeAssistant,
    exception: Exception,
    mock_slide_api: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test starting a flow from discovery."""

    MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "slide_host"}, unique_id="12:34:56:78:90:cd"
    ).add_to_hass(hass)

    mock_slide_api.slide_info.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=MOCK_ZEROCONF_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_connection_failed"


async def test_options_flow(
    hass: HomeAssistant, mock_slide_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow works correctly."""
    await setup_platform(hass, mock_config_entry, [Platform.COVER])

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_INVERT_POSITION: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_INVERT_POSITION: True,
    }
