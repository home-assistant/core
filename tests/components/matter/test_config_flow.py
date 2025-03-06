"""Test the Matter config flow."""

from __future__ import annotations

from collections.abc import Generator
from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import uuid4

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import Discovery
from matter_server.client.exceptions import CannotConnect, InvalidServerVersion
import pytest

from homeassistant import config_entries
from homeassistant.components.matter.const import ADDON_SLUG, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

ADDON_DISCOVERY_INFO = {
    "addon": "Matter Server",
    "host": "host1",
    "port": 5581,
}
ZEROCONF_INFO_TCP = ZeroconfServiceInfo(
    ip_address=ip_address("fd11:be53:8d46:0:729e:5a4f:539d:1ee6"),
    ip_addresses=[ip_address("fd11:be53:8d46:0:729e:5a4f:539d:1ee6")],
    port=5540,
    hostname="CDEFGHIJ12345678.local.",
    type="_matter._tcp.local.",
    name="ABCDEFGH123456789-0000000012345678._matter._tcp.local.",
    properties={"SII": "3300", "SAI": "1100", "T": "0"},
)

ZEROCONF_INFO_UDP = ZeroconfServiceInfo(
    ip_address=ip_address("fd11:be53:8d46:0:729e:5a4f:539d:1ee6"),
    ip_addresses=[ip_address("fd11:be53:8d46:0:729e:5a4f:539d:1ee6")],
    port=5540,
    hostname="CDEFGHIJ12345678.local.",
    type="_matterc._udp.local.",
    name="ABCDEFGH123456789._matterc._udp.local.",
    properties={
        "VP": "4874+77",
        "DT": "21",
        "DN": "Eve Door",
        "SII": "3300",
        "SAI": "1100",
        "T": "0",
        "D": "183",
        "CM": "2",
        "RI": "0400530980B950D59BF473CFE42BD7DDBF2D",
        "PH": "36",
        "PI": None,
    },
)


@pytest.fixture(name="setup_entry", autouse=True)
def setup_entry_fixture() -> Generator[AsyncMock]:
    """Mock entry setup."""
    with patch(
        "homeassistant.components.matter.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="unload_entry", autouse=True)
def unload_entry_fixture() -> Generator[AsyncMock]:
    """Mock entry unload."""
    with patch(
        "homeassistant.components.matter.async_unload_entry", return_value=True
    ) as mock_unload_entry:
        yield mock_unload_entry


@pytest.fixture(name="client_connect", autouse=True)
def client_connect_fixture() -> Generator[AsyncMock]:
    """Mock server version."""
    with patch(
        "homeassistant.components.matter.config_flow.MatterClient.connect"
    ) as client_connect:
        yield client_connect


@pytest.fixture(name="supervisor")
def supervisor_fixture() -> Generator[MagicMock]:
    """Mock Supervisor."""
    with patch(
        "homeassistant.components.matter.config_flow.is_hassio", return_value=True
    ) as is_hassio:
        yield is_hassio


@pytest.fixture(autouse=True)
def mock_get_addon_discovery_info(get_addon_discovery_info: AsyncMock) -> None:
    """Mock get add-on discovery info."""


@pytest.fixture(name="addon_setup_time", autouse=True)
def addon_setup_time_fixture() -> Generator[int]:
    """Mock add-on setup sleep time."""
    with patch(
        "homeassistant.components.matter.config_flow.ADDON_SETUP_TIMEOUT", new=0
    ) as addon_setup_time:
        yield addon_setup_time


@pytest.fixture(name="not_onboarded")
def mock_onboarded_fixture() -> Generator[MagicMock]:
    """Mock that Home Assistant is not yet onboarded."""
    with patch(
        "homeassistant.components.matter.config_flow.async_is_onboarded",
        return_value=False,
    ) as mock_onboarded:
        yield mock_onboarded


async def test_manual_create_entry(
    hass: HomeAssistant,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
) -> None:
    """Test user step create entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "ws://localhost:5580/ws",
        },
    )
    await hass.async_block_till_done()

    assert client_connect.call_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://localhost:5580/ws",
        "integration_created_addon": False,
        "use_addon": False,
    }
    assert setup_entry.call_count == 1


@pytest.mark.parametrize(
    ("error", "side_effect"),
    [
        ("cannot_connect", CannotConnect(Exception("Boom"))),
        ("invalid_server_version", InvalidServerVersion("Invalid version")),
        ("unknown", Exception("Unknown boom")),
    ],
)
async def test_manual_errors(
    hass: HomeAssistant,
    client_connect: AsyncMock,
    error: str,
    side_effect: Exception,
) -> None:
    """Test user step cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    client_connect.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "ws://localhost:5580/ws",
        },
    )

    assert client_connect.call_count == 1
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_manual_already_configured(
    hass: HomeAssistant,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
) -> None:
    """Test manual step abort if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"url": "ws://host1:5581/ws"}, title="Matter"
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "ws://localhost:5580/ws",
        },
    )
    await hass.async_block_till_done()

    assert client_connect.call_count == 1
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfiguration_successful"
    assert entry.data["url"] == "ws://localhost:5580/ws"
    assert entry.data["use_addon"] is False
    assert entry.data["integration_created_addon"] is False
    assert entry.title == "Matter"
    assert setup_entry.call_count == 1


@pytest.mark.parametrize("zeroconf_info", [ZEROCONF_INFO_TCP, ZEROCONF_INFO_UDP])
async def test_zeroconf_discovery(
    hass: HomeAssistant,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
    zeroconf_info: ZeroconfServiceInfo,
) -> None:
    """Test flow started from Zeroconf discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "ws://localhost:5580/ws",
        },
    )
    await hass.async_block_till_done()

    assert client_connect.call_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://localhost:5580/ws",
        "integration_created_addon": False,
        "use_addon": False,
    }
    assert setup_entry.call_count == 1


@pytest.mark.parametrize("zeroconf_info", [ZEROCONF_INFO_TCP, ZEROCONF_INFO_UDP])
async def test_zeroconf_discovery_not_onboarded_not_supervisor(
    hass: HomeAssistant,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
    not_onboarded: MagicMock,
    zeroconf_info: ZeroconfServiceInfo,
) -> None:
    """Test flow started from Zeroconf discovery when not onboarded."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "ws://localhost:5580/ws",
        },
    )
    await hass.async_block_till_done()

    assert client_connect.call_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://localhost:5580/ws",
        "integration_created_addon": False,
        "use_addon": False,
    }
    assert setup_entry.call_count == 1


@pytest.mark.parametrize("zeroconf_info", [ZEROCONF_INFO_TCP, ZEROCONF_INFO_UDP])
@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_matter_server",
                service="matter",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_zeroconf_not_onboarded_already_discovered(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_info: AsyncMock,
    addon_running: AsyncMock,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
    not_onboarded: MagicMock,
    zeroconf_info: ZeroconfServiceInfo,
) -> None:
    """Test flow Zeroconf discovery when not onboarded and already discovered."""
    result_flow_1 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf_info,
    )
    result_flow_2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf_info,
    )
    await hass.async_block_till_done()
    assert result_flow_2["type"] is FlowResultType.ABORT
    assert result_flow_2["reason"] == "already_configured"
    assert addon_info.call_count == 1
    assert client_connect.call_count == 1
    assert result_flow_1["type"] is FlowResultType.CREATE_ENTRY
    assert result_flow_1["title"] == "Matter"
    assert result_flow_1["data"] == {
        "url": "ws://host1:5581/ws",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert setup_entry.call_count == 1


@pytest.mark.parametrize("zeroconf_info", [ZEROCONF_INFO_TCP, ZEROCONF_INFO_UDP])
@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_matter_server",
                service="matter",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_zeroconf_not_onboarded_running(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_info: AsyncMock,
    addon_running: AsyncMock,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
    not_onboarded: MagicMock,
    zeroconf_info: ZeroconfServiceInfo,
) -> None:
    """Test flow Zeroconf discovery when not onboarded and add-on running."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf_info,
    )
    await hass.async_block_till_done()

    assert addon_info.call_count == 1
    assert client_connect.call_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://host1:5581/ws",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert setup_entry.call_count == 1


@pytest.mark.parametrize("zeroconf_info", [ZEROCONF_INFO_TCP, ZEROCONF_INFO_UDP])
@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_matter_server",
                service="matter",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_zeroconf_not_onboarded_installed(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_info: AsyncMock,
    addon_installed: AsyncMock,
    start_addon: AsyncMock,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
    not_onboarded: MagicMock,
    zeroconf_info: ZeroconfServiceInfo,
) -> None:
    """Test flow Zeroconf discovery when not onboarded and add-on installed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf_info,
    )
    await hass.async_block_till_done()

    assert addon_info.call_count == 1
    assert start_addon.call_args == call("core_matter_server")
    assert client_connect.call_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://host1:5581/ws",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert setup_entry.call_count == 1


@pytest.mark.parametrize("zeroconf_info", [ZEROCONF_INFO_TCP, ZEROCONF_INFO_UDP])
@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_matter_server",
                service="matter",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_zeroconf_not_onboarded_not_installed(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_info: AsyncMock,
    addon_store_info: AsyncMock,
    addon_not_installed: AsyncMock,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
    not_onboarded: MagicMock,
    zeroconf_info: ZeroconfServiceInfo,
) -> None:
    """Test flow Zeroconf discovery when not onboarded and add-on not installed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf_info,
    )
    await hass.async_block_till_done()

    assert addon_info.call_count == 0
    assert addon_store_info.call_count == 2
    assert install_addon.call_args == call("core_matter_server")
    assert start_addon.call_args == call("core_matter_server")
    assert client_connect.call_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://host1:5581/ws",
        "use_addon": True,
        "integration_created_addon": True,
    }
    assert setup_entry.call_count == 1


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_matter_server",
                service="matter",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_supervisor_discovery(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_running: AsyncMock,
    addon_info: AsyncMock,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
) -> None:
    """Test flow started from Supervisor discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Matter Server",
            slug=ADDON_SLUG,
            uuid="1234",
        ),
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert addon_info.call_count == 1
    assert client_connect.call_count == 0
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://host1:5581/ws",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert setup_entry.call_count == 1


@pytest.mark.parametrize(
    ("discovery_info", "error"),
    [
        (
            [
                Discovery(
                    addon="core_matter_server",
                    service="matter",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            SupervisorError(),
        )
    ],
)
async def test_supervisor_discovery_addon_info_failed(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_running: AsyncMock,
    addon_info: AsyncMock,
    error: Exception,
) -> None:
    """Test Supervisor discovery and addon info failed."""
    addon_info.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Matter Server",
            slug=ADDON_SLUG,
            uuid="1234",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert addon_info.call_count == 1
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_info_failed"


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_matter_server",
                service="matter",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_clean_supervisor_discovery_on_user_create(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_running: AsyncMock,
    addon_info: AsyncMock,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
) -> None:
    """Test discovery flow is cleaned up when a user flow is finished."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Matter Server",
            slug=ADDON_SLUG,
            uuid="1234",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": False}
    )

    assert addon_info.call_count == 0
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "ws://localhost:5580/ws",
        },
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.flow.async_progress()) == 0
    assert client_connect.call_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://localhost:5580/ws",
        "use_addon": False,
        "integration_created_addon": False,
    }
    assert setup_entry.call_count == 1


async def test_abort_supervisor_discovery_with_existing_entry(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_running: AsyncMock,
    addon_info: AsyncMock,
) -> None:
    """Test discovery flow is aborted if an entry already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"url": "ws://localhost:5580/ws"},
        title="Matter",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Matter Server",
            slug=ADDON_SLUG,
            uuid="1234",
        ),
    )

    assert addon_info.call_count == 0
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_abort_supervisor_discovery_with_existing_flow(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_installed: AsyncMock,
    addon_info: AsyncMock,
) -> None:
    """Test hassio discovery flow is aborted when another flow is in progress."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Matter Server",
            slug=ADDON_SLUG,
            uuid="1234",
        ),
    )

    assert addon_info.call_count == 0
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_abort_supervisor_discovery_for_other_addon(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_installed: AsyncMock,
    addon_info: AsyncMock,
) -> None:
    """Test hassio discovery flow is aborted for a non official add-on discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config={
                "addon": "Other Matter Server",
                "host": "host1",
                "port": 3001,
            },
            name="Other Matter Server",
            slug="other_addon",
            uuid="1234",
        ),
    )

    assert addon_info.call_count == 0
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_matter_addon"


async def test_supervisor_discovery_addon_not_running(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_installed: AsyncMock,
    addon_info: AsyncMock,
    start_addon: AsyncMock,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
) -> None:
    """Test discovery with add-on already installed but not running."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Matter Server",
            slug=ADDON_SLUG,
            uuid="1234",
        ),
    )

    assert addon_info.call_count == 0
    assert result["step_id"] == "hassio_confirm"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert addon_info.call_count == 1
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert start_addon.call_args == call("core_matter_server")
    assert client_connect.call_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://host1:5581/ws",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert setup_entry.call_count == 1


async def test_supervisor_discovery_addon_not_installed(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_not_installed: AsyncMock,
    install_addon: AsyncMock,
    addon_info: AsyncMock,
    addon_store_info: AsyncMock,
    start_addon: AsyncMock,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
) -> None:
    """Test discovery with add-on not installed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Matter Server",
            slug=ADDON_SLUG,
            uuid="1234",
        ),
    )

    assert addon_info.call_count == 0
    assert addon_store_info.call_count == 0
    assert result["step_id"] == "hassio_confirm"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert addon_info.call_count == 0
    assert addon_store_info.call_count == 1
    assert result["step_id"] == "install_addon"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call("core_matter_server")
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert start_addon.call_args == call("core_matter_server")
    assert client_connect.call_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://host1:5581/ws",
        "use_addon": True,
        "integration_created_addon": True,
    }
    assert setup_entry.call_count == 1


async def test_not_addon(
    hass: HomeAssistant,
    supervisor: MagicMock,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
) -> None:
    """Test opting out of add-on on Supervisor."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "ws://localhost:5581/ws",
        },
    )
    await hass.async_block_till_done()

    assert client_connect.call_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://localhost:5581/ws",
        "use_addon": False,
        "integration_created_addon": False,
    }
    assert setup_entry.call_count == 1


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_matter_server",
                service="matter",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_addon_running(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_running: AsyncMock,
    addon_info: AsyncMock,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
) -> None:
    """Test add-on already running on Supervisor."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )
    await hass.async_block_till_done()

    assert addon_info.call_count == 1
    assert client_connect.call_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://host1:5581/ws",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert setup_entry.call_count == 1


@pytest.mark.parametrize(
    (
        "discovery_info",
        "discovery_info_error",
        "client_connect_error",
        "addon_info_error",
        "abort_reason",
        "discovery_info_called",
        "client_connect_called",
    ),
    [
        (
            [
                Discovery(
                    addon="core_matter_server",
                    service="matter",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            SupervisorError(),
            None,
            None,
            "addon_get_discovery_info_failed",
            True,
            False,
        ),
        (
            [
                Discovery(
                    addon="core_matter_server",
                    service="matter",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            None,
            CannotConnect(Exception("Boom")),
            None,
            "cannot_connect",
            True,
            True,
        ),
        (
            [],
            None,
            None,
            None,
            "addon_get_discovery_info_failed",
            True,
            False,
        ),
        (
            [
                Discovery(
                    addon="core_matter_server",
                    service="matter",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            None,
            None,
            SupervisorError(),
            "addon_info_failed",
            False,
            False,
        ),
    ],
)
async def test_addon_running_failures(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_running: AsyncMock,
    addon_info: AsyncMock,
    get_addon_discovery_info: AsyncMock,
    client_connect: AsyncMock,
    discovery_info_error: Exception | None,
    client_connect_error: Exception | None,
    addon_info_error: Exception | None,
    abort_reason: str,
    discovery_info_called: bool,
    client_connect_called: bool,
) -> None:
    """Test all failures when add-on is running."""
    get_addon_discovery_info.side_effect = discovery_info_error
    client_connect.side_effect = client_connect_error
    addon_info.side_effect = addon_info_error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert addon_info.call_count == 1
    assert get_addon_discovery_info.called is discovery_info_called
    assert client_connect.called is client_connect_called
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == abort_reason


@pytest.mark.parametrize("zeroconf_info", [ZEROCONF_INFO_TCP, ZEROCONF_INFO_UDP])
@pytest.mark.parametrize(
    (
        "discovery_info",
        "discovery_info_error",
        "client_connect_error",
        "addon_info_error",
        "abort_reason",
        "discovery_info_called",
        "client_connect_called",
    ),
    [
        (
            [
                Discovery(
                    addon="core_matter_server",
                    service="matter",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            SupervisorError(),
            None,
            None,
            "addon_get_discovery_info_failed",
            True,
            False,
        ),
        (
            [
                Discovery(
                    addon="core_matter_server",
                    service="matter",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            None,
            CannotConnect(Exception("Boom")),
            None,
            "cannot_connect",
            True,
            True,
        ),
        (
            [],
            None,
            None,
            None,
            "addon_get_discovery_info_failed",
            True,
            False,
        ),
        (
            [
                Discovery(
                    addon="core_matter_server",
                    service="matter",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            None,
            None,
            SupervisorError(),
            "addon_info_failed",
            False,
            False,
        ),
    ],
)
async def test_addon_running_failures_zeroconf(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_running: AsyncMock,
    addon_info: AsyncMock,
    get_addon_discovery_info: AsyncMock,
    client_connect: AsyncMock,
    discovery_info_error: Exception | None,
    client_connect_error: Exception | None,
    addon_info_error: Exception | None,
    abort_reason: str,
    discovery_info_called: bool,
    client_connect_called: bool,
    not_onboarded: MagicMock,
    zeroconf_info: ZeroconfServiceInfo,
) -> None:
    """Test all failures when add-on is running and not onboarded."""
    get_addon_discovery_info.side_effect = discovery_info_error
    client_connect.side_effect = client_connect_error
    addon_info.side_effect = addon_info_error
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf_info,
    )
    await hass.async_block_till_done()

    assert addon_info.call_count == 1
    assert get_addon_discovery_info.called is discovery_info_called
    assert client_connect.called is client_connect_called
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == abort_reason


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_matter_server",
                service="matter",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_addon_running_already_configured(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_running: AsyncMock,
    addon_info: AsyncMock,
    setup_entry: AsyncMock,
) -> None:
    """Test that only one instance is allowed when add-on is running."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "url": "ws://localhost:5580/ws",
        },
        title="Matter",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )
    await hass.async_block_till_done()

    assert addon_info.call_count == 1
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfiguration_successful"
    assert entry.data["url"] == "ws://host1:5581/ws"
    assert entry.title == "Matter"
    assert setup_entry.call_count == 1


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_matter_server",
                service="matter",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_addon_installed(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_installed: AsyncMock,
    addon_info: AsyncMock,
    start_addon: AsyncMock,
    setup_entry: AsyncMock,
) -> None:
    """Test add-on already installed but not running on Supervisor."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert addon_info.call_count == 1
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert start_addon.call_args == call("core_matter_server")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://host1:5581/ws",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert setup_entry.call_count == 1


@pytest.mark.parametrize(
    (
        "discovery_info",
        "start_addon_error",
        "client_connect_error",
        "discovery_info_called",
        "client_connect_called",
    ),
    [
        (
            [
                Discovery(
                    addon="core_matter_server",
                    service="matter",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            SupervisorError(),
            None,
            False,
            False,
        ),
        (
            [
                Discovery(
                    addon="core_matter_server",
                    service="matter",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            None,
            CannotConnect(Exception("Boom")),
            True,
            True,
        ),
        (
            [],
            None,
            None,
            True,
            False,
        ),
    ],
)
async def test_addon_installed_failures(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_installed: AsyncMock,
    addon_info: AsyncMock,
    start_addon: AsyncMock,
    get_addon_discovery_info: AsyncMock,
    client_connect: AsyncMock,
    start_addon_error: Exception | None,
    client_connect_error: Exception | None,
    discovery_info_called: bool,
    client_connect_called: bool,
) -> None:
    """Test add-on start failure when add-on is installed."""
    start_addon.side_effect = start_addon_error
    client_connect.side_effect = client_connect_error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert addon_info.call_count == 1
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert start_addon.call_args == call("core_matter_server")
    assert get_addon_discovery_info.called is discovery_info_called
    assert client_connect.called is client_connect_called
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_start_failed"


@pytest.mark.parametrize("zeroconf_info", [ZEROCONF_INFO_TCP, ZEROCONF_INFO_UDP])
@pytest.mark.parametrize(
    (
        "discovery_info",
        "start_addon_error",
        "client_connect_error",
        "discovery_info_called",
        "client_connect_called",
    ),
    [
        (
            [
                Discovery(
                    addon="core_matter_server",
                    service="matter",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            SupervisorError(),
            None,
            False,
            False,
        ),
        (
            [
                Discovery(
                    addon="core_matter_server",
                    service="matter",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            None,
            CannotConnect(Exception("Boom")),
            True,
            True,
        ),
        (
            [],
            None,
            None,
            True,
            False,
        ),
    ],
)
async def test_addon_installed_failures_zeroconf(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_installed: AsyncMock,
    addon_info: AsyncMock,
    start_addon: AsyncMock,
    get_addon_discovery_info: AsyncMock,
    client_connect: AsyncMock,
    start_addon_error: Exception | None,
    client_connect_error: Exception | None,
    discovery_info_called: bool,
    client_connect_called: bool,
    not_onboarded: MagicMock,
    zeroconf_info: ZeroconfServiceInfo,
) -> None:
    """Test add-on start failure when add-on is installed and not onboarded."""
    start_addon.side_effect = start_addon_error
    client_connect.side_effect = client_connect_error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zeroconf_info
    )
    await hass.async_block_till_done()

    assert addon_info.call_count == 1
    assert start_addon.call_args == call("core_matter_server")
    assert get_addon_discovery_info.called is discovery_info_called
    assert client_connect.called is client_connect_called
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_start_failed"


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_matter_server",
                service="matter",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_addon_installed_already_configured(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_installed: AsyncMock,
    addon_info: AsyncMock,
    start_addon: AsyncMock,
    setup_entry: AsyncMock,
) -> None:
    """Test that only one instance is allowed when add-on is installed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "url": "ws://localhost:5580/ws",
        },
        title="Matter",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert addon_info.call_count == 1
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert start_addon.call_args == call("core_matter_server")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfiguration_successful"
    assert entry.data["url"] == "ws://host1:5581/ws"
    assert entry.title == "Matter"
    assert setup_entry.call_count == 1


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_matter_server",
                service="matter",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_addon_not_installed(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_not_installed: AsyncMock,
    install_addon: AsyncMock,
    addon_info: AsyncMock,
    addon_store_info: AsyncMock,
    start_addon: AsyncMock,
    setup_entry: AsyncMock,
) -> None:
    """Test add-on not installed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert addon_info.call_count == 0
    assert addon_store_info.call_count == 1
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call("core_matter_server")
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert start_addon.call_args == call("core_matter_server")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://host1:5581/ws",
        "use_addon": True,
        "integration_created_addon": True,
    }
    assert setup_entry.call_count == 1


async def test_addon_not_installed_failures(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_not_installed: AsyncMock,
    addon_info: AsyncMock,
    install_addon: AsyncMock,
) -> None:
    """Test add-on install failure."""
    install_addon.side_effect = SupervisorError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call("core_matter_server")
    assert addon_info.call_count == 0
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_install_failed"


@pytest.mark.parametrize("zeroconf_info", [ZEROCONF_INFO_TCP, ZEROCONF_INFO_UDP])
async def test_addon_not_installed_failures_zeroconf(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_not_installed: AsyncMock,
    addon_info: AsyncMock,
    install_addon: AsyncMock,
    not_onboarded: MagicMock,
    zeroconf_info: ZeroconfServiceInfo,
) -> None:
    """Test add-on install failure."""
    install_addon.side_effect = SupervisorError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zeroconf_info
    )
    await hass.async_block_till_done()

    assert install_addon.call_args == call("core_matter_server")
    assert addon_info.call_count == 0
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_install_failed"


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_matter_server",
                service="matter",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_addon_not_installed_already_configured(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_not_installed: AsyncMock,
    addon_info: AsyncMock,
    addon_store_info: AsyncMock,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
) -> None:
    """Test that only one instance is allowed when add-on is not installed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "url": "ws://localhost:5580/ws",
        },
        title="Matter",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert addon_info.call_count == 0
    assert addon_store_info.call_count == 1
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call("core_matter_server")
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert start_addon.call_args == call("core_matter_server")
    assert client_connect.call_count == 1
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfiguration_successful"
    assert entry.data["url"] == "ws://host1:5581/ws"
    assert entry.title == "Matter"
    assert setup_entry.call_count == 1
