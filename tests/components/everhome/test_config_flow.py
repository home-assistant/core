"""Tests for the everHome/EcoTracker integration."""

from dataclasses import replace
from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.everhome.const import CONF_FAST_POLLING, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info import zeroconf

from tests.common import MockConfigEntry, get_schema_suggested_value

IP_ADDRESS = "192.168.178.104"
NEW_IP_ADDRESS = "192.168.178.105"
DEVICE_ID = "abcdef123456"

ZEROCONF_DISCOVERY = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address(IP_ADDRESS),
    ip_addresses=[ip_address(IP_ADDRESS)],
    hostname="ecotracker-E80690E0F2B4.local.",
    name="ecotracker-E80690E0F2B4",
    port=80,
    type="_everhome._tcp.",
    properties={"productid": 1137, "serial": "abcdef123456", "ip": IP_ADDRESS},
)


async def test_user_flow(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
) -> None:
    """Test full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: IP_ADDRESS},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "EcoTracker " + DEVICE_ID
    assert result["data"] == {CONF_HOST: IP_ADDRESS}
    assert result["options"] == {CONF_FAST_POLLING: False}
    assert result["result"].unique_id == DEVICE_ID


async def test_user_flow_error(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
) -> None:
    """Test full user configuration flow with connection error."""
    mock_everhome_client.async_update.return_value = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: IP_ADDRESS},
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"

    mock_everhome_client.async_update.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: IP_ADDRESS},
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "EcoTracker " + DEVICE_ID
    assert result["data"] == {CONF_HOST: IP_ADDRESS}
    assert result["result"].unique_id == DEVICE_ID


@pytest.mark.usefixtures("mock_everhome_client")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the user flow aborts when the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: IP_ADDRESS},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
) -> None:
    """Test zeroconf flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "EcoTracker " + DEVICE_ID
    assert result["data"] == {CONF_HOST: IP_ADDRESS}
    assert result["options"] == {CONF_FAST_POLLING: False}
    assert result["result"].unique_id == DEVICE_ID


async def test_zeroconf_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test rediscovering a configured device updates its host and aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=replace(
            ZEROCONF_DISCOVERY,
            ip_address=ip_address(NEW_IP_ADDRESS),
            ip_addresses=[ip_address(NEW_IP_ADDRESS)],
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {CONF_HOST: NEW_IP_ADDRESS}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize(
    ("source", "discovery_info", "step_id", "user_input"),
    [
        pytest.param(SOURCE_USER, None, "user", {CONF_HOST: IP_ADDRESS}, id="user"),
        pytest.param(
            SOURCE_ZEROCONF, ZEROCONF_DISCOVERY, "zeroconf_confirm", {}, id="zeroconf"
        ),
    ],
)
@pytest.mark.usefixtures("mock_everhome_client")
async def test_setup_fast_polling_enable(
    hass: HomeAssistant,
    source: str,
    discovery_info: zeroconf.ZeroconfServiceInfo | None,
    step_id: str,
    user_input: dict[str, Any],
) -> None:
    """Test enabling fast polling during setup asks for confirmation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=discovery_info
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**user_input, CONF_FAST_POLLING: True}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "fast_polling"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "fast_polling_enable"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: IP_ADDRESS}
    assert result["options"] == {CONF_FAST_POLLING: True}
    assert result["result"].unique_id == DEVICE_ID


@pytest.mark.parametrize(
    ("source", "discovery_info", "step_id", "user_input", "suggested_host"),
    [
        pytest.param(
            SOURCE_USER,
            None,
            "user",
            {CONF_HOST: IP_ADDRESS},
            IP_ADDRESS,
            id="user",
        ),
        pytest.param(
            SOURCE_ZEROCONF,
            ZEROCONF_DISCOVERY,
            "zeroconf_confirm",
            {},
            None,
            id="zeroconf",
        ),
    ],
)
@pytest.mark.usefixtures("mock_everhome_client")
async def test_setup_fast_polling_cancel(
    hass: HomeAssistant,
    source: str,
    discovery_info: zeroconf.ZeroconfServiceInfo | None,
    step_id: str,
    user_input: dict[str, Any],
    suggested_host: str | None,
) -> None:
    """Test cancelling fast polling returns to the setup form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=discovery_info
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**user_input, CONF_FAST_POLLING: True}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "fast_polling_cancel"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_HOST)
        == suggested_host
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_FAST_POLLING: False}


async def test_zeroconf_flow_error(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
) -> None:
    """Test zeroconf flow with connection error."""
    mock_everhome_client.async_update.return_value = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_no_serial(
    hass: HomeAssistant,
) -> None:
    """Test zeroconf flow aborts when serial is missing from TXT record."""
    discovery_without_serial = zeroconf.ZeroconfServiceInfo(
        ip_address=ip_address(IP_ADDRESS),
        ip_addresses=[ip_address(IP_ADDRESS)],
        hostname="ecotracker-E80690E0F2B4.local.",
        name="ecotracker-E80690E0F2B4",
        port=80,
        type="_everhome._tcp.",
        properties={"productid": 1137, "ip": IP_ADDRESS},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_without_serial,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_serial"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: NEW_IP_ADDRESS},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_HOST: NEW_IP_ADDRESS}


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow recovers from a connection error."""
    mock_config_entry.add_to_hass(hass)
    mock_everhome_client.async_update.return_value = False

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: NEW_IP_ADDRESS},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_everhome_client.async_update.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: NEW_IP_ADDRESS},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_HOST: NEW_IP_ADDRESS}


async def test_reconfigure_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow aborts when pointed at a different device."""
    mock_config_entry.add_to_hass(hass)
    mock_everhome_client.get_data.return_value.serial = "fedcba654321"

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: NEW_IP_ADDRESS},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == {CONF_HOST: IP_ADDRESS}


async def test_options_flow_fast_polling_enable(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test enabling fast polling in the options flow asks for confirmation."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_FAST_POLLING: True}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "fast_polling"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "fast_polling_enable"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_FAST_POLLING: True}
    # The entry is reloaded so the new interval takes effect.
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_fast_polling_cancel(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cancelling fast polling returns to the options form."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_FAST_POLLING: True}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "fast_polling_cancel"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert mock_config_entry.options == {}


@pytest.mark.parametrize(
    ("current", "new"),
    [
        pytest.param(True, False, id="disable"),
        pytest.param(True, True, id="keep_enabled"),
        pytest.param(False, False, id="keep_disabled"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_no_confirmation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    current: bool,
    new: bool,
) -> None:
    """Test the options flow only asks for confirmation when enabling."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_FAST_POLLING: current}
    )

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_FAST_POLLING)
        is current
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_FAST_POLLING: new}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_FAST_POLLING: new}
