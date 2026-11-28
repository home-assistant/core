"""Test Govee light local config flow."""

import asyncio
from errno import EADDRINUSE
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant import config_entries
from homeassistant.components.govee_light_local.const import (
    CLEANUP_TIMEOUT,
    CONF_FINGERPRINT,
    DOMAIN,
)
from homeassistant.components.network import Adapter
from homeassistant.const import CONF_IP_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    DISABLED_NETWORK_ADAPTERS,
    EXPECTED_LISTENING_ADDRESSES,
    NETWORK_ADAPTERS,
    answer_probes,
    answer_scans,
    create_device,
    create_entry,
    create_legacy_entry,
    scan_reply,
    setup_light,
    start_user_flow,
    start_user_manual,
    start_user_scan,
    wait_for_scan,
)

ADDRESS_ERRORS = [
    pytest.param("not an address", None, "invalid_host", id="invalid_address"),
    pytest.param("192.168.1.150", None, "cannot_connect", id="no_reply"),
    pytest.param(
        "192.168.1.150",
        OSError(EADDRINUSE, "Address already in use"),
        "cannot_connect",
        id="bind_error",
    ),
]

DISCOVERY_INFO = {
    CONF_IP_ADDRESS: "192.168.1.100",
    CONF_FINGERPRINT: "asdawdqwdqwd",
    CONF_MODEL: "H615A",
}


@pytest.mark.usefixtures("mock_network_adapters")
async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test the lamps found on every enabled adapter are offered as discovered."""

    answer_scans(
        mock_govee_api,
        create_device(mock_govee_api),
        create_device(
            mock_govee_api, ip="192.168.1.101", fingerprint="other", sku="H615B"
        ),
    )

    with patch(
        "homeassistant.components.govee_light_local.coordinator.GoveeController",
        return_value=mock_govee_api,
    ) as mock_controller:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "scan"}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "scan"
        assert result["progress_action"] == "scan"

        result = await wait_for_scan(hass, result)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_started"

    assert mock_controller.call_count == 1
    assert (
        mock_controller.call_args.kwargs["listening_addresses"]
        == EXPECTED_LISTENING_ADDRESSES
    )
    mock_govee_api.start.assert_awaited_once_with(require_all=False)
    mock_govee_api.cleanup.assert_called_once_with(timeout=CLEANUP_TIMEOUT)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert {flow["context"]["unique_id"] for flow in flows} == {
        "asdawdqwdqwd",
        "other",
    }
    assert {flow["step_id"] for flow in flows} == {"discovery_confirm"}

    result = await hass.config_entries.flow.async_configure(
        next(
            flow["flow_id"] for flow in flows if flow["context"]["unique_id"] == "other"
        ),
        {},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "H615B"
    assert result["data"] == {CONF_IP_ADDRESS: "192.168.1.101"}
    assert result["result"].unique_id == "other"
    mock_setup_entry.assert_awaited_once()


@pytest.mark.parametrize(
    ("adapters", "start_side_effect", "start_calls", "cleanup_calls"),
    [
        pytest.param(NETWORK_ADAPTERS, None, 1, 1, id="no_reply"),
        pytest.param(
            NETWORK_ADAPTERS,
            OSError(EADDRINUSE, "Address already in use"),
            1,
            1,
            id="bind_error",
        ),
        pytest.param(
            DISABLED_NETWORK_ADAPTERS, None, 0, 0, id="no_listening_addresses"
        ),
    ],
)
async def test_user_flow_no_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
    adapters: list[Adapter],
    start_side_effect: OSError | None,
    start_calls: int,
    cleanup_calls: int,
) -> None:
    """Test the user flow aborts when no lamp answers or it cannot listen."""

    mock_govee_api.start.side_effect = start_side_effect

    with patch(
        "homeassistant.components.network.async_get_adapters", return_value=adapters
    ):
        result = await start_user_scan(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"

    assert mock_govee_api.start.await_count == start_calls
    assert mock_govee_api.cleanup.call_count == cleanup_calls
    mock_setup_entry.assert_not_called()


async def test_user_flow_with_devices_set_up(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test set up lamps are not offered, and their controller does the scan."""

    await setup_light(hass, mock_govee_api)

    result = await start_user_scan(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"

    answer_scans(
        mock_govee_api,
        create_device(
            mock_govee_api, ip="192.168.1.101", fingerprint="other", sku="H615B"
        ),
    )
    result = await start_user_scan(hass)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_started"
    mock_govee_api.start.assert_awaited_once()
    mock_govee_api.cleanup.assert_not_called()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["unique_id"] for flow in flows] == ["other"]


async def test_user_flow_offers_dismissed_device_again(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test a lamp whose discovery the user dismissed is offered again."""

    await setup_light(hass, mock_govee_api)
    answer_scans(
        mock_govee_api,
        create_device(
            mock_govee_api, ip="192.168.1.101", fingerprint="other", sku="H615B"
        ),
    )
    mock_govee_api.send_discovery_message()
    await hass.async_block_till_done()
    (flow,) = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    hass.config_entries.flow.async_abort(flow["flow_id"])

    # Scan replies from a lamp that was seen before do not offer it again.
    mock_govee_api.send_discovery_message()
    await hass.async_block_till_done()
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    result = await start_user_scan(hass)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_started"
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["unique_id"] for flow in flows] == ["other"]


async def test_user_flow_offers_only_answering_lamps(
    hass: HomeAssistant, mock_govee_api: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a dismissed lamp that went silent is neither counted nor offered."""

    await setup_light(hass, mock_govee_api)
    silent_device = create_device(
        mock_govee_api, ip="192.168.1.101", fingerprint="silent", sku="H615B"
    )
    scan_reply(mock_govee_api, silent_device)
    await hass.async_block_till_done()
    (flow,) = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    hass.config_entries.flow.async_abort(flow["flow_id"])
    assert silent_device in mock_govee_api.devices

    freezer.tick(60)
    result = await start_user_scan(hass)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    answer_scans(
        mock_govee_api,
        create_device(
            mock_govee_api, ip="192.168.1.102", fingerprint="other", sku="H615C"
        ),
    )
    result = await start_user_scan(hass)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_started"
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["unique_id"] for flow in flows] == ["other"]


async def test_user_flow_counts_lamps_set_up_during_the_scan(
    hass: HomeAssistant, mock_govee_api: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a lamp that is set up while the scan still runs counts as found."""

    answer_scans(mock_govee_api, create_device(mock_govee_api))
    scan_sent = asyncio.Event()
    deliver_replies = mock_govee_api.send_discovery_message.side_effect

    def send_discovery_message() -> None:
        deliver_replies()
        scan_sent.set()

    mock_govee_api.send_discovery_message.side_effect = send_discovery_message
    entry_added = asyncio.Event()

    @callback
    def entry_changed(
        change: config_entries.ConfigEntryChange, entry: config_entries.ConfigEntry
    ) -> None:
        entry_added.set()

    async_dispatcher_connect(
        hass, config_entries.SIGNAL_CONFIG_ENTRY_CHANGED, entry_changed
    )

    with (
        patch(
            "homeassistant.components.govee_light_local.coordinator.DISCOVERY_TIMEOUT",
            5,
        ),
        patch(
            "homeassistant.components.onboarding.async_is_onboarded",
            return_value=False,
        ),
    ):
        task = hass.async_create_background_task(
            start_user_scan(hass),
            "user flow",
        )
        await scan_sent.wait()
        # During onboarding the lamp gets its entry without a prompt.
        await entry_added.wait()
        assert hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, "asdawdqwdqwd"
        )
        assert not task.done()

        freezer.tick(5)
        async_fire_time_changed(hass)
        result = await task
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_started"


@pytest.mark.parametrize(
    ("answering_lamps", "late_lamps", "still_scanning_after", "reason"),
    [
        pytest.param([{}], [], 0, "discovery_started", id="ends_once_replies_settle"),
        pytest.param(
            [{}],
            [{"ip": "192.168.1.101", "fingerprint": "other", "sku": "H615B"}],
            1,
            "discovery_started",
            id="extends_for_a_late_reply",
        ),
        pytest.param([], [], 59, "no_devices_found", id="waits_for_a_first_reply"),
    ],
)
async def test_user_flow_scan_duration(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
    answering_lamps: list[dict[str, str]],
    late_lamps: list[dict[str, str]],
    still_scanning_after: int,
    reason: str,
) -> None:
    """Test the scan ends a second after the last reply, or else at its timeout."""

    for lamp in answering_lamps:
        answer_scans(mock_govee_api, create_device(mock_govee_api, **lamp))
    scan_sent = asyncio.Event()
    deliver_replies = mock_govee_api.send_discovery_message.side_effect

    def send_discovery_message() -> None:
        deliver_replies()
        scan_sent.set()

    mock_govee_api.send_discovery_message.side_effect = send_discovery_message

    with patch(
        "homeassistant.components.govee_light_local.coordinator.DISCOVERY_TIMEOUT", 60
    ):
        result = await start_user_flow(hass, "scan")
        await scan_sent.wait()
        for lamp in late_lamps:
            scan_reply(mock_govee_api, create_device(mock_govee_api, **lamp))

        freezer.tick(still_scanning_after)
        async_fire_time_changed(hass)
        # Enough loop passes for a scan to end; async_block_till_done would
        # wait for the scan itself.
        for _ in range(20):
            await asyncio.sleep(0)
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        freezer.tick(1)
        async_fire_time_changed(hass)
        result = await wait_for_scan(hass, result)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_user_flow_releases_port_when_cancelled(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test the controller releases the port when the flow is closed mid-scan."""

    with patch(
        "homeassistant.components.govee_light_local.coordinator.DISCOVERY_TIMEOUT", 5
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "scan"}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        mock_govee_api.send_discovery_message.assert_called_once()

        hass.config_entries.flow.async_abort(result["flow_id"])
        await hass.async_block_till_done()

    mock_govee_api.cleanup.assert_called_once_with(timeout=CLEANUP_TIMEOUT)


@pytest.mark.parametrize(
    ("loaded_lamps", "cleanup_calls"),
    [
        pytest.param([], 1, id="first_lamp"),
        pytest.param([{}], 0, id="next_to_loaded_lamp"),
    ],
)
async def test_user_flow_by_address(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    loaded_lamps: list[dict[str, str]],
    cleanup_calls: int,
) -> None:
    """Test adding a lamp that only answers a scan sent to its own address."""

    for lamp in loaded_lamps:
        await setup_light(hass, mock_govee_api, **lamp)
    answer_probes(
        mock_govee_api,
        create_device(
            mock_govee_api, ip="192.168.1.101", fingerprint="other", sku="H615B"
        ),
    )

    result = await start_user_manual(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.101"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "H615B"
    assert result["data"] == {CONF_IP_ADDRESS: "192.168.1.101"}
    assert result["result"].unique_id == "other"
    assert result["result"].state is config_entries.ConfigEntryState.LOADED
    # The lamp is not offered as a discovered device as well.
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    # The controller the probe started is released when no lamp is set up yet.
    assert mock_govee_api.cleanup.call_count == cleanup_calls


@pytest.mark.parametrize(("ip_address", "start_side_effect", "error"), ADDRESS_ERRORS)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_by_address_errors(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    ip_address: str,
    start_side_effect: OSError | None,
    error: str,
) -> None:
    """Test the address can be corrected after it could not be used."""

    mock_govee_api.start.side_effect = start_side_effect

    result = await start_user_manual(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: ip_address}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_IP_ADDRESS: error}

    mock_govee_api.start.side_effect = None
    answer_probes(mock_govee_api, create_device(mock_govee_api))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "asdawdqwdqwd"


async def _submit_address_twice(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> list[asyncio.Task[config_entries.ConfigFlowResult]]:
    """Submit the same address in two user flows and wait until both probe it."""
    scan_sent = asyncio.Event()
    mock_govee_api.send_discovery_message.side_effect = scan_sent.set
    tasks = []
    for _ in range(2):
        result = await start_user_manual(hass)
        tasks.append(
            hass.async_create_background_task(
                hass.config_entries.flow.async_configure(
                    result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.100"}
                ),
                "user flow",
            )
        )
    await scan_sent.wait()
    await hass.async_block_till_done()
    return tasks


@pytest.mark.parametrize(
    ("replying_lamps", "elapsed", "result_types", "errors"),
    [
        pytest.param(
            [{}],
            0,
            [FlowResultType.ABORT, FlowResultType.CREATE_ENTRY],
            [None, None],
            id="reply",
        ),
        pytest.param(
            [],
            5,
            [FlowResultType.FORM, FlowResultType.FORM],
            [{CONF_IP_ADDRESS: "cannot_connect"}] * 2,
            id="no_reply",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_by_address_concurrent(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
    replying_lamps: list[dict[str, str]],
    elapsed: int,
    result_types: list[FlowResultType],
    errors: list[dict[str, str] | None],
) -> None:
    """Test two flows probing the same address share the probe and its outcome."""

    with patch(
        "homeassistant.components.govee_light_local.coordinator.DISCOVERY_TIMEOUT", 5
    ):
        tasks = await _submit_address_twice(hass, mock_govee_api)
        assert not any(task.done() for task in tasks)
        for lamp in replying_lamps:
            scan_reply(mock_govee_api, create_device(mock_govee_api, **lamp))
        freezer.tick(elapsed)
        async_fire_time_changed(hass)
        results = await asyncio.gather(*tasks)
        await hass.async_block_till_done()

    assert sorted(result["type"] for result in results) == result_types
    assert [result.get("errors") for result in results] == errors
    mock_govee_api.send_discovery_message.assert_called_once()
    assert not mock_govee_api.discovery_queue


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_by_address_reply_at_timeout(
    hass: HomeAssistant, mock_govee_api: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a reply arriving as the probe times out is still used by every flow."""

    with patch(
        "homeassistant.components.govee_light_local.coordinator.DISCOVERY_TIMEOUT", 5
    ):
        tasks = await _submit_address_twice(hass, mock_govee_api)
        freezer.tick(5)
        async_fire_time_changed(hass)
        # The timeout has fired, but the probing flow has not run again yet.
        scan_reply(mock_govee_api, create_device(mock_govee_api))
        results = await asyncio.gather(*tasks)
        await hass.async_block_till_done()

    assert sorted(result["type"] for result in results) == [
        FlowResultType.ABORT,
        FlowResultType.CREATE_ENTRY,
    ]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_by_address_with_pending_discovery(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test a lamp that is already offered as discovered can be added by address."""

    answer_probes(mock_govee_api, create_device(mock_govee_api))
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data=DISCOVERY_INFO,
    )

    result = await start_user_manual(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "asdawdqwdqwd"
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_by_address_second_reply(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test a lamp answering the probe twice is not offered as discovered as well."""

    device = create_device(mock_govee_api)
    scan_sent = asyncio.Event()
    mock_govee_api.send_discovery_message.side_effect = scan_sent.set

    result = await start_user_manual(hass)
    with patch(
        "homeassistant.components.govee_light_local.coordinator.DISCOVERY_TIMEOUT", 5
    ):
        task = hass.async_create_task(
            hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.100"}
            )
        )
        await scan_sent.wait()
        # A lamp answers the multicast scan and the one sent to its address.
        replies = [scan_reply(mock_govee_api, device) for _ in range(2)]
        result = await task
    await hass.async_block_till_done()

    # Left untracked both times, so the second reply does not offer the lamp.
    assert replies == [False, False]
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "asdawdqwdqwd"
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_user_flow_by_address_of_loaded_lamp(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test probing the address of a set up lamp does not leave it queued."""

    await setup_light(hass, mock_govee_api)

    result = await start_user_manual(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert not mock_govee_api.discovery_queue


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_by_address_already_configured(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test a configured lamp found at another address gets that address."""

    device = create_device(mock_govee_api)
    entry = create_entry(hass, device)
    device.update_ip("192.168.1.150")
    answer_probes(mock_govee_api, device)

    result = await start_user_manual(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.150"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_IP_ADDRESS: "192.168.1.150"}


async def test_reconfigure(hass: HomeAssistant, mock_govee_api: AsyncMock) -> None:
    """Test changing the address of a lamp."""

    entry, device = await setup_light(hass, mock_govee_api)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    device.update_ip("192.168.1.150")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.150"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_IP_ADDRESS: "192.168.1.150"}
    assert entry.state is config_entries.ConfigEntryState.LOADED


@pytest.mark.parametrize(("ip_address", "start_side_effect", "error"), ADDRESS_ERRORS)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    ip_address: str,
    start_side_effect: OSError | None,
    error: str,
) -> None:
    """Test the address can be corrected after it could not be used."""

    device = create_device(mock_govee_api)
    # Not set up, so the flow is the one to start the controller.
    entry = create_entry(hass, device)
    mock_govee_api.start.side_effect = start_side_effect

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: ip_address}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_IP_ADDRESS: error}

    mock_govee_api.start.side_effect = None
    device.update_ip("192.168.1.150")
    answer_probes(mock_govee_api, device)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.150"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_IP_ADDRESS: "192.168.1.150"}
    assert entry.state is config_entries.ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "disabled_by",
    [
        pytest.param(None, id="enabled"),
        pytest.param(config_entries.ConfigEntryDisabler.USER, id="disabled"),
    ],
)
async def test_reconfigure_legacy_entry(
    hass: HomeAssistant, disabled_by: config_entries.ConfigEntryDisabler | None
) -> None:
    """Test the entry for every lamp has no address to change."""

    entry = create_legacy_entry(hass)
    await hass.config_entries.async_set_disabled_by(entry.entry_id, disabled_by)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_split"


@pytest.mark.parametrize(
    "pending_discoveries",
    [
        pytest.param([], id="unknown_lamp"),
        pytest.param(
            [
                {
                    CONF_IP_ADDRESS: "192.168.1.101",
                    CONF_FINGERPRINT: "other",
                    CONF_MODEL: "H615B",
                }
            ],
            id="discovered_lamp",
        ),
    ],
)
async def test_reconfigure_wrong_device(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    pending_discoveries: list[dict[str, str]],
) -> None:
    """Test the address of another lamp is not accepted."""

    entry, _ = await setup_light(hass, mock_govee_api)
    other_device = create_device(
        mock_govee_api, ip="192.168.1.101", fingerprint="other", sku="H615B"
    )
    answer_probes(mock_govee_api, other_device)
    for discovery_info in pending_discoveries:
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=discovery_info,
        )

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: "192.168.1.101"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert entry.data == {CONF_IP_ADDRESS: "192.168.1.100"}

    # The other lamp was only identified, so it is still offered once it is heard.
    assert other_device not in mock_govee_api.devices
    assert not mock_govee_api.discovery_queue
    scan_reply(mock_govee_api, other_device)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["unique_id"] for flow in flows] == ["other"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_integration_discovery(hass: HomeAssistant) -> None:
    """Test a discovered lamp is set up after the user confirms it."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data=DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {
        "model": "H615A",
        "ip": "192.168.1.100",
    }

    # The same lamp answering again does not start a second flow.
    duplicate = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={**DISCOVERY_INFO, CONF_IP_ADDRESS: "192.168.1.150"},
    )
    assert duplicate["type"] is FlowResultType.ABORT
    assert duplicate["reason"] == "already_in_progress"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "H615A"
    assert result["data"] == {CONF_IP_ADDRESS: "192.168.1.100"}
    assert result["result"].unique_id == "asdawdqwdqwd"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_integration_discovery_configured_before_confirmation(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test confirming does not replace an entry the lamp got in the meantime."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={**DISCOVERY_INFO, CONF_IP_ADDRESS: "192.168.1.150"},
    )
    assert result["type"] is FlowResultType.FORM

    entry = create_entry(hass, create_device(mock_govee_api))

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert entry.data == {CONF_IP_ADDRESS: "192.168.1.150"}


@pytest.mark.parametrize(
    ("source", "onboarded"),
    [
        pytest.param(
            config_entries.SOURCE_INTEGRATION_DISCOVERY, False, id="onboarding"
        ),
        pytest.param(config_entries.SOURCE_IMPORT, True, id="import"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_without_confirmation(
    hass: HomeAssistant, source: str, onboarded: bool
) -> None:
    """Test a lamp is set up without a prompt during onboarding or migration."""

    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=onboarded,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=DISCOVERY_INFO
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "H615A"
    assert result["data"] == {CONF_IP_ADDRESS: "192.168.1.100"}
    assert result["result"].unique_id == "asdawdqwdqwd"


@pytest.mark.parametrize(
    ("source", "ip_address", "stored_ip_address"),
    [
        pytest.param(
            config_entries.SOURCE_INTEGRATION_DISCOVERY,
            "192.168.1.150",
            "192.168.1.150",
            id="discovery",
        ),
        pytest.param(
            config_entries.SOURCE_IMPORT, "192.168.1.150", "192.168.1.150", id="import"
        ),
        pytest.param(
            config_entries.SOURCE_IMPORT,
            None,
            "192.168.1.100",
            id="import_without_address",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_already_configured(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    source: str,
    ip_address: str | None,
    stored_ip_address: str,
) -> None:
    """Test a configured lamp answering from a new address updates its entry."""

    entry: MockConfigEntry = create_entry(hass, create_device(mock_govee_api))

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source},
        data={**DISCOVERY_INFO, CONF_IP_ADDRESS: ip_address},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_IP_ADDRESS: stored_ip_address}
