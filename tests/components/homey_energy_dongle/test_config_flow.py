"""Test the Homey Energy Dongle config flow."""

from ipaddress import ip_address
from unittest.mock import MagicMock, call

from dsmr_parser.parsers import TelegramParser
from homey_energy_dongle_ws import (
    ConnectionLimitError,
    ConnectionLostError,
    LocalApiDisabledError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.homey_energy_dongle.const import (
    CONF_DSMR_VERSION,
    CONF_WS_PATH,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import DONGLE_ID, EQUIPMENT_IDENTIFIER
from .conftest import TelegramQueue

USER_INPUT = {CONF_HOST: "192.168.1.88"}


def _unknown_telegram() -> str:
    """Return a telegram whose profile this library does not recognize."""
    body = (
        "/ISk5\\2MT382-1000\r\n"
        "\r\n"
        "1-0:0.0.0(00000000)\r\n"
        f"0-0:96.1.1({EQUIPMENT_IDENTIFIER})\r\n"
        "1-0:1.8.1(000004.426*kWh)\r\n"
        "!"
    )
    return f"{body}{TelegramParser.crc16(body):04X}\r\n"


DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.50"),
    ip_addresses=[ip_address("192.168.1.50")],
    hostname="energy.local.",
    name=f"Homey Energy Dongle {DONGLE_ID}._energydongle._tcp.local.",
    port=80,
    properties={"p": "/ws", "v": "1.0"},
    type="_energydongle._tcp.local.",
)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(
    hass: HomeAssistant,
    mock_client: MagicMock,
    telegrams: TelegramQueue,
    telegram_data: str,
) -> None:
    """Test manual setup detects DSMR 5 and disconnects.

    Without mDNS there is no dongle ID, so the entry is matched on host.
    """
    telegrams.put_nowait(telegram_data)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Homey Energy Dongle"
    assert result["data"] == {
        CONF_HOST: "192.168.1.88",
        CONF_PORT: 80,
        CONF_WS_PATH: "/ws",
        CONF_DSMR_VERSION: "5",
    }
    assert result["result"].unique_id is None
    # The dongle allows two connections, so the probe must release its own.
    mock_client.return_value.__aexit__.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("error", "reason"),
    [
        pytest.param(
            LocalApiDisabledError("Local API disabled"),
            "local_api_disabled",
            id="local_api",
        ),
        pytest.param(
            ConnectionLimitError("Connection limit reached"),
            "too_many_connections",
            id="limit",
        ),
        pytest.param(ConnectionLostError("refused"), "cannot_connect", id="lost"),
        pytest.param(RuntimeError(), "unknown", id="unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    telegrams: TelegramQueue,
    telegram_data: str,
    error: Exception,
    reason: str,
) -> None:
    """Test errors are shown and the flow can recover."""
    telegrams.put_nowait(error)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    telegrams.put_nowait(telegram_data)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_unknown_version(
    hass: HomeAssistant, telegrams: TelegramQueue
) -> None:
    """Test an unrecognized telegram asks for the meter profile."""
    telegrams.put_nowait(_unknown_telegram())
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dsmr_version"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DSMR_VERSION: "Q3D"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DSMR_VERSION] == "Q3D"
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_invalid_checksum_asks_then_rejects_same_profile(
    hass: HomeAssistant, telegrams: TelegramQueue, telegram_data: str
) -> None:
    """Test a detected profile that fails checksum is not stored."""
    telegrams.put_nowait(telegram_data.replace("!EFF0\r\n", "!0000\r\n"))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dsmr_version"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DSMR_VERSION: "5"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_dsmr_version"}

    # DSMR 2.2 does not validate the CRC, so the same telegram can still be stored.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DSMR_VERSION: "2.2"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DSMR_VERSION] == "2.2"


async def test_user_flow_known_host(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test a dongle can't be added twice by its address, without connecting."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_client.assert_not_called()


async def test_zeroconf_host_added_during_confirm(
    hass: HomeAssistant, telegrams: TelegramQueue, telegram_data: str
) -> None:
    """Test a dongle added by address while discovery waits doesn't get added twice."""
    telegrams.put_nowait(telegram_data)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY
    )
    assert result["step_id"] == "zeroconf_confirm"
    MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.50"}).add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_client: MagicMock,
    telegrams: TelegramQueue,
    telegram_data: str,
) -> None:
    """Test discovery detects the profile and confirms without connecting again."""
    telegrams.put_nowait(telegram_data)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {
        "name": "Homey Energy Dongle (37e4)",
        "version": "DSMR 5",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Homey Energy Dongle (37e4)"
    assert result["data"] == {
        CONF_HOST: "192.168.1.50",
        CONF_PORT: 80,
        CONF_WS_PATH: "/ws",
        CONF_DSMR_VERSION: "5",
    }
    assert result["result"].unique_id == DONGLE_ID
    assert mock_client.call_args_list == [
        call("192.168.1.50", port=80, path="/ws", reconnect=False, dsmr_version=None),
    ]


async def test_zeroconf_updates_host(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test discovery of a configured dongle on a new address updates the entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.50"
    mock_client.assert_not_called()


@pytest.mark.parametrize(
    ("unique_id", "expected_unique_id"),
    [
        pytest.param(None, DONGLE_ID, id="added_by_address"),
        pytest.param("aaaa", "aaaa", id="other_dongle"),
    ],
)
async def test_zeroconf_known_host(
    hass: HomeAssistant,
    mock_client: MagicMock,
    unique_id: str | None,
    expected_unique_id: str,
) -> None:
    """Test discovery of a configured address aborts without connecting.

    An entry added by address learns the dongle ID, so it can follow the
    dongle to a new address.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=unique_id, data={CONF_HOST: "192.168.1.50"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == expected_unique_id
    mock_client.assert_not_called()


@pytest.mark.usefixtures("mock_setup_entry", "mock_onboarding")
async def test_zeroconf_during_onboarding(
    hass: HomeAssistant, telegrams: TelegramQueue, telegram_data: str
) -> None:
    """Test discovery creates the entry without confirmation during onboarding."""
    telegrams.put_nowait(telegram_data)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DSMR_VERSION] == "5"
    assert result["result"].unique_id == DONGLE_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_confirm_error(
    hass: HomeAssistant, telegrams: TelegramQueue, telegram_data: str
) -> None:
    """Test connection errors are shown on confirmation and can recover."""
    telegrams.put_nowait(ConnectionLostError("refused"))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_meter"
    assert result["errors"] == {}

    telegrams.put_nowait(ConnectionLostError("refused"))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    telegrams.put_nowait(telegram_data)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DSMR_VERSION] == "5"
    assert result["result"].unique_id == DONGLE_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_unknown_version(
    hass: HomeAssistant, telegrams: TelegramQueue
) -> None:
    """Test discovery of an unrecognized telegram asks for the meter profile."""
    telegrams.put_nowait(_unknown_telegram())
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dsmr_version"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DSMR_VERSION: "5"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Homey Energy Dongle (37e4)"
    assert result["data"] == {
        CONF_HOST: "192.168.1.50",
        CONF_PORT: 80,
        CONF_WS_PATH: "/ws",
        CONF_DSMR_VERSION: "5",
    }
    assert result["result"].unique_id == DONGLE_ID


async def test_zeroconf_confirm_unknown_version(
    hass: HomeAssistant, telegrams: TelegramQueue
) -> None:
    """Test an unrecognized telegram read on confirmation asks for the profile."""
    telegrams.put_nowait(ConnectionLostError("refused"))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY
    )
    assert result["step_id"] == "zeroconf_meter"

    telegrams.put_nowait(_unknown_telegram())
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dsmr_version"


async def test_zeroconf_already_in_progress(
    hass: HomeAssistant, telegrams: TelegramQueue
) -> None:
    """Test a second discovery of the same dongle aborts."""
    telegrams.put_nowait(ConnectionLostError("refused"))
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_zeroconf_ignore_unreadable_dongle(
    hass: HomeAssistant, telegrams: TelegramQueue
) -> None:
    """Test a dongle that can't be read can be ignored and stays ignored."""
    telegrams.put_nowait(LocalApiDisabledError("Local API disabled"))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY
    )
    assert result["step_id"] == "zeroconf_meter"

    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IGNORE},
        data={"unique_id": DONGLE_ID, "title": "Homey Energy Dongle (37e4)"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    telegrams: TelegramQueue,
    telegram_data: str,
) -> None:
    """Test the host and DSMR version can be changed after errors."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_input = {CONF_HOST: "192.168.1.99", CONF_DSMR_VERSION: "4"}
    telegrams.put_nowait(ConnectionLostError("refused"))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=new_input
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    telegrams.put_nowait(telegram_data)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=new_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_HOST: "192.168.1.99",
        CONF_PORT: 80,
        CONF_WS_PATH: "/ws",
        CONF_DSMR_VERSION: "4",
    }
    # Another dongle can answer on the new address; discovery tells which.
    assert mock_config_entry.unique_id is None


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_rejects_unparsed_telegram(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    telegrams: TelegramQueue,
    telegram_data: str,
) -> None:
    """Test a telegram the chosen profile cannot parse is rejected immediately."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    user_input = {CONF_HOST: mock_config_entry.data[CONF_HOST], CONF_DSMR_VERSION: "5"}
    telegrams.put_nowait(telegram_data.replace("!EFF0\r\n", "!0000\r\n"))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_dsmr_version"}

    telegrams.put_nowait(telegram_data)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.unique_id == DONGLE_ID


async def test_reconfigure_to_host_in_use(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Test an entry can't move to the address of another entry's dongle."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.99"}).add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.99",
            CONF_DSMR_VERSION: mock_config_entry.data[CONF_DSMR_VERSION],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.88"
    mock_client.assert_not_called()
