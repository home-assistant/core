"""Test the Matter config flow."""
from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import DEFAULT, AsyncMock, MagicMock, call, patch

from matter_server.client.exceptions import CannotConnect, InvalidServerVersion
import pytest

from homeassistant import config_entries
from homeassistant.components.hassio import HassioAPIError, HassioServiceInfo
from homeassistant.components.matter.const import ADDON_SLUG, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

ADDON_DISCOVERY_INFO = {
    "addon": "Matter Server",
    "host": "host1",
    "port": 5581,
}


@pytest.fixture(name="setup_entry", autouse=True)
def setup_entry_fixture() -> Generator[AsyncMock, None, None]:
    """Mock entry setup."""
    with patch(
        "homeassistant.components.matter.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="client_connect", autouse=True)
def client_connect_fixture() -> Generator[AsyncMock, None, None]:
    """Mock server version."""
    with patch(
        "homeassistant.components.matter.config_flow.MatterClient.connect"
    ) as client_connect:
        yield client_connect


@pytest.fixture(name="supervisor")
def supervisor_fixture() -> Generator[MagicMock, None, None]:
    """Mock Supervisor."""
    with patch(
        "homeassistant.components.matter.config_flow.is_hassio", return_value=True
    ) as is_hassio:
        yield is_hassio


@pytest.fixture(name="discovery_info")
def discovery_info_fixture() -> Any:
    """Return the discovery info from the supervisor."""
    return DEFAULT


@pytest.fixture(name="get_addon_discovery_info", autouse=True)
def get_addon_discovery_info_fixture(
    discovery_info: Any,
) -> Generator[AsyncMock, None, None]:
    """Mock get add-on discovery info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_discovery_info",
        return_value=discovery_info,
    ) as get_addon_discovery_info:
        yield get_addon_discovery_info


@pytest.fixture(name="addon_setup_time", autouse=True)
def addon_setup_time_fixture() -> Generator[int, None, None]:
    """Mock add-on setup sleep time."""
    with patch(
        "homeassistant.components.matter.config_flow.ADDON_SETUP_TIMEOUT", new=0
    ) as addon_setup_time:
        yield addon_setup_time


async def test_manual_create_entry(
    hass: HomeAssistant,
    client_connect: AsyncMock,
    setup_entry: AsyncMock,
) -> None:
    """Test user step create entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "ws://localhost:5580/ws",
        },
    )
    await hass.async_block_till_done()

    assert client_connect.call_count == 1
    assert result["type"] == FlowResultType.CREATE_ENTRY
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
    assert result["type"] == FlowResultType.FORM
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

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "ws://localhost:5580/ws",
        },
    )
    await hass.async_block_till_done()

    assert client_connect.call_count == 1
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfiguration_successful"
    assert entry.data["url"] == "ws://localhost:5580/ws"
    assert entry.data["use_addon"] is False
    assert entry.data["integration_created_addon"] is False
    assert entry.title == "Matter"
    assert setup_entry.call_count == 1


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
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
        ),
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert addon_info.call_count == 1
    assert client_connect.call_count == 0
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://host1:5581/ws",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert setup_entry.call_count == 1


@pytest.mark.parametrize(
    ("discovery_info", "error"),
    [({"config": ADDON_DISCOVERY_INFO}, HassioAPIError())],
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
        ),
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert addon_info.call_count == 1
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "addon_info_failed"


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
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
        ),
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": False}
    )

    assert addon_info.call_count == 0
    assert result["type"] == FlowResultType.FORM
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
    assert result["type"] == FlowResultType.CREATE_ENTRY
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
        ),
    )

    assert addon_info.call_count == 0
    assert result["type"] == FlowResultType.ABORT
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
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Matter Server",
            slug=ADDON_SLUG,
        ),
    )

    assert addon_info.call_count == 0
    assert result["type"] == FlowResultType.ABORT
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
        ),
    )

    assert addon_info.call_count == 0
    assert result["type"] == FlowResultType.ABORT
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
        ),
    )

    assert addon_info.call_count == 0
    assert result["step_id"] == "hassio_confirm"
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert addon_info.call_count == 1
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert start_addon.call_args == call(hass, "core_matter_server")
    assert client_connect.call_count == 1
    assert result["type"] == FlowResultType.CREATE_ENTRY
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
        ),
    )

    assert addon_info.call_count == 0
    assert addon_store_info.call_count == 0
    assert result["step_id"] == "hassio_confirm"
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert addon_info.call_count == 0
    assert addon_store_info.call_count == 1
    assert result["step_id"] == "install_addon"
    assert result["type"] == FlowResultType.SHOW_PROGRESS

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call(hass, "core_matter_server")
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert start_addon.call_args == call(hass, "core_matter_server")
    assert client_connect.call_count == 1
    assert result["type"] == FlowResultType.CREATE_ENTRY
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": False}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "ws://localhost:5581/ws",
        },
    )
    await hass.async_block_till_done()

    assert client_connect.call_count == 1
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter"
    assert result["data"] == {
        "url": "ws://localhost:5581/ws",
        "use_addon": False,
        "integration_created_addon": False,
    }
    assert setup_entry.call_count == 1


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )
    await hass.async_block_till_done()

    assert addon_info.call_count == 1
    assert client_connect.call_count == 1
    assert result["type"] == FlowResultType.CREATE_ENTRY
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
            {"config": ADDON_DISCOVERY_INFO},
            HassioAPIError(),
            None,
            None,
            "addon_get_discovery_info_failed",
            True,
            False,
        ),
        (
            {"config": ADDON_DISCOVERY_INFO},
            None,
            CannotConnect(Exception("Boom")),
            None,
            "cannot_connect",
            True,
            True,
        ),
        (
            None,
            None,
            None,
            None,
            "addon_get_discovery_info_failed",
            True,
            False,
        ),
        (
            {"config": ADDON_DISCOVERY_INFO},
            None,
            None,
            HassioAPIError(),
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert addon_info.call_count == 1
    assert get_addon_discovery_info.called is discovery_info_called
    assert client_connect.called is client_connect_called
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == abort_reason


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )
    await hass.async_block_till_done()

    assert addon_info.call_count == 1
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfiguration_successful"
    assert entry.data["url"] == "ws://host1:5581/ws"
    assert entry.title == "Matter"
    assert setup_entry.call_count == 1


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert addon_info.call_count == 1
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert start_addon.call_args == call(hass, "core_matter_server")
    assert result["type"] == FlowResultType.CREATE_ENTRY
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
            {"config": ADDON_DISCOVERY_INFO},
            HassioAPIError(),
            None,
            False,
            False,
        ),
        (
            {"config": ADDON_DISCOVERY_INFO},
            None,
            CannotConnect(Exception("Boom")),
            True,
            True,
        ),
        (
            None,
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert addon_info.call_count == 1
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert start_addon.call_args == call(hass, "core_matter_server")
    assert get_addon_discovery_info.called is discovery_info_called
    assert client_connect.called is client_connect_called
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "addon_start_failed"


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert addon_info.call_count == 1
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert start_addon.call_args == call(hass, "core_matter_server")
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfiguration_successful"
    assert entry.data["url"] == "ws://host1:5581/ws"
    assert entry.title == "Matter"
    assert setup_entry.call_count == 1


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert addon_info.call_count == 0
    assert addon_store_info.call_count == 1
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call(hass, "core_matter_server")
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert start_addon.call_args == call(hass, "core_matter_server")
    assert result["type"] == FlowResultType.CREATE_ENTRY
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
    install_addon.side_effect = HassioAPIError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call(hass, "core_matter_server")
    assert addon_info.call_count == 0
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "addon_install_failed"


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert addon_info.call_count == 0
    assert addon_store_info.call_count == 1
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call(hass, "core_matter_server")
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert start_addon.call_args == call(hass, "core_matter_server")
    assert client_connect.call_count == 1
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfiguration_successful"
    assert entry.data["url"] == "ws://host1:5581/ws"
    assert entry.title == "Matter"
    assert setup_entry.call_count == 1
