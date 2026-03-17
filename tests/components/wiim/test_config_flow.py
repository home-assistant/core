"""Tests for the WiiM config flow."""

from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from wiim.models import WiimProbeResult

from homeassistant.components.wiim.config_flow import (
    CannotConnect,
    _async_probe_wiim_host,
)
from homeassistant.components.wiim.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

DISCOVERY_INFO = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.100"),
    ip_addresses=[ip_address("192.168.1.100")],
    hostname="wiim-pro.local.",
    name="WiiM Pro._linkplay._tcp.local.",
    port=49152,
    properties={"uuid": "uuid:test-5678"},
    type="_linkplay._tcp.local.",
)


def _mock_probe_result(
    *,
    host: str = "192.168.1.100",
    udn: str = "uuid:test-1234",
    name: str = "WiiM Pro",
) -> WiimProbeResult:
    """Return a default probe result for the WiiM tests."""
    return WiimProbeResult(
        host=host,
        udn=udn,
        name=name,
        location=f"http://{host}:49152/description.xml",
        model="WiiM Pro",
    )


async def test_user_flow_create_entry(hass: HomeAssistant) -> None:
    """Test the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.wiim.config_flow._async_probe_wiim_host",
        return_value=_mock_probe_result(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.1.100"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "WiiM Pro"
    assert result["data"] == {CONF_HOST: "192.168.1.100"}
    assert result["result"].unique_id == "uuid:test-1234"


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test the user flow handles connection failures."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wiim.config_flow._async_probe_wiim_host",
        side_effect=CannotConnect("cannot_connect"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.1.100"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test the user flow aborts for an already configured device."""
    test_udn = "uuid:test-1234"
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=test_udn)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.wiim.config_flow._async_probe_wiim_host",
        return_value=_mock_probe_result(udn=test_udn),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.1.100"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test the zeroconf discovery flow."""
    device_info = _mock_probe_result(
        host="192.168.1.123",
        udn="uuid:sample-udn",
        name="Mock WiiM",
    )

    with patch(
        "homeassistant.components.wiim.config_flow._async_probe_wiim_host",
        return_value=device_info,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=DISCOVERY_INFO,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {"name": device_info.name}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == device_info.name
    assert result["data"] == {CONF_HOST: device_info.host}
    assert result["result"].unique_id == device_info.udn


async def test_zeroconf_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test the zeroconf flow aborts on connection errors."""
    with patch(
        "homeassistant.components.wiim.config_flow._async_probe_wiim_host",
        side_effect=CannotConnect("cannot_connect"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=DISCOVERY_INFO,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_already_configured(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test the zeroconf flow aborts for an already configured device."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id=DISCOVERY_INFO.properties["uuid"]
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_probe_wiim_host_success(
    mock_hass: HomeAssistant,
    mock_upnp_device: Any,
    mock_wiim_api_endpoint: AsyncMock,
) -> None:
    """Test probing a host returns WiiM device information."""
    expected_result = _mock_probe_result(
        name="Test WiiM Device", udn="uuid:test-udn-1234"
    )

    with patch(
        "homeassistant.components.wiim.config_flow.async_probe_wiim_device",
        return_value=expected_result,
    ):
        result = await _async_probe_wiim_host(mock_hass, "192.168.1.100")

    assert result == expected_result


async def test_async_probe_wiim_host_timeout_error(
    mock_hass: HomeAssistant,
) -> None:
    """Test probing a host handles timeout errors."""
    with (
        patch(
            "homeassistant.components.wiim.config_flow.async_probe_wiim_device",
            side_effect=TimeoutError,
        ),
        pytest.raises(CannotConnect),
    ):
        await _async_probe_wiim_host(mock_hass, "192.168.1.200")


async def test_async_probe_wiim_host_returns_none(
    mock_hass: HomeAssistant,
) -> None:
    """Test probing a host handles empty probe results."""
    with (
        patch(
            "homeassistant.components.wiim.config_flow.async_probe_wiim_device",
            return_value=None,
        ),
        pytest.raises(CannotConnect),
    ):
        await _async_probe_wiim_host(mock_hass, "192.168.1.201")
