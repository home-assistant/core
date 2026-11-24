"""Test Govee light local config flow."""

import asyncio
from errno import EADDRINUSE, EADDRNOTAVAIL
from ipaddress import IPv4Network
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
from homeassistant.const import CONF_IP_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    DISABLED_NETWORK_ADAPTERS,
    EXPECTED_LISTENING_ADDRESSES,
    answer_scans,
    create_device,
    create_entry,
    scan_reply,
    setup_light,
)

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


async def test_user_flow_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_govee_api: AsyncMock
) -> None:
    """Test the user flow aborts when no lamp answers."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"

    mock_govee_api.start.assert_awaited_once()
    mock_setup_entry.assert_not_called()
    mock_govee_api.cleanup.assert_called_once_with(timeout=CLEANUP_TIMEOUT)


async def test_user_flow_with_devices_set_up(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test set up lamps are not offered, and their controller does the scan."""

    await setup_light(hass, mock_govee_api)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"

    answer_scans(
        mock_govee_api,
        create_device(
            mock_govee_api, ip="192.168.1.101", fingerprint="other", sku="H615B"
        ),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
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

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_started"
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["unique_id"] for flow in flows] == ["other"]


async def test_user_flow_ignores_lamp_that_stopped_answering(
    hass: HomeAssistant, mock_govee_api: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a lamp heard earlier that no longer answers does not count as found."""

    await setup_light(hass, mock_govee_api)
    silent_device = create_device(
        mock_govee_api, ip="192.168.1.101", fingerprint="silent", sku="H615B"
    )
    scan_reply(mock_govee_api, silent_device)
    await hass.async_block_till_done()
    assert silent_device in mock_govee_api.devices

    freezer.tick(60)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_offers_only_answering_lamps(
    hass: HomeAssistant, mock_govee_api: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a dismissed lamp that went silent is not offered with the answering ones."""

    await setup_light(hass, mock_govee_api)
    silent_device = create_device(
        mock_govee_api, ip="192.168.1.101", fingerprint="silent", sku="H615B"
    )
    scan_reply(mock_govee_api, silent_device)
    await hass.async_block_till_done()
    (flow,) = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    hass.config_entries.flow.async_abort(flow["flow_id"])

    freezer.tick(60)
    answer_scans(
        mock_govee_api,
        create_device(
            mock_govee_api, ip="192.168.1.102", fingerprint="other", sku="H615C"
        ),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

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
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            ),
            "user flow",
        )
        await scan_sent.wait()
        # During onboarding the lamp gets its entry without a prompt.
        await hass.async_block_till_done()
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


async def test_user_flow_releases_port_when_cancelled(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test the controller releases the port when the scan is cancelled."""

    started = asyncio.Event()

    async def _start(**kwargs: bool) -> None:
        started.set()

    mock_govee_api.start.side_effect = _start

    with patch(
        "homeassistant.components.govee_light_local.coordinator.DISCOVERY_TIMEOUT", 5
    ):
        task = hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
        )
        await started.wait()
        # Yield once more so the flow parks in the discovery wait before we cancel it.
        await asyncio.sleep(0)
        task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    mock_govee_api.cleanup.assert_called_once_with(timeout=CLEANUP_TIMEOUT)


async def test_user_flow_bind_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test the user flow aborts when the listening port cannot be bound."""

    mock_govee_api.start.side_effect = OSError(EADDRINUSE, "Address already in use")
    answer_scans(mock_govee_api, create_device(mock_govee_api))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"

    assert mock_govee_api.start.call_count == 1
    mock_setup_entry.assert_not_awaited()


async def test_user_flow_no_listening_addresses(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test aborting when no enabled adapter provides an IPv4 address."""

    answer_scans(mock_govee_api, create_device(mock_govee_api))

    with patch(
        "homeassistant.components.network.async_get_adapters",
        return_value=DISABLED_NETWORK_ADAPTERS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"

    mock_govee_api.start.assert_not_awaited()
    mock_setup_entry.assert_not_called()


@pytest.mark.usefixtures("mock_network_adapters")
async def test_user_flow_with_partial_bind(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test discovery succeeds through the adapters that do bind."""

    mock_govee_api.listening_addresses = ["192.168.1.2"]
    mock_govee_api.networks = [IPv4Network("192.168.1.0/24")]
    mock_govee_api.bind_failures = [
        ("10.0.0.7", OSError(EADDRNOTAVAIL, "Cannot assign requested address"))
    ]
    answer_scans(mock_govee_api, create_device(mock_govee_api))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_started"
    mock_govee_api.start.assert_awaited_once_with(require_all=False)
    mock_setup_entry.assert_not_called()


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
