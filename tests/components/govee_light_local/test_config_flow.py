"""Test Govee light local config flow."""

from errno import EADDRINUSE, EADDRNOTAVAIL
from ipaddress import IPv4Network
from unittest.mock import AsyncMock, call, patch

from govee_local_api import GoveeDevice
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.govee_light_local.const import CONF_HOSTS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    DEFAULT_CAPABILITIES,
    DISABLED_NETWORK_ADAPTERS,
    EXPECTED_LISTENING_ADDRESSES,
    NETWORK_ADAPTERS,
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


async def test_creating_entry_has_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_govee_api: AsyncMock
) -> None:
    """Test the form reports when no devices are found, and recovers."""

    mock_govee_api.devices = []

    with patch(
        "homeassistant.components.govee_light_local.config_flow.DISCOVERY_TIMEOUT",
        0,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "no_devices_found"}

        mock_govee_api.start.assert_awaited_once()
        mock_setup_entry.assert_not_called()

    mock_govee_api.devices = _get_devices(mock_govee_api)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    mock_setup_entry.assert_awaited_once()


@pytest.mark.usefixtures("mock_network_adapters")
async def test_creating_entry_has_with_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test a single controller listens on every enabled adapter address."""

    mock_govee_api.devices = _get_devices(mock_govee_api)

    with patch(
        "homeassistant.components.govee_light_local.config_flow.GoveeController",
        return_value=mock_govee_api,
    ) as mock_controller:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {}
        assert result["options"] == {CONF_HOSTS: []}

        await hass.async_block_till_done()

    assert mock_controller.call_count == 1
    assert (
        mock_controller.call_args.kwargs["listening_addresses"]
        == EXPECTED_LISTENING_ADDRESSES
    )
    mock_govee_api.add_device_to_discovery_queue.assert_not_called()
    mock_govee_api.start.assert_awaited_once()
    mock_setup_entry.assert_awaited_once()


async def test_creating_entry_with_hosts(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test entered addresses are normalized and probed by unicast."""

    mock_govee_api.devices = _get_devices(mock_govee_api)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOSTS: [" 10.0.0.74", "10.0.0.92", "", "10.0.0.74"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_HOSTS: ["10.0.0.74", "10.0.0.92"]}
    await hass.async_block_till_done()

    assert mock_govee_api.add_device_to_discovery_queue.call_args_list == [
        call("10.0.0.74"),
        call("10.0.0.92"),
    ]
    mock_setup_entry.assert_awaited_once()


async def test_creating_entry_invalid_host(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test an invalid address is rejected before any discovery runs."""

    mock_govee_api.devices = _get_devices(mock_govee_api)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOSTS: ["10.0.0.74", "lamp.local"]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOSTS: "invalid_host"}
    mock_govee_api.start.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOSTS: ["10.0.0.74"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_HOSTS: ["10.0.0.74"]}
    await hass.async_block_till_done()
    mock_setup_entry.assert_awaited_once()


async def test_creating_entry_errno(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test the form reports a controller that fails to start."""

    e = OSError()
    e.errno = EADDRINUSE
    mock_govee_api.start.side_effect = e
    mock_govee_api.devices = _get_devices(mock_govee_api)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices_found"}

    await hass.async_block_till_done()

    assert mock_govee_api.start.call_count == 1
    mock_setup_entry.assert_not_awaited()

    mock_govee_api.start.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    mock_setup_entry.assert_awaited_once()


async def test_creating_entry_no_listening_addresses(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test the form reports when no enabled adapter has an IPv4 address."""

    mock_govee_api.devices = _get_devices(mock_govee_api)

    with patch(
        "homeassistant.components.network.async_get_adapters",
        return_value=DISABLED_NETWORK_ADAPTERS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "no_devices_found"}

        await hass.async_block_till_done()

    mock_govee_api.start.assert_not_awaited()
    mock_setup_entry.assert_not_called()

    with patch(
        "homeassistant.components.network.async_get_adapters",
        return_value=NETWORK_ADAPTERS,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
    mock_setup_entry.assert_awaited_once()


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
    mock_govee_api.devices = _get_devices(mock_govee_api)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    mock_govee_api.start.assert_awaited_once_with(require_all=False)
    mock_setup_entry.assert_awaited_once()


async def test_single_instance(hass: HomeAssistant) -> None:
    """Test only one entry can be set up."""

    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test editing the addresses, rejecting an invalid one, reloads the entry."""

    entry = MockConfigEntry(domain=DOMAIN, options={CONF_HOSTS: ["10.0.0.74"]})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert mock_setup_entry.call_count == 1

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_HOSTS: ["10.0.0.300"]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOSTS: "invalid_host"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_HOSTS: ["10.0.0.74", " 10.0.0.92 "]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.options == {CONF_HOSTS: ["10.0.0.74", "10.0.0.92"]}
    assert mock_setup_entry.call_count == 2
