"""Tests for the AirGradient config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from airgradient import (
    AirGradientConnectionError,
    AirGradientParseError,
    ConfigurationControl,
)

from homeassistant.components.airgradient.const import DOMAIN
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

OLD_ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("10.0.0.131"),
    ip_addresses=[ip_address("10.0.0.131")],
    hostname="airgradient_84fce612f5b8.local.",
    name="airgradient_84fce612f5b8._airgradient._tcp.local.",
    port=80,
    type="_airgradient._tcp.local.",
    properties={
        "vendor": "AirGradient",
        "fw_ver": "3.0.8",
        "serialno": "84fce612f5b8",
        "model": "I-9PSL",
    },
)

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("10.0.0.131"),
    ip_addresses=[ip_address("10.0.0.131")],
    hostname="airgradient_84fce612f5b8.local.",
    name="airgradient_84fce612f5b8._airgradient._tcp.local.",
    port=80,
    type="_airgradient._tcp.local.",
    properties={
        "vendor": "AirGradient",
        "fw_ver": "3.1.1",
        "serialno": "84fce612f5b8",
        "model": "I-9PSL",
    },
)


async def test_full_flow(
    hass: HomeAssistant,
    mock_new_airgradient_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "I-9PSL"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
    }
    assert result["result"].unique_id == "84fce612f5b8"
    mock_new_airgradient_client.set_configuration_control.assert_awaited_once_with(
        ConfigurationControl.LOCAL
    )


async def test_flow_with_registered_device(
    hass: HomeAssistant,
    mock_cloud_airgradient_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we don't revert the cloud setting."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "84fce612f5b8"
    mock_cloud_airgradient_client.set_configuration_control.assert_not_called()


async def test_flow_errors(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test flow errors."""
    mock_airgradient_client.get_current_measures.side_effect = (
        AirGradientConnectionError()
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_airgradient_client.get_current_measures.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_old_firmware_version(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test flow with old firmware version."""
    mock_airgradient_client.get_current_measures.side_effect = AirGradientParseError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_version"


async def test_duplicate(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_new_airgradient_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test zeroconf flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "I-9PSL"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
    }
    assert result["result"].unique_id == "84fce612f5b8"
    mock_new_airgradient_client.set_configuration_control.assert_awaited_once_with(
        ConfigurationControl.LOCAL
    )


async def test_zeroconf_flow_cloud_device(
    hass: HomeAssistant,
    mock_cloud_airgradient_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test zeroconf flow doesn't revert the cloud setting."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_cloud_airgradient_client.set_configuration_control.assert_not_called()


async def test_zeroconf_flow_abort_old_firmware(hass: HomeAssistant) -> None:
    """Test zeroconf flow aborts with old firmware."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=OLD_ZEROCONF_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_version"


async def test_zeroconf_flow_abort_duplicate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test zeroconf flow aborts with duplicate."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_works_discovery(
    hass: HomeAssistant,
    mock_new_airgradient_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow can continue after discovery happened."""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert len(hass.config_entries.flow.async_progress(DOMAIN)) == 2
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Verify the discovery flow was aborted
    assert not hass.config_entries.flow.async_progress(DOMAIN)
