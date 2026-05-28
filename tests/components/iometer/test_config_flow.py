"""Test the IOmeter config flow."""

from ipaddress import ip_address
from unittest.mock import MagicMock

from iometer import IOmeterConnectionError, IOmeterNoStatusError, Status
import pytest

from homeassistant.components.iometer.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry, async_load_fixture

IP_ADDRESS = "10.0.0.2"
IOMETER_DEVICE_ID = "658c2b34-2017-45f2-a12b-731235f8bb97"

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address(IP_ADDRESS),
    ip_addresses=[ip_address(IP_ADDRESS)],
    hostname="IOmeter-EC63E8.local.",
    name="IOmeter-EC63E8",
    port=80,
    type="_iometer._tcp.",
    properties={},
)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
) -> None:
    """Test full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: IP_ADDRESS},
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IOmeter 1ISK0000000000"
    assert result["data"] == {CONF_HOST: IP_ADDRESS}
    assert result["result"].unique_id == IOMETER_DEVICE_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
) -> None:
    """Test zeroconf flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IOmeter 1ISK0000000000"
    assert result["data"] == {CONF_HOST: IP_ADDRESS}
    assert result["result"].unique_id == IOMETER_DEVICE_ID


async def test_zeroconf_flow_abort_duplicate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test zeroconf flow aborts with duplicate."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (IOmeterConnectionError(), "cannot_connect"),
        (IOmeterNoStatusError(), "no_status"),
    ],
    ids=["status-connection", "status-missing"],
)
async def test_zeroconf_flow_abort_errors(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test zeroconf flow aborts when the SSE client raises an exception."""
    mock_iometer_client.watch_status.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_zeroconf_flow_abort_no_meter(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
) -> None:
    """Test zeroconf flow aborts when the status contains no meter info."""
    mock_status = MagicMock()
    mock_status.meter = None

    async def no_meter_watch():
        yield mock_status

    mock_iometer_client.watch_status.side_effect = no_meter_watch

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_readings"


@pytest.mark.parametrize(
    ("exception", "error_key"),
    [
        (IOmeterConnectionError(), "cannot_connect"),
        (IOmeterNoStatusError(), "no_status"),
    ],
    ids=["status-connection", "status-missing"],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
    exception: Exception,
    error_key: str,
) -> None:
    """Test user flow shows errors for SSE client exceptions and recovers on retry."""
    call_count = {"n": 0}
    valid_status = Status.from_json(
        await async_load_fixture(hass, "status.json", DOMAIN)
    )

    async def success_watch():
        yield valid_status

    def conditional_watch():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise exception
        return success_watch()

    mock_iometer_client.watch_status.side_effect = conditional_watch

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: IP_ADDRESS},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: IP_ADDRESS},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_no_meter_error(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
) -> None:
    """Test user flow shows error when status contains no meter info."""
    call_count = {"n": 0}
    mock_status = MagicMock()
    mock_status.meter = None
    valid_status = Status.from_json(
        await async_load_fixture(hass, "status.json", DOMAIN)
    )

    async def conditional_watch():
        call_count["n"] += 1
        if call_count["n"] == 1:
            yield mock_status
        else:
            yield valid_status

    mock_iometer_client.watch_status.side_effect = conditional_watch

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: IP_ADDRESS},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_readings"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: IP_ADDRESS},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_abort_duplicate(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: IP_ADDRESS},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
