"""Define tests for the Lunatone config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

import aiohttp
from lunatone_rest_api_client.models import InfoData
import pytest
from yarl import URL

from homeassistant.components.lunatone.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import (
    BASE_IP,
    BASE_URL,
    INFO_DATA,
    LEGACY_INFO_DATA,
    MANUFACTURER,
    UUID,
    setup_integration,
)

from tests.common import MockConfigEntry

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address(BASE_IP),
    ip_addresses=[ip_address(BASE_IP)],
    hostname="dali2_display.local.",
    name="DALI-2 Display._http._tcp.local.",
    port=80,
    type="_http._tcp.local.",
    properties={
        "path": "/",
        "manufacturer": MANUFACTURER.lower(),
        "device": "dali-2 display",
        "uid": UUID.lower(),
        "type": "dali-2-display",
    },
)


@pytest.mark.parametrize(("info_data"), [INFO_DATA, LEGACY_INFO_DATA])
async def test_full_flow(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_setup_entry: AsyncMock,
    info_data: InfoData,
) -> None:
    """Test full user flow."""
    mock_lunatone_info.set_data(info_data)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: BASE_URL},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == BASE_URL
    assert result["data"] == {CONF_URL: BASE_URL}


async def test_full_flow_fail_because_of_missing_device_infos(
    hass: HomeAssistant, mock_lunatone_info: AsyncMock
) -> None:
    """Test full flow."""
    mock_lunatone_info.serial_number = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: BASE_URL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "missing_device_info"}


async def test_device_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the flow is aborted when the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: BASE_URL},
    )

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "already_configured"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (aiohttp.InvalidUrlClientError(BASE_URL), "invalid_url"),
        (aiohttp.ClientConnectionError(), "cannot_connect"),
    ],
)
async def test_user_step_fail_with_error(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test user step with an error."""
    mock_lunatone_info.async_update.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: BASE_URL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_lunatone_info.async_update.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: BASE_URL},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == BASE_URL
    assert result["data"] == {CONF_URL: BASE_URL}


async def test_zeroconf_flow(
    hass: HomeAssistant, mock_lunatone_devices: AsyncMock, mock_lunatone_info: AsyncMock
) -> None:
    """Test zeroconf flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == BASE_URL
    assert result["data"] == {CONF_URL: BASE_URL}
    assert result["result"].unique_id == UUID.replace("-", "")


async def test_zeroconf_flow_abort_duplicate(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test zeroconf flow aborts with duplicate."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (aiohttp.InvalidUrlClientError(BASE_URL), "invalid_url"),
        (aiohttp.ClientConnectionError(), "cannot_connect"),
    ],
)
async def test_zeroconf_flow_abort_with_error(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test zeroconf flow aborts with error."""

    mock_lunatone_info.async_update.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_error

    mock_lunatone_info.async_update.side_effect = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_reconfigure(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""
    url = URL.build(scheme="http", host="10.0.0.100").human_repr()[:-1]

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: url}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_URL: url}


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (aiohttp.InvalidUrlClientError(BASE_URL), "invalid_url"),
        (aiohttp.ClientConnectionError(), "cannot_connect"),
    ],
)
async def test_reconfigure_fail_with_error(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test reconfigure flow with an error."""
    url = URL.build(scheme="http", host="10.0.0.100").human_repr()[:-1]

    mock_lunatone_info.async_update.side_effect = exception

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: url}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_lunatone_info.async_update.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: url}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_URL: url}
