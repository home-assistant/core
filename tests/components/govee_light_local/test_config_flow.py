"""Test Govee light local config flow."""

import asyncio
from errno import EADDRINUSE, EADDRNOTAVAIL
from ipaddress import IPv4Network
from unittest.mock import AsyncMock, patch

from govee_local_api import GoveeDevice
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.govee_light_local.const import (
    CLEANUP_TIMEOUT,
    CONF_DEVICE_IP,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    DEFAULT_CAPABILITIES,
    DISABLED_NETWORK_ADAPTERS,
    EXPECTED_LISTENING_ADDRESSES,
    set_mocked_devices,
)


def _get_devices(mock_govee_api: AsyncMock) -> list[GoveeDevice]:
    return [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd1",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]


async def test_abort_on_multiple_flows(hass: HomeAssistant) -> None:
    """Test a second user flow is aborted while the first is still in progress."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"


async def test_integration_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_creating_entry_has_no_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test setting up Govee with no devices."""

    set_mocked_devices(mock_govee_api, [])

    with patch(
        "homeassistant.components.govee_light_local.config_flow.DISCOVERY_TIMEOUT",
        0,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        # Confirmation form
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.ABORT

        await hass.async_block_till_done()
        mock_govee_api.start.assert_awaited_once()
        mock_setup_entry.assert_not_called()
        mock_govee_api.cleanup.assert_called_once_with(timeout=CLEANUP_TIMEOUT)


async def test_discovery_releases_port_when_cancelled(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test the discovery controller releases the port when the flow is cancelled."""

    set_mocked_devices(mock_govee_api, [])
    started = asyncio.Event()

    async def _start(**kwargs: bool) -> None:
        started.set()

    mock_govee_api.start.side_effect = _start

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    task = hass.async_create_task(
        hass.config_entries.flow.async_configure(result["flow_id"], {})
    )
    await started.wait()
    # Yield once more so the flow parks in the discovery wait before we cancel it.
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    mock_govee_api.cleanup.assert_called_once_with(timeout=CLEANUP_TIMEOUT)


@pytest.mark.usefixtures("mock_network_adapters")
async def test_creating_entry_with_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test a single controller listens on every enabled adapter address."""

    set_mocked_devices(mock_govee_api, _get_devices(mock_govee_api))

    with patch(
        "homeassistant.components.govee_light_local.config_flow.GoveeController",
        return_value=mock_govee_api,
    ) as mock_controller:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        # Confirmation form
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == DOMAIN
        # The options flow owns this setting, so it must be seeded into options
        # rather than data, which an options flow can never write.
        assert result["data"] == {}
        assert result["options"] == {}

        await hass.async_block_till_done()

    assert mock_controller.call_count == 1
    assert (
        mock_controller.call_args.kwargs["listening_addresses"]
        == EXPECTED_LISTENING_ADDRESSES
    )
    mock_govee_api.start.assert_awaited_once()
    mock_setup_entry.assert_awaited_once()


async def test_creating_entry_errno(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test setting up Govee with devices."""

    e = OSError()
    e.errno = EADDRINUSE
    mock_govee_api.start.side_effect = e
    set_mocked_devices(mock_govee_api, _get_devices(mock_govee_api))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    # Confirmation form
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT

    await hass.async_block_till_done()

    assert mock_govee_api.start.call_count == 1
    mock_setup_entry.assert_not_awaited()


async def test_discovery_without_listening_addresses(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test discovery aborts when no enabled adapter provides an IPv4 address."""
    with patch(
        "homeassistant.components.network.async_get_adapters",
        return_value=DISABLED_NETWORK_ADAPTERS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    mock_govee_api.start.assert_not_awaited()


@pytest.mark.usefixtures("mock_network_adapters")
async def test_creating_entry_with_partial_bind(
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
    set_mocked_devices(mock_govee_api, _get_devices(mock_govee_api))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    # Confirmation form
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOMAIN

    await hass.async_block_till_done()

    mock_govee_api.start.assert_awaited_once_with(require_all=False)
    mock_setup_entry.assert_awaited_once()


async def test_add_device_subentry(hass: HomeAssistant) -> None:
    """Test adding a manual device through the device subentry flow."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.100"
    assert result["unique_id"] == "192.168.1.100"
    assert result["data"] == {CONF_DEVICE_IP: "192.168.1.100"}

    subentry = next(iter(config_entry.subentries.values()))
    assert subentry.subentry_type == SUBENTRY_TYPE_DEVICE
    assert subentry.data == {CONF_DEVICE_IP: "192.168.1.100"}
    assert subentry.unique_id == "192.168.1.100"


async def test_add_device_subentry_invalid_ip(hass: HomeAssistant) -> None:
    """Test the device subentry flow rejects a malformed IP address."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: "foo"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_ip"}
    assert result["description_placeholders"] == {"ip": "foo"}

    # The flow stays open, so a corrected address still completes.
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_DEVICE_IP: "192.168.1.100"}


async def test_add_device_subentry_duplicate(hass: HomeAssistant) -> None:
    """Test the device subentry flow rejects an already configured IP."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=[
            ConfigSubentryData(
                data={CONF_DEVICE_IP: "192.168.1.100"},
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="192.168.1.100",
                unique_id="192.168.1.100",
            )
        ],
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "already_configured"}
    assert len(config_entry.subentries) == 1

    # The flow stays open, so a different address still completes.
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: "192.168.1.101"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(config_entry.subentries) == 2


async def test_reconfigure_device_subentry(hass: HomeAssistant) -> None:
    """Test changing a manual device's IP address in place."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=[
            ConfigSubentryData(
                data={CONF_DEVICE_IP: "192.168.1.100"},
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="192.168.1.100",
                unique_id="192.168.1.100",
            )
        ],
    )
    config_entry.add_to_hass(hass)
    subentry_id = next(iter(config_entry.subentries))

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "subentry_id": subentry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: "192.168.1.102"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert len(config_entry.subentries) == 1
    subentry = config_entry.subentries[subentry_id]
    assert subentry.data == {CONF_DEVICE_IP: "192.168.1.102"}
    assert subentry.title == "192.168.1.102"
    assert subentry.unique_id == "192.168.1.102"


async def test_reconfigure_device_subentry_invalid_ip(hass: HomeAssistant) -> None:
    """Test the reconfigure step rejects a malformed IP address."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=[
            ConfigSubentryData(
                data={CONF_DEVICE_IP: "192.168.1.100"},
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="192.168.1.100",
                unique_id="192.168.1.100",
            )
        ],
    )
    config_entry.add_to_hass(hass)
    subentry_id = next(iter(config_entry.subentries))

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "subentry_id": subentry_id,
        },
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: "foo"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_ip"}
    assert result["description_placeholders"] == {"ip": "foo"}

    # The flow stays open, so a corrected address still completes.
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: "192.168.1.102"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.subentries[subentry_id].unique_id == "192.168.1.102"


async def test_reconfigure_device_subentry_duplicate(hass: HomeAssistant) -> None:
    """Test the reconfigure step rejects another subentry's IP but allows its own."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=[
            ConfigSubentryData(
                data={CONF_DEVICE_IP: "192.168.1.100"},
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="192.168.1.100",
                unique_id="192.168.1.100",
            ),
            ConfigSubentryData(
                data={CONF_DEVICE_IP: "192.168.1.101"},
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="192.168.1.101",
                unique_id="192.168.1.101",
            ),
        ],
    )
    config_entry.add_to_hass(hass)
    subentry_id = next(
        subentry_id
        for subentry_id, subentry in config_entry.subentries.items()
        if subentry.unique_id == "192.168.1.100"
    )

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "subentry_id": subentry_id,
        },
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: "192.168.1.101"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "already_configured"}

    # The subentry's own IP is not a conflict with itself.
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_IP: "192.168.1.100"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
