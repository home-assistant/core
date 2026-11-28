"""Test the manual and discovery flows for Heiman Local."""

from dataclasses import replace
from ipaddress import IPv4Address, IPv6Address

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.heiman_local.const import DOMAIN
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_USER,
    SOURCE_ZEROCONF,
    ConfigEntry,
    ConfigEntryState,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import WiFiSwitch

_MAC = "a8c1d6010203"


@pytest.fixture
def discovery_info(device: WiFiSwitch) -> ZeroconfServiceInfo:
    """Advertise the local HTTP test switch."""
    address = IPv4Address(str(device.address[CONF_HOST]))
    return ZeroconfServiceInfo(
        ip_address=address,
        ip_addresses=[address],
        port=int(device.address[CONF_PORT]),
        hostname="heiman-sw-0203.local.",
        type="_heiman._tcp.local.",
        name="heiman-sw-0203._heiman._tcp.local.",
        properties={},
    )


async def test_duplicate_switch(
    hass: HomeAssistant, entry: ConfigEntry, device: WiFiSwitch
) -> None:
    """Detect a duplicate switch after receiving the MAC in a different format."""
    device.mac = "a8-c1-d6-01-02-03"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], device.address
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [entry]


@pytest.mark.parametrize(
    ("changes", "overrides", "errors"),
    [
        pytest.param(
            {},
            {CONF_HOST: "http://127.0.0.1"},
            {CONF_HOST: "invalid_host"},
            id="invalid-address",
        ),
        pytest.param(
            {"schema": "different"},
            {},
            {"base": "unsupported_device"},
            id="unsupported-protocol",
        ),
        pytest.param(
            {"online": False}, {}, {"base": "cannot_connect"}, id="unavailable"
        ),
    ],
)
async def test_setup_form_errors(
    hass: HomeAssistant,
    device: WiFiSwitch,
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, bool | str],
    overrides: dict[str, str],
    errors: dict[str, str],
) -> None:
    """Keep the form available after invalid input or an incompatible device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    with monkeypatch.context() as patch:
        for attribute, value in changes.items():
            patch.setattr(device, attribute, value)
        result = await hass.config_entries.flow.async_configure(
            flow_id, {**device.address, **overrides}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == errors
        assert not hass.config_entries.async_entries(DOMAIN)

    result = await hass.config_entries.flow.async_configure(flow_id, device.address)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_flow(
    hass: HomeAssistant,
    device: WiFiSwitch,
    discovery_info: ZeroconfServiceInfo,
) -> None:
    """Confirm a dual-stack device using its advertised IPv4 address."""
    primary_address = IPv6Address("::1")
    discovery_info = replace(
        discovery_info,
        ip_address=primary_address,
        ip_addresses=[primary_address, *discovery_info.ip_addresses],
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {"name": "Heiman WiFi Switch"}
    assert not hass.config_entries.async_entries(DOMAIN)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == _MAC
    assert result["data"] == device.address


@pytest.mark.parametrize(
    ("overrides", "changes", "reason"),
    [
        pytest.param(
            {"ip_address": IPv6Address("::1"), "ip_addresses": [IPv6Address("::1")]},
            {},
            "no_ipv4_address",
            id="ipv6-only",
        ),
        pytest.param({"port": None}, {}, "cannot_connect", id="missing-port"),
        pytest.param({}, {"schema": "other"}, "unsupported_device", id="unsupported"),
        pytest.param({}, {"online": False}, "cannot_connect", id="unavailable"),
    ],
)
async def test_zeroconf_error_recovery(
    hass: HomeAssistant,
    device: WiFiSwitch,
    discovery_info: ZeroconfServiceInfo,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, IPv6Address | list[IPv6Address] | None],
    changes: dict[str, str | bool],
    reason: str,
) -> None:
    """Retry discovery after the switch becomes available for setup."""
    with monkeypatch.context() as patch:
        for attribute, value in changes.items():
            patch.setattr(device, attribute, value)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=replace(discovery_info, **overrides),
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == reason
        assert not hass.config_entries.async_entries(DOMAIN)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == device.address
    assert result["result"].unique_id == _MAC


async def test_zeroconf_updates_address(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: WiFiSwitch,
    discovery_info: ZeroconfServiceInfo,
) -> None:
    """Update the existing entry when its switch advertises a new address."""
    hass.config_entries.async_update_entry(
        entry, data={CONF_HOST: "192.0.2.10", CONF_PORT: 80}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert entry.data == device.address
    assert entry.state is ConfigEntryState.LOADED


async def test_zeroconf_ignored_entry(
    hass: HomeAssistant, discovery_info: ZeroconfServiceInfo
) -> None:
    """Preserve a previously ignored device."""
    entry = MockConfigEntry(domain=DOMAIN, source=SOURCE_IGNORE, unique_id=_MAC)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert not entry.data
