"""Test the ZhongHong config flow."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.climate import (
    ATTR_FAN_MODES,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
)
from homeassistant.components.zhong_hong.config_flow import DISCOVERY_TIMEOUT
from homeassistant.components.zhong_hong.const import (
    CONF_FAN_MODES,
    CONF_GATEWAY_ADDRESS,
    DEFAULT_GATEWAY_ADDRESS,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import ENTITY_ID, HOST, FakeGateway

from tests.common import MockConfigEntry, get_schema_suggested_value

USER_INPUT = {
    CONF_HOST: HOST,
    CONF_PORT: DEFAULT_PORT,
    CONF_GATEWAY_ADDRESS: DEFAULT_GATEWAY_ADDRESS,
}


async def test_user_flow(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
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


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a gateway that cannot be reached is reported, and can be retried.

    Discovery is what reports it, whether there is nothing at the address at
    all or something that does not speak the protocol. Its bound covers
    connecting, so neither costs more than the form can afford to wait.
    """
    mock_gateway.discovery_error = OSError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    # A gateway that refused us must not be left holding an open socket.
    assert mock_gateway.stop_listen_calls == 1

    mock_gateway.discovery_error = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT


async def test_user_flow_no_devices_found(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
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


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
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


@pytest.mark.parametrize(
    ("attribute", "value", "reason"),
    [
        ("discovery_error", OSError, "cannot_connect"),
        ("discovery_result", [], "no_devices_found"),
    ],
    ids=["cannot_connect", "no_devices_found"],
)
async def test_import_flow_with_a_gateway_that_does_not_answer(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_setup_entry: AsyncMock,
    attribute: str,
    value: Any,
    reason: str,
) -> None:
    """Test YAML that no longer describes a working gateway is not imported.

    The configuration can have gone stale since it was written, and a
    configuration entry that never works is worse than being told why. Which
    of the two failed is reported back to the platform that started the
    import, so that it can say so.
    """
    setattr(mock_gateway, attribute, value)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_import_flow_already_configured(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
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


async def test_options_flow(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test choosing which of the fan speeds the air conditioners have."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_FAN_MODES: [FAN_LOW, FAN_MEDIUM, FAN_HIGH]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_FAN_MODES: [FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    }
    # Saving reloads the entry, which is where the entity picks the speeds up.
    assert hass.states.get(ENTITY_ID).attributes[ATTR_FAN_MODES] == [
        FAN_LOW,
        FAN_MEDIUM,
        FAN_HIGH,
    ]


async def test_options_flow_opens_on_the_current_speeds(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
) -> None:
    """Test the form opens on the speeds already saved, not on all five."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_GATEWAY_ADDRESS: DEFAULT_GATEWAY_ADDRESS,
        },
        options={CONF_FAN_MODES: [FAN_LOW]},
    )
    await setup_integration(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert get_schema_suggested_value(result["data_schema"].schema, CONF_FAN_MODES) == [
        FAN_LOW
    ]


async def test_options_flow_needs_a_fan_speed(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the options cannot leave an air conditioner with no speed at all."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_FAN_MODES: []}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_FAN_MODES: "no_fan_modes_selected"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_FAN_MODES: [FAN_LOW]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_FAN_MODES: [FAN_LOW]}
