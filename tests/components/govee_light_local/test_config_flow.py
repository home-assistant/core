"""Test Govee light local config flow."""

from errno import EADDRINUSE, EADDRNOTAVAIL
from ipaddress import IPv4Network
from unittest.mock import AsyncMock, patch

from govee_local_api import GoveeDevice
import pytest

from homeassistant import config_entries
from homeassistant.components.govee_light_local.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    DEFAULT_CAPABILITIES,
    DISABLED_NETWORK_ADAPTERS,
    EXPECTED_LISTENING_ADDRESSES,
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
    """Test setting up Govee with no devices."""

    mock_govee_api.devices = []

    with patch(
        "homeassistant.components.govee_light_local.config_flow.DISCOVERY_TIMEOUT",
        0,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.ABORT

        await hass.async_block_till_done()

        mock_govee_api.start.assert_awaited_once()
        mock_setup_entry.assert_not_called()


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

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY

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
    mock_govee_api.devices = _get_devices(mock_govee_api)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Confirmation form
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT

    await hass.async_block_till_done()

    assert mock_govee_api.start.call_count == 1
    mock_setup_entry.assert_not_awaited()


async def test_creating_entry_no_listening_addresses(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test aborting when no enabled adapter provides an IPv4 address."""

    mock_govee_api.devices = _get_devices(mock_govee_api)

    with patch(
        "homeassistant.components.network.async_get_adapters",
        return_value=DISABLED_NETWORK_ADAPTERS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.ABORT

        await hass.async_block_till_done()

    mock_govee_api.start.assert_not_awaited()
    mock_setup_entry.assert_not_called()


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

    # Confirmation form
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    mock_govee_api.start.assert_awaited_once_with(require_all=False)
    mock_setup_entry.assert_awaited_once()
