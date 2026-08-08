"""Test the ZhongHong config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.zhong_hong.config_flow import DISCOVERY_TIMEOUT
from homeassistant.components.zhong_hong.const import (
    CONF_GATEWAY_ADDRESS,
    DEFAULT_GATEWAY_ADDRESS,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEVICE_ADDRESS, HOST, FakeGateway

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_HOST: HOST,
    CONF_PORT: DEFAULT_PORT,
    CONF_GATEWAY_ADDRESS: DEFAULT_GATEWAY_ADDRESS,
}


async def test_user_flow(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_socket_probe: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the happy path of the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1
    # Discovery is bounded here. Unbounded it retries for over five minutes,
    # which is what an address that connects but does not answer would cost
    # someone waiting on the form.
    assert mock_gateway.discovery_timeouts == [DISCOVERY_TIMEOUT]


async def test_user_flow_unreachable_host(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_socket_probe: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test an unreachable host is reported and the flow can be retried."""
    mock_socket_probe.side_effect = OSError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    # The gateway is never asked to discover when the host does not answer.
    assert mock_gateway.stop_listen_calls == 0

    mock_socket_probe.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT


async def test_user_flow_discovery_fails(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_socket_probe: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a host that answers but is not a gateway is reported."""
    mock_gateway.discovery_error = OSError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    # The probing gateway must not be left holding an open socket.
    assert mock_gateway.stop_listen_calls == 1

    mock_gateway.discovery_error = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_no_devices_found(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_socket_probe: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a gateway without air conditioners is reported."""
    mock_gateway.discovery_result = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices_found"}

    mock_gateway.discovery_result = [(1, 1)]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_closes_the_probe_before_discovering(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_socket_probe: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the probe socket is gone before discovery opens its own.

    The gateway takes one connection at a time, so a probe still on its way
    out would have discovery refused and report a reachable gateway as
    unreachable.
    """
    writer = mock_socket_probe.return_value[1]
    closed_before_discovery = False

    def _discovery_ac(timeout: float | None = None) -> list[tuple[int, int]]:
        nonlocal closed_before_discovery
        closed_before_discovery = writer.wait_closed.await_count == 1
        return [DEVICE_ADDRESS]

    mock_gateway.discovery_ac = _discovery_ac

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert closed_before_discovery


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_socket_probe: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the same gateway cannot be added twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_second_gateway_on_another_port(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_socket_probe: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the port is part of what tells two gateways apart."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={**USER_INPUT, CONF_PORT: DEFAULT_PORT + 1},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_import_flow(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_socket_probe: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a YAML configuration is imported."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == USER_INPUT


async def test_import_flow_does_not_touch_the_gateway(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_socket_probe: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test an import goes through without the gateway being reachable.

    The gateway takes one connection at a time and may still be holding the
    previous run's, so checking it here would fail for reasons that say
    nothing about the configuration. Setting up the entry retries; this does
    not.
    """
    mock_socket_probe.side_effect = OSError
    mock_gateway.discovery_error = OSError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT
    assert mock_socket_probe.call_count == 0


async def test_import_flow_already_configured(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_socket_probe: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test importing the same gateway twice is a no-op."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
