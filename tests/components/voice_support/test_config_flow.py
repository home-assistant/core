"""Test the Voice support config flow."""

import asyncio
from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock, call, patch

from aiohasupervisor import SupervisorError
import aiohttp
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.voice_support.app import APP_SLUG
from homeassistant.components.voice_support.config_flow import (
    CONF_USE_APP,
    ISSUE_APP_SETUP_FAILED,
)
from homeassistant.components.voice_support.const import (
    CONF_INTEGRATION_CREATED_APP,
    DOMAIN,
)
from homeassistant.config_entries import (
    SOURCE_HASSIO,
    SOURCE_SYSTEM,
    SOURCE_USER,
    SOURCE_ZEROCONF,
    ConfigEntryState,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import APP_HOST, APP_INFO_URL, HOST, INFO, INFO_URL, PORT

HASSIO_DATA = HassioServiceInfo(
    config={"host": APP_HOST, "port": PORT},
    name="Voice",
    slug=APP_SLUG,
    uuid="1234",
)

ZEROCONF_DATA = ZeroconfServiceInfo(
    ip_address=ip_address(HOST),
    ip_addresses=[ip_address(HOST)],
    hostname="voice.local.",
    name="Voice._voice-support._tcp.local.",
    port=PORT,
    properties={},
    type="_voice-support._tcp.local.",
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("labs")
async def test_user_flow_feature_off(hass: HomeAssistant) -> None:
    """Test nothing can be set up until the feature is on."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "preview_feature_disabled"


@pytest.mark.usefixtures("preview_feature_enabled", "app_info")
async def test_manual_flow(hass: HomeAssistant) -> None:
    """Test saying where the app runs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Voice"
    assert result["data"] == {CONF_HOST: HOST, CONF_PORT: PORT}


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        pytest.param({"exc": aiohttp.ClientError}, "cannot_connect", id="unreachable"),
        pytest.param({"json": {"name": "Voice"}}, "cannot_connect", id="malformed"),
        pytest.param(
            {"json": {**INFO, "api_version": 2}}, "unsupported_version", id="version"
        ),
    ],
)
@pytest.mark.usefixtures("preview_feature_enabled")
async def test_manual_flow_cannot_use_app(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    reason: str,
) -> None:
    """Test an app that does not answer, or cannot be used, can be tried again."""
    aioclient_mock.get(INFO_URL, **response)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, json=INFO)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("preview_feature_enabled", "app_info")
async def test_manual_flows_at_once(hass: HomeAssistant) -> None:
    """Test two people saying where the app runs do not make two entries."""
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        first["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_configure(
        second["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("preview_feature_enabled")
async def test_user_flow_single_instance(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test there is one app."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.usefixtures("supervisor", "preview_feature_enabled")
async def test_on_supervisor_without_app(hass: HomeAssistant) -> None:
    """Test opting out of the app on Supervisor leads to manual setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: False}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


@pytest.mark.usefixtures(
    "supervisor",
    "preview_feature_enabled",
    "app_info",
    "addon_not_installed",
    "get_addon_discovery_info",
)
async def test_app_not_installed(
    hass: HomeAssistant, install_addon: AsyncMock, start_addon: AsyncMock
) -> None:
    """Test installing and starting the app."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_app"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert install_addon.call_args == call(APP_SLUG)
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_app"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert start_addon.call_args == call(APP_SLUG)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Voice"
    assert result["data"] == {
        CONF_HOST: APP_HOST,
        CONF_PORT: PORT,
        CONF_INTEGRATION_CREATED_APP: True,
    }


@pytest.mark.usefixtures(
    "supervisor",
    "preview_feature_enabled",
    "app_info",
    "addon_installed",
    "get_addon_discovery_info",
)
async def test_app_installed_not_running(
    hass: HomeAssistant, install_addon: AsyncMock, start_addon: AsyncMock
) -> None:
    """Test starting an installed app."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_app"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert install_addon.call_count == 0
    assert start_addon.call_args == call(APP_SLUG)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: APP_HOST, CONF_PORT: PORT}


@pytest.mark.usefixtures(
    "supervisor",
    "preview_feature_enabled",
    "app_info",
    "addon_running",
    "get_addon_discovery_info",
)
async def test_app_running(
    hass: HomeAssistant, install_addon: AsyncMock, start_addon: AsyncMock
) -> None:
    """Test using an already running app."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )

    assert install_addon.call_count == 0
    assert start_addon.call_count == 0
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: APP_HOST, CONF_PORT: PORT}


@pytest.mark.parametrize(
    ("discovery_failure", "info_response", "reason"),
    [
        pytest.param(
            SupervisorError(),
            {"json": INFO},
            "app_get_discovery_info_failed",
            id="info",
        ),
        pytest.param(
            None, {"exc": aiohttp.ClientError}, "cannot_connect", id="unreachable"
        ),
        pytest.param(
            None,
            {"json": {**INFO, "api_version": 2}},
            "unsupported_version",
            id="version",
        ),
    ],
)
@pytest.mark.usefixtures(
    "supervisor",
    "preview_feature_enabled",
    "addon_running",
    "install_addon",
    "start_addon",
)
async def test_app_running_cannot_be_used(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_addon_discovery_info: AsyncMock,
    discovery_failure: Exception | None,
    info_response: dict[str, Any],
    reason: str,
) -> None:
    """Test a running app that cannot be reached, or used, is reported."""
    get_addon_discovery_info.side_effect = discovery_failure
    aioclient_mock.get(APP_INFO_URL, **info_response)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures(
    "supervisor", "preview_feature_enabled", "addon_not_installed", "start_addon"
)
async def test_app_install_failed(
    hass: HomeAssistant, install_addon: AsyncMock
) -> None:
    """Test a failed installation is reported."""
    install_addon.side_effect = SupervisorError()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "app_install_failed"


@pytest.mark.usefixtures(
    "supervisor", "preview_feature_enabled", "addon_installed", "install_addon"
)
async def test_app_start_failed(hass: HomeAssistant, start_addon: AsyncMock) -> None:
    """Test a failed start is reported."""
    start_addon.side_effect = SupervisorError()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "app_start_failed"


@pytest.mark.usefixtures(
    "supervisor",
    "preview_feature_enabled",
    "addon_installed",
    "install_addon",
    "start_addon",
    "get_addon_discovery_info",
)
async def test_app_start_unsupported_version(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an app that starts speaking another protocol version is reported."""
    aioclient_mock.get(APP_INFO_URL, json={**INFO, "api_version": 2})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_version"


@pytest.mark.usefixtures(
    "supervisor", "preview_feature_enabled", "addon_installed", "install_addon"
)
async def test_app_start_timeout(
    hass: HomeAssistant, start_addon: AsyncMock, get_addon_discovery_info: AsyncMock
) -> None:
    """Test an app that never answers after starting is reported."""
    get_addon_discovery_info.return_value = []
    with patch(
        "homeassistant.components.voice_support.config_flow.APP_START_ROUNDS", 2
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USE_APP: True}
        )
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "app_start_failed"


@pytest.mark.usefixtures("supervisor", "preview_feature_enabled", "addon_store_info")
async def test_app_info_failed(
    hass: HomeAssistant, addon_store_info: AsyncMock
) -> None:
    """Test the Supervisor not answering about the app is reported."""
    addon_store_info.side_effect = SupervisorError()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "app_info_failed"


@pytest.mark.usefixtures(
    "supervisor",
    "preview_feature_enabled",
    "app_info",
    "addon_not_installed",
    "get_addon_discovery_info",
)
async def test_system_flow(
    hass: HomeAssistant,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the app is set up with nobody watching, from install to entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SYSTEM}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert install_addon.call_args == call(APP_SLUG)
    assert start_addon.call_args == call(APP_SLUG)
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_SYSTEM
    assert entries[0].data == {
        CONF_HOST: APP_HOST,
        CONF_PORT: PORT,
        CONF_INTEGRATION_CREATED_APP: True,
    }
    assert not issue_registry.issues


@pytest.mark.usefixtures("supervisor", "preview_feature_enabled")
async def test_system_flow_with_an_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test nothing is set up behind the person's back when they have an app."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SYSTEM}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("supervisor", "labs")
async def test_system_flow_feature_off(hass: HomeAssistant) -> None:
    """Test the system flow does nothing with the feature off."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SYSTEM}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "preview_feature_disabled"


@pytest.mark.usefixtures(
    "supervisor", "preview_feature_enabled", "addon_not_installed", "start_addon"
)
async def test_system_flow_failure_leaves_an_issue(
    hass: HomeAssistant,
    install_addon: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a silent flow that fails says so in Repairs."""
    install_addon.side_effect = SupervisorError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SYSTEM}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "app_install_failed"
    assert not hass.config_entries.async_entries(DOMAIN)
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_APP_SETUP_FAILED)
    assert issue is not None
    assert issue.translation_key == ISSUE_APP_SETUP_FAILED


@pytest.mark.usefixtures(
    "supervisor",
    "preview_feature_enabled",
    "app_info",
    "addon_running",
    "get_addon_discovery_info",
)
async def test_system_flow_success_clears_the_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a later success takes the complaint back."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_APP_SETUP_FAILED,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_APP_SETUP_FAILED,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SYSTEM}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_APP_SETUP_FAILED) is None


@pytest.mark.usefixtures("preview_feature_enabled", "app_info")
async def test_hassio_flow(hass: HomeAssistant) -> None:
    """Test the app announcing itself gets an entry without a word."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=HASSIO_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Voice"
    assert result["data"] == {CONF_HOST: APP_HOST, CONF_PORT: PORT}


@pytest.mark.usefixtures("labs")
async def test_hassio_flow_feature_off(hass: HomeAssistant) -> None:
    """Test the app announcing itself is ignored with the feature off."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=HASSIO_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "preview_feature_disabled"


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        pytest.param({"exc": aiohttp.ClientError}, "cannot_connect", id="unreachable"),
        pytest.param({"json": {"name": "Voice"}}, "cannot_connect", id="malformed"),
        pytest.param(
            {"json": {**INFO, "api_version": 2}}, "unsupported_version", id="version"
        ),
    ],
)
@pytest.mark.usefixtures("preview_feature_enabled")
async def test_hassio_flow_cannot_use_app(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    reason: str,
) -> None:
    """Test an announced app that does not answer, or cannot be used, gets no entry."""
    aioclient_mock.get(APP_INFO_URL, **response)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=HASSIO_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures(
    "supervisor",
    "preview_feature_enabled",
    "app_info",
    "addon_not_installed",
    "start_addon",
    "get_addon_discovery_info",
)
async def test_hassio_flow_while_system_flow_runs(
    hass: HomeAssistant, install_addon: AsyncMock
) -> None:
    """Test the app announcing itself mid-setup does not start a second flow."""
    installing = hass.loop.create_future()

    async def _install(addon: str) -> None:
        await installing

    install_addon.side_effect = _install
    system_flow = hass.async_create_task(
        hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_SYSTEM})
    )
    await asyncio.sleep(0)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=HASSIO_DATA
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"

    installing.set_result(None)
    result = await system_flow
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize(
    ("source", "data", "host"),
    [
        pytest.param(SOURCE_HASSIO, HASSIO_DATA, APP_HOST, id="hassio"),
        pytest.param(SOURCE_ZEROCONF, ZEROCONF_DATA, HOST, id="zeroconf"),
    ],
)
@pytest.mark.usefixtures("preview_feature_enabled", "app_info")
async def test_discovery_updates_the_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    source: str,
    data: HassioServiceInfo | ZeroconfServiceInfo,
    host: str,
) -> None:
    """Test a rediscovered app with a new port updates and reloads the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="Voice", data={CONF_HOST: host, CONF_PORT: PORT + 1}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert mock_setup_entry.call_count == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=data
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_HOST: host, CONF_PORT: PORT}
    assert mock_setup_entry.call_count == 2


@pytest.mark.usefixtures("preview_feature_enabled", "app_info")
async def test_discovery_reloads_a_retrying_entry(hass: HomeAssistant) -> None:
    """Test the app coming back does not wait out the retry backoff."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Voice",
        data={CONF_HOST: APP_HOST, CONF_PORT: PORT},
        state=ConfigEntryState.SETUP_RETRY,
    )
    entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_HASSIO}, data=HASSIO_DATA
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert reload.call_args == call(entry.entry_id)


@pytest.mark.usefixtures("preview_feature_enabled", "app_info")
async def test_discovery_leaves_an_unchanged_loaded_entry_alone(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the app announcing itself again at the same address is no reason to reload.

    The Supervisor re-sends every discovery at each start, and the client
    keeps its own view of the app fresh.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, title="Voice", data={CONF_HOST: APP_HOST, CONF_PORT: PORT}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert mock_setup_entry.call_count == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=HASSIO_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_setup_entry.call_count == 1


@pytest.mark.usefixtures("preview_feature_enabled", "app_info")
async def test_discovery_leaves_another_host_alone(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an entry pointed at an app of the person's own is not overwritten."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=HASSIO_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {CONF_HOST: HOST, CONF_PORT: PORT}


@pytest.mark.usefixtures("preview_feature_enabled", "app_info")
async def test_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test an app found on the network is confirmed before it is used."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {"name": "Voice", "host": HOST}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Voice"
    assert result["data"] == {CONF_HOST: HOST, CONF_PORT: PORT}


@pytest.mark.usefixtures("labs")
async def test_zeroconf_flow_feature_off(hass: HomeAssistant) -> None:
    """Test an app found on the network is ignored with the feature off."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "preview_feature_disabled"


@pytest.mark.usefixtures("preview_feature_enabled")
async def test_zeroconf_flow_no_port(hass: HomeAssistant) -> None:
    """Test an announcement without a port is useless."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address(HOST),
            ip_addresses=[ip_address(HOST)],
            hostname="voice.local.",
            name="Voice._voice-support._tcp.local.",
            port=None,
            properties={},
            type="_voice-support._tcp.local.",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        pytest.param({"exc": aiohttp.ClientError}, "cannot_connect", id="unreachable"),
        pytest.param({"json": {"name": "Voice"}}, "cannot_connect", id="malformed"),
        pytest.param(
            {"json": {**INFO, "api_version": 2}}, "unsupported_version", id="version"
        ),
    ],
)
@pytest.mark.usefixtures("preview_feature_enabled")
async def test_zeroconf_flow_cannot_use_app(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    reason: str,
) -> None:
    """Test an app found on the network that cannot be used is dropped."""
    aioclient_mock.get(INFO_URL, **response)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("preview_feature_enabled", "app_info")
async def test_zeroconf_confirm_after_an_entry_appeared(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test confirming a stale discovery does not make a second entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DATA
    )
    assert result["type"] is FlowResultType.FORM
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
