"""Test Zeroconf component setup process."""

from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
from zeroconf import (
    BadTypeInNameException,
    InterfaceChoice,
    IPVersion,
    ServiceStateChange,
)
from zeroconf.asyncio import AsyncServiceInfo

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.generated import zeroconf as zc_gen
from homeassistant.helpers.discovery_flow import DiscoveryKey
from homeassistant.setup import ATTR_COMPONENT, async_setup_component

from tests.common import MockConfigEntry, MockModule, mock_integration

NON_UTF8_VALUE = b"ABCDEF\x8a"
NON_ASCII_KEY = b"non-ascii-key\x8a"
PROPERTIES = {
    b"macaddress": b"ABCDEF012345",
    b"non-utf8-value": NON_UTF8_VALUE,
    NON_ASCII_KEY: None,
}

HOMEKIT_STATUS_UNPAIRED = b"1"
HOMEKIT_STATUS_PAIRED = b"0"


def service_update_mock(zeroconf, services, handlers, *, limit_service=None):
    """Call service update handler."""
    for service in services:
        if limit_service is not None and service != limit_service:
            continue
        handlers[0](zeroconf, service, f"_name.{service}", ServiceStateChange.Added)


def get_service_info_mock(
    service_type: str, name: str, *args: Any, **kwargs: Any
) -> AsyncServiceInfo:
    """Return service info for get_service_info."""
    return AsyncServiceInfo(
        service_type,
        name,
        addresses=[b"\n\x00\x00\x14"],
        port=80,
        weight=0,
        priority=0,
        server="name.local.",
        properties=PROPERTIES,
    )


def get_service_info_mock_without_an_address(
    service_type: str, name: str
) -> AsyncServiceInfo:
    """Return service info for get_service_info without any addresses."""
    return AsyncServiceInfo(
        service_type,
        name,
        addresses=[],
        port=80,
        weight=0,
        priority=0,
        server="name.local.",
        properties=PROPERTIES,
    )


def get_homekit_info_mock(model, pairing_status):
    """Return homekit info for get_service_info for an homekit device."""

    def mock_homekit_info(service_type, name):
        return AsyncServiceInfo(
            service_type,
            name,
            addresses=[b"\n\x00\x00\x14"],
            port=80,
            weight=0,
            priority=0,
            server="name.local.",
            properties={b"md": model.encode(), b"sf": pairing_status},
        )

    return mock_homekit_info


def get_zeroconf_info_mock(macaddress):
    """Return info for get_service_info for an zeroconf device."""

    def mock_zc_info(service_type, name):
        return AsyncServiceInfo(
            service_type,
            name,
            addresses=[b"\n\x00\x00\x14"],
            port=80,
            weight=0,
            priority=0,
            server="name.local.",
            properties={b"macaddress": macaddress.encode()},
        )

    return mock_zc_info


def get_zeroconf_info_mock_manufacturer(manufacturer):
    """Return info for get_service_info for an zeroconf device."""

    def mock_zc_info(service_type, name):
        return AsyncServiceInfo(
            service_type,
            name,
            addresses=[b"\n\x00\x00\x14"],
            port=80,
            weight=0,
            priority=0,
            server="name.local.",
            properties={b"manufacturer": manufacturer.encode()},
        )

    return mock_zc_info


def get_zeroconf_info_mock_model(model):
    """Return info for get_service_info for an zeroconf device."""

    def mock_zc_info(service_type, name):
        return AsyncServiceInfo(
            service_type,
            name,
            addresses=[b"\n\x00\x00\x14"],
            port=80,
            weight=0,
            priority=0,
            server="name.local.",
            properties={b"model": model.encode()},
        )

    return mock_zc_info


async def test_setup(hass: HomeAssistant, mock_async_zeroconf: MagicMock) -> None:
    """Test configured options for a device are loaded via config entry."""
    mock_zc = {
        "_http._tcp.local.": [
            {
                "domain": "shelly",
                "name": "shelly*",
                "properties": {"macaddress": "ffaadd*"},
            }
        ],
        "_Volumio._tcp.local.": [{"domain": "volumio"}],
    }
    with (
        patch.dict(
            zc_gen.ZEROCONF,
            mock_zc,
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf, "AsyncServiceBrowser", side_effect=service_update_mock
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_service_info_mock,
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    expected_flow_calls = 0
    for matching_components in mock_zc.values():
        domains = set()
        for component in matching_components:
            if len(component) == 1:
                domains.add(component["domain"])
        expected_flow_calls += len(domains)
    assert len(mock_config_flow.mock_calls) == expected_flow_calls

    # Test instance is set.
    assert "zeroconf" in hass.data
    assert await zeroconf.async_get_async_instance(hass) is mock_async_zeroconf


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_setup_with_overly_long_url_and_name(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we still setup with long urls and names."""
    with (
        patch.object(hass.config_entries.flow, "async_init"),
        patch.object(zeroconf, "AsyncServiceBrowser", side_effect=service_update_mock),
        patch(
            "homeassistant.components.zeroconf.get_url",
            return_value=(
                "https://this.url.is.way.too.long/very/deep/path/that/will/make/us/go/over"
                "/the/maximum/string/length/and/would/cause/zeroconf/to/fail/to/startup"
                "/because/the/key/and/value/can/only/be/255/bytes/and/this/string/is/a"
                "/bit/longer/than/the/maximum/length/that/we/allow/for/a/value"
            ),
        ),
        patch.object(
            hass.config,
            "location_name",
            (
                "\u00dcBER \u00dcber German Umlaut long string long string long string long"
                " string long string long string long string long string long string long"
                " string long string long string long string long string long string long"
                " string long string long string long string long string long string long"
                " string long string long string long string long string long string long"
                " string long string long string long string long string long string long"
                " string long string long string long string long string long string long"
                " string long string long string long string long string long string long"
                " string long string long string long string long string"
            ),
        ),
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo.async_request",
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    assert "https://this.url.is.way.too.long" in caplog.text
    assert "German Umlaut" in caplog.text


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_setup_with_defaults(
    hass: HomeAssistant, mock_zeroconf: MagicMock
) -> None:
    """Test default interface config."""
    with (
        patch.object(hass.config_entries.flow, "async_init"),
        patch.object(zeroconf, "AsyncServiceBrowser", side_effect=service_update_mock),
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_service_info_mock,
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    mock_zeroconf.assert_called_with(
        interfaces=InterfaceChoice.Default, ip_version=IPVersion.V4Only
    )


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_zeroconf_match_macaddress(hass: HomeAssistant) -> None:
    """Test configured options for a device are loaded via config entry."""

    def http_only_service_update_mock(zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_http._tcp.local.",
            "Shelly108._http._tcp.local.",
            ServiceStateChange.Added,
        )

    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {
                "_http._tcp.local.": [
                    {
                        "domain": "shelly",
                        "name": "shelly*",
                        "properties": {"macaddress": "ffaadd*"},
                    }
                ]
            },
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf, "AsyncServiceBrowser", side_effect=http_only_service_update_mock
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_zeroconf_info_mock("FFAADDCC11DD"),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "shelly"
    assert mock_config_flow.mock_calls[0][2]["context"] == {
        "discovery_key": DiscoveryKey(
            domain="zeroconf",
            key=("_http._tcp.local.", "Shelly108._http._tcp.local."),
            version=1,
        ),
        "source": "zeroconf",
    }


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_zeroconf_match_manufacturer(hass: HomeAssistant) -> None:
    """Test configured options for a device are loaded via config entry."""

    def http_only_service_update_mock(zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_airplay._tcp.local.",
            "s1000._airplay._tcp.local.",
            ServiceStateChange.Added,
        )

    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {
                "_airplay._tcp.local.": [
                    {"domain": "samsungtv", "properties": {"manufacturer": "samsung*"}}
                ]
            },
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf, "AsyncServiceBrowser", side_effect=http_only_service_update_mock
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_zeroconf_info_mock_manufacturer("Samsung Electronics"),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "samsungtv"


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_zeroconf_match_model(hass: HomeAssistant) -> None:
    """Test matching a specific model in zeroconf."""

    def http_only_service_update_mock(zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_airplay._tcp.local.",
            "s1000._airplay._tcp.local.",
            ServiceStateChange.Added,
        )

    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {
                "_airplay._tcp.local.": [
                    {"domain": "appletv", "properties": {"model": "appletv*"}}
                ]
            },
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf, "AsyncServiceBrowser", side_effect=http_only_service_update_mock
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_zeroconf_info_mock_model("appletv"),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "appletv"


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_zeroconf_match_manufacturer_not_present(hass: HomeAssistant) -> None:
    """Test matchers reject when a property is missing."""

    def http_only_service_update_mock(zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_airplay._tcp.local.",
            "s1000._airplay._tcp.local.",
            ServiceStateChange.Added,
        )

    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {
                "_airplay._tcp.local.": [
                    {"domain": "samsungtv", "properties": {"manufacturer": "samsung*"}}
                ]
            },
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf, "AsyncServiceBrowser", side_effect=http_only_service_update_mock
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_zeroconf_info_mock("aabbccddeeff"),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 0


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_zeroconf_no_match(hass: HomeAssistant) -> None:
    """Test configured options for a device are loaded via config entry."""

    def http_only_service_update_mock(zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_http._tcp.local.",
            "somethingelse._http._tcp.local.",
            ServiceStateChange.Added,
        )

    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {"_http._tcp.local.": [{"domain": "shelly", "name": "shelly*"}]},
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf, "AsyncServiceBrowser", side_effect=http_only_service_update_mock
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_zeroconf_info_mock("FFAADDCC11DD"),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 0


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_zeroconf_no_match_manufacturer(hass: HomeAssistant) -> None:
    """Test configured options for a device are loaded via config entry."""

    def http_only_service_update_mock(zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_airplay._tcp.local.",
            "s1000._airplay._tcp.local.",
            ServiceStateChange.Added,
        )

    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {
                "_airplay._tcp.local.": [
                    {"domain": "samsungtv", "properties": {"manufacturer": "samsung*"}}
                ]
            },
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf, "AsyncServiceBrowser", side_effect=http_only_service_update_mock
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_zeroconf_info_mock_manufacturer("Not Samsung Electronics"),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 0


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_homekit_match_partial_space(hass: HomeAssistant) -> None:
    """Test configured options for a device are loaded via config entry."""
    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {"_hap._tcp.local.": [{"domain": "homekit_controller"}]},
            clear=True,
        ),
        patch.dict(
            zc_gen.HOMEKIT,
            {"LIFX": {"domain": "lifx", "always_discover": True}},
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf,
            "AsyncServiceBrowser",
            side_effect=lambda *args, **kwargs: service_update_mock(
                *args, **kwargs, limit_service="_hap._tcp.local."
            ),
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_homekit_info_mock("LIFX bulb", HOMEKIT_STATUS_UNPAIRED),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    # One for HKC, and one for LIFX since lifx is local polling
    assert len(mock_config_flow.mock_calls) == 2
    assert mock_config_flow.mock_calls[0][1][0] == "lifx"
    assert mock_config_flow.mock_calls[1][2]["context"] == {
        "source": "zeroconf",
        "alternative_domain": "lifx",
        "discovery_key": DiscoveryKey(
            domain="zeroconf",
            key=("_hap._tcp.local.", "_name._hap._tcp.local."),
            version=1,
        ),
    }


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_device_with_invalid_name(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we ignore devices with an invalid name."""
    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {"_hap._tcp.local.": [{"domain": "homekit_controller"}]},
            clear=True,
        ),
        patch.dict(
            zc_gen.HOMEKIT,
            {"LIFX": {"domain": "lifx", "always_discover": True}},
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf,
            "AsyncServiceBrowser",
            side_effect=lambda *args, **kwargs: service_update_mock(
                *args, **kwargs, limit_service="_hap._tcp.local."
            ),
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=BadTypeInNameException,
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 0
    assert "Bad name in zeroconf record" in caplog.text


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_homekit_match_partial_dash(hass: HomeAssistant) -> None:
    """Test configured options for a device are loaded via config entry."""
    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {"_hap._udp.local.": [{"domain": "homekit_controller"}]},
            clear=True,
        ),
        patch.dict(
            zc_gen.HOMEKIT,
            {"Smart Bridge": {"domain": "lutron_caseta", "always_discover": False}},
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf,
            "AsyncServiceBrowser",
            side_effect=lambda *args, **kwargs: service_update_mock(
                *args, **kwargs, limit_service="_hap._udp.local."
            ),
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_homekit_info_mock(
                "Smart Bridge-001", HOMEKIT_STATUS_UNPAIRED
            ),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "lutron_caseta"


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_homekit_match_partial_fnmatch(hass: HomeAssistant) -> None:
    """Test matching homekit devices with fnmatch."""
    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {"_hap._tcp.local.": [{"domain": "homekit_controller"}]},
            clear=True,
        ),
        patch.dict(
            zc_gen.HOMEKIT,
            {"YLDP*": {"domain": "yeelight", "always_discover": False}},
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf,
            "AsyncServiceBrowser",
            side_effect=lambda *args, **kwargs: service_update_mock(
                *args, **kwargs, limit_service="_hap._tcp.local."
            ),
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_homekit_info_mock("YLDP13YL", HOMEKIT_STATUS_UNPAIRED),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "yeelight"


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_homekit_match_full(hass: HomeAssistant) -> None:
    """Test configured options for a device are loaded via config entry."""
    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {"_hap._udp.local.": [{"domain": "homekit_controller"}]},
            clear=True,
        ),
        patch.dict(
            zc_gen.HOMEKIT,
            {"BSB002": {"domain": "hue", "always_discover": False}},
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf,
            "AsyncServiceBrowser",
            side_effect=lambda *args, **kwargs: service_update_mock(
                *args, **kwargs, limit_service="_hap._udp.local."
            ),
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_homekit_info_mock("BSB002", HOMEKIT_STATUS_UNPAIRED),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "hue"


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_homekit_already_paired(hass: HomeAssistant) -> None:
    """Test that an already paired device is sent to homekit_controller."""
    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {"_hap._tcp.local.": [{"domain": "homekit_controller"}]},
            clear=True,
        ),
        patch.dict(
            zc_gen.HOMEKIT,
            {
                "AC02": {"domain": "tado", "always_discover": True},
                "tado": {"domain": "tado", "always_discover": True},
            },
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf,
            "AsyncServiceBrowser",
            side_effect=lambda *args, **kwargs: service_update_mock(
                *args, **kwargs, limit_service="_hap._tcp.local."
            ),
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_homekit_info_mock("tado", HOMEKIT_STATUS_PAIRED),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 2
    assert mock_config_flow.mock_calls[0][1][0] == "tado"
    assert mock_config_flow.mock_calls[1][1][0] == "homekit_controller"


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_homekit_invalid_paring_status(hass: HomeAssistant) -> None:
    """Test that missing paring data is not sent to homekit_controller."""
    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {"_hap._tcp.local.": [{"domain": "homekit_controller"}]},
            clear=True,
        ),
        patch.dict(
            zc_gen.HOMEKIT,
            {"Smart Bridge": {"domain": "lutron_caseta", "always_discover": False}},
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf,
            "AsyncServiceBrowser",
            side_effect=lambda *args, **kwargs: service_update_mock(
                *args, **kwargs, limit_service="_hap._tcp.local."
            ),
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_homekit_info_mock("Smart Bridge", b"invalid"),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "lutron_caseta"


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_homekit_not_paired(hass: HomeAssistant) -> None:
    """Test that an not paired device is sent to homekit_controller."""
    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {"_hap._tcp.local.": [{"domain": "homekit_controller"}]},
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf, "AsyncServiceBrowser", side_effect=service_update_mock
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_homekit_info_mock(
                "this_will_not_match_any_integration", HOMEKIT_STATUS_UNPAIRED
            ),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "homekit_controller"


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_homekit_controller_still_discovered_unpaired_for_cloud(
    hass: HomeAssistant,
) -> None:
    """Test discovery is still passed to homekit controller when unpaired.

    When unpaired and discovered by cloud integration.

    Since we prefer local control, if the integration that is being discovered
    is cloud AND the homekit device is unpaired we still want to discovery it
    """
    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {"_hap._udp.local.": [{"domain": "homekit_controller"}]},
            clear=True,
        ),
        patch.dict(
            zc_gen.HOMEKIT,
            {"Rachio": {"domain": "rachio", "always_discover": True}},
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf,
            "AsyncServiceBrowser",
            side_effect=lambda *args, **kwargs: service_update_mock(
                *args, **kwargs, limit_service="_hap._udp.local."
            ),
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_homekit_info_mock("Rachio-xyz", HOMEKIT_STATUS_UNPAIRED),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 2
    assert mock_config_flow.mock_calls[0][1][0] == "rachio"
    assert mock_config_flow.mock_calls[1][1][0] == "homekit_controller"


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_homekit_controller_still_discovered_unpaired_for_polling(
    hass: HomeAssistant,
) -> None:
    """Test discovery is still passed to homekit controller when unpaired.

    When unpaired and discovered by polling integration.

    Since we prefer local push, if the integration that is being discovered
    is polling AND the homekit device is unpaired we still want to discovery it
    """
    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {"_hap._udp.local.": [{"domain": "homekit_controller"}]},
            clear=True,
        ),
        patch.dict(
            zc_gen.HOMEKIT,
            {"iSmartGate": {"domain": "gogogate2", "always_discover": True}},
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf,
            "AsyncServiceBrowser",
            side_effect=lambda *args, **kwargs: service_update_mock(
                *args, **kwargs, limit_service="_hap._udp.local."
            ),
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_homekit_info_mock("iSmartGate", HOMEKIT_STATUS_UNPAIRED),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 2
    assert mock_config_flow.mock_calls[0][1][0] == "gogogate2"
    assert mock_config_flow.mock_calls[1][1][0] == "homekit_controller"


async def test_info_from_service_non_utf8(hass: HomeAssistant) -> None:
    """Test info_from_service handles non UTF-8 property keys and values correctly."""
    service_type = "_test._tcp.local."
    info = zeroconf.info_from_service(
        get_service_info_mock(service_type, f"test.{service_type}")
    )
    assert NON_ASCII_KEY.decode("ascii", "replace") in info.properties
    assert "non-utf8-value" in info.properties
    assert info.properties["non-utf8-value"] == NON_UTF8_VALUE.decode(
        "utf-8", "replace"
    )


async def test_info_from_service_with_addresses(hass: HomeAssistant) -> None:
    """Test info_from_service does not throw when there are no addresses."""
    service_type = "_test._tcp.local."
    info = zeroconf.info_from_service(
        get_service_info_mock_without_an_address(service_type, f"test.{service_type}")
    )
    assert info is None


async def test_info_from_service_with_link_local_address_first(
    hass: HomeAssistant,
) -> None:
    """Test that the link local address is ignored."""
    service_type = "_test._tcp.local."
    service_info = get_service_info_mock(service_type, f"test.{service_type}")
    service_info.addresses = ["169.254.12.3", "192.168.66.12"]
    info = zeroconf.info_from_service(service_info)
    assert info.host == "192.168.66.12"
    assert info.addresses == ["169.254.12.3", "192.168.66.12"]


async def test_info_from_service_with_unspecified_address_first(
    hass: HomeAssistant,
) -> None:
    """Test that the unspecified address is ignored."""
    service_type = "_test._tcp.local."
    service_info = get_service_info_mock(service_type, f"test.{service_type}")
    service_info.addresses = ["0.0.0.0", "192.168.66.12"]
    info = zeroconf.info_from_service(service_info)
    assert info.host == "192.168.66.12"
    assert info.addresses == ["0.0.0.0", "192.168.66.12"]


async def test_info_from_service_with_unspecified_address_only(
    hass: HomeAssistant,
) -> None:
    """Test that the unspecified address is ignored."""
    service_type = "_test._tcp.local."
    service_info = get_service_info_mock(service_type, f"test.{service_type}")
    service_info.addresses = ["0.0.0.0"]
    info = zeroconf.info_from_service(service_info)
    assert info is None


async def test_info_from_service_with_link_local_address_second(
    hass: HomeAssistant,
) -> None:
    """Test that the link local address is ignored."""
    service_type = "_test._tcp.local."
    service_info = get_service_info_mock(service_type, f"test.{service_type}")
    service_info.addresses = ["192.168.66.12", "169.254.12.3"]
    info = zeroconf.info_from_service(service_info)
    assert info.host == "192.168.66.12"
    assert info.addresses == ["192.168.66.12", "169.254.12.3"]


async def test_info_from_service_with_link_local_address_only(
    hass: HomeAssistant,
) -> None:
    """Test that the link local address is ignored."""
    service_type = "_test._tcp.local."
    service_info = get_service_info_mock(service_type, f"test.{service_type}")
    service_info.addresses = ["169.254.12.3"]
    info = zeroconf.info_from_service(service_info)
    assert info is None


async def test_info_from_service_prefers_ipv4(hass: HomeAssistant) -> None:
    """Test that ipv4 addresses are preferred."""
    service_type = "_test._tcp.local."
    service_info = get_service_info_mock(service_type, f"test.{service_type}")
    service_info.addresses = ["2001:db8:3333:4444:5555:6666:7777:8888", "192.168.66.12"]
    info = zeroconf.info_from_service(service_info)
    assert info.host == "192.168.66.12"


async def test_info_from_service_can_return_ipv6(hass: HomeAssistant) -> None:
    """Test that IPv6-only devices can be discovered."""
    service_type = "_test._tcp.local."
    service_info = get_service_info_mock(service_type, f"test.{service_type}")
    service_info.addresses = ["fd11:1111:1111:0:1234:1234:1234:1234"]
    info = zeroconf.info_from_service(service_info)
    assert info.host == "fd11:1111:1111:0:1234:1234:1234:1234"


async def test_get_instance(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock
) -> None:
    """Test we get an instance."""
    assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
    assert await zeroconf.async_get_async_instance(hass) is mock_async_zeroconf
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert len(mock_async_zeroconf.ha_async_close.mock_calls) == 0
    # Only shutdown at the close event so integrations have time
    # to send out their goodbyes
    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()
    assert len(mock_async_zeroconf.ha_async_close.mock_calls) == 1


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_removed_ignored(hass: HomeAssistant) -> None:
    """Test we remove it when a zeroconf entry is removed."""

    def service_update_mock(zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_service.added.local.",
            "name._service.added.local.",
            ServiceStateChange.Added,
        )
        handlers[0](
            zeroconf,
            "_service.updated.local.",
            "name._service.updated.local.",
            ServiceStateChange.Updated,
        )
        handlers[0](
            zeroconf,
            "_service.removed.local.",
            "name._service.removed.local.",
            ServiceStateChange.Removed,
        )

    with (
        patch.object(zeroconf, "AsyncServiceBrowser", side_effect=service_update_mock),
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_service_info_mock,
        ) as mock_service_info,
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_info.mock_calls) == 2
    assert mock_service_info.mock_calls[0][1][0] == "_service.added.local."
    assert mock_service_info.mock_calls[1][1][0] == "_service.updated.local."


_ADAPTER_WITH_DEFAULT_ENABLED = [
    {
        "auto": True,
        "default": True,
        "enabled": True,
        "ipv4": [{"address": "192.168.1.5", "network_prefix": 23}],
        "ipv6": [],
        "name": "eth1",
    }
]


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_async_detect_interfaces_setting_non_loopback_route(
    hass: HomeAssistant,
) -> None:
    """Test without default interface and the route returns a non-loopback address."""
    with (
        patch("homeassistant.components.zeroconf.HaZeroconf") as mock_zc,
        patch.object(hass.config_entries.flow, "async_init"),
        patch.object(zeroconf, "AsyncServiceBrowser", side_effect=service_update_mock),
        patch(
            "homeassistant.components.zeroconf.network.async_get_adapters",
            return_value=_ADAPTER_WITH_DEFAULT_ENABLED,
        ),
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_service_info_mock,
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert mock_zc.mock_calls[0] == call(
        interfaces=InterfaceChoice.Default, ip_version=IPVersion.V4Only
    )


_ADAPTERS_WITH_MANUAL_CONFIG = [
    {
        "auto": True,
        "index": 1,
        "default": False,
        "enabled": True,
        "ipv4": [],
        "ipv6": [
            {
                "address": "2001:db8::",
                "network_prefix": 64,
                "flowinfo": 1,
                "scope_id": 1,
            },
            {
                "address": "fe80::1234:5678:9abc:def0",
                "network_prefix": 64,
                "flowinfo": 1,
                "scope_id": 1,
            },
        ],
        "name": "eth0",
    },
    {
        "auto": True,
        "index": 2,
        "default": False,
        "enabled": True,
        "ipv4": [{"address": "192.168.1.5", "network_prefix": 23}],
        "ipv6": [],
        "name": "eth1",
    },
    {
        "auto": True,
        "index": 3,
        "default": False,
        "enabled": True,
        "ipv4": [{"address": "172.16.1.5", "network_prefix": 23}],
        "ipv6": [
            {
                "address": "fe80::dead:beef:dead:beef",
                "network_prefix": 64,
                "flowinfo": 1,
                "scope_id": 3,
            }
        ],
        "name": "eth2",
    },
    {
        "auto": False,
        "index": 4,
        "default": False,
        "enabled": False,
        "ipv4": [{"address": "169.254.3.2", "network_prefix": 16}],
        "ipv6": [],
        "name": "vtun0",
    },
]


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_async_detect_interfaces_setting_empty_route_linux(
    hass: HomeAssistant,
) -> None:
    """Test without default interface config and the route returns nothing on linux."""
    with (
        patch("homeassistant.components.zeroconf.sys.platform", "linux"),
        patch("homeassistant.components.zeroconf.HaZeroconf") as mock_zc,
        patch.object(hass.config_entries.flow, "async_init"),
        patch.object(zeroconf, "AsyncServiceBrowser", side_effect=service_update_mock),
        patch(
            "homeassistant.components.zeroconf.network.async_get_adapters",
            return_value=_ADAPTERS_WITH_MANUAL_CONFIG,
        ),
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_service_info_mock,
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
    assert mock_zc.mock_calls[0] == call(
        interfaces=[
            "2001:db8::%1",
            "fe80::1234:5678:9abc:def0%1",
            "192.168.1.5",
            "172.16.1.5",
            "fe80::dead:beef:dead:beef%3",
        ],
        ip_version=IPVersion.All,
    )


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_async_detect_interfaces_setting_empty_route_freebsd(
    hass: HomeAssistant,
) -> None:
    """Test without default interface and the route returns nothing on freebsd."""
    with (
        patch("homeassistant.components.zeroconf.sys.platform", "freebsd"),
        patch("homeassistant.components.zeroconf.HaZeroconf") as mock_zc,
        patch.object(hass.config_entries.flow, "async_init"),
        patch.object(zeroconf, "AsyncServiceBrowser", side_effect=service_update_mock),
        patch(
            "homeassistant.components.zeroconf.network.async_get_adapters",
            return_value=_ADAPTERS_WITH_MANUAL_CONFIG,
        ),
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_service_info_mock,
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
    assert mock_zc.mock_calls[0] == call(
        interfaces=[
            "192.168.1.5",
            "172.16.1.5",
        ],
        ip_version=IPVersion.V4Only,
    )


_ADAPTER_WITH_DEFAULT_ENABLED_AND_IPV6 = [
    {
        "auto": True,
        "default": True,
        "enabled": True,
        "index": 1,
        "ipv4": [{"address": "192.168.1.5", "network_prefix": 23}],
        "ipv6": [
            {
                "address": "fe80::dead:beef:dead:beef",
                "network_prefix": 64,
                "flowinfo": 1,
                "scope_id": 3,
            }
        ],
        "name": "eth1",
    }
]


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_async_detect_interfaces_explicitly_set_ipv6_linux(
    hass: HomeAssistant,
) -> None:
    """Test interfaces are explicitly set when IPv6 is present on linux."""
    with (
        patch("homeassistant.components.zeroconf.sys.platform", "linux"),
        patch("homeassistant.components.zeroconf.HaZeroconf") as mock_zc,
        patch.object(hass.config_entries.flow, "async_init"),
        patch.object(zeroconf, "AsyncServiceBrowser", side_effect=service_update_mock),
        patch(
            "homeassistant.components.zeroconf.network.async_get_adapters",
            return_value=_ADAPTER_WITH_DEFAULT_ENABLED_AND_IPV6,
        ),
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_service_info_mock,
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert mock_zc.mock_calls[0] == call(
        interfaces=["192.168.1.5", "fe80::dead:beef:dead:beef%3"],
        ip_version=IPVersion.All,
    )


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_async_detect_interfaces_explicitly_set_ipv6_freebsd(
    hass: HomeAssistant,
) -> None:
    """Test interfaces are explicitly set when IPv6 is present on freebsd."""
    with (
        patch("homeassistant.components.zeroconf.sys.platform", "freebsd"),
        patch("homeassistant.components.zeroconf.HaZeroconf") as mock_zc,
        patch.object(hass.config_entries.flow, "async_init"),
        patch.object(zeroconf, "AsyncServiceBrowser", side_effect=service_update_mock),
        patch(
            "homeassistant.components.zeroconf.network.async_get_adapters",
            return_value=_ADAPTER_WITH_DEFAULT_ENABLED_AND_IPV6,
        ),
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_service_info_mock,
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert mock_zc.mock_calls[0] == call(
        interfaces=InterfaceChoice.Default,
        ip_version=IPVersion.V4Only,
    )


async def test_no_name(hass: HomeAssistant, mock_async_zeroconf: MagicMock) -> None:
    """Test fallback to Home for mDNS announcement if the name is missing."""
    hass.config.location_name = ""
    with patch("homeassistant.components.zeroconf.HaZeroconf"):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    register_call = mock_async_zeroconf.async_register_service.mock_calls[-1]
    info = register_call.args[0]
    assert info.name == "Home._home-assistant._tcp.local."


async def test_setup_with_disallowed_characters_in_local_name(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock
) -> None:
    """Test we still setup with disallowed characters in the location name."""
    with (
        patch.object(hass.config_entries.flow, "async_init"),
        patch.object(zeroconf, "AsyncServiceBrowser", side_effect=service_update_mock),
        patch.object(
            hass.config,
            "location_name",
            "My.House",
        ),
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo.async_request",
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    calls = mock_async_zeroconf.async_register_service.mock_calls
    assert calls[0][1][0].name == "My House._home-assistant._tcp.local."


async def test_start_with_frontend(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock
) -> None:
    """Test we start with the frontend."""
    with patch("homeassistant.components.zeroconf.HaZeroconf"):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: "frontend"})
        await hass.async_block_till_done()

    mock_async_zeroconf.async_register_service.assert_called_once()


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_zeroconf_removed(hass: HomeAssistant) -> None:
    """Test we dismiss flows when a PTR record is removed."""

    def _device_removed_mock(zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_http._tcp.local.",
            "Shelly108._http._tcp.local.",
            ServiceStateChange.Removed,
        )

    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {
                "_http._tcp.local.": [
                    {
                        "domain": "shelly",
                        "name": "shelly*",
                    }
                ]
            },
            clear=True,
        ),
        patch.object(
            hass.config_entries.flow,
            "async_progress_by_init_data_type",
            return_value=[{"flow_id": "mock_flow_id"}],
        ) as mock_async_progress_by_init_data_type,
        patch.object(hass.config_entries.flow, "async_abort") as mock_async_abort,
        patch.object(
            zeroconf, "AsyncServiceBrowser", side_effect=_device_removed_mock
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_zeroconf_info_mock("FFAADDCC11DD"),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_async_progress_by_init_data_type.mock_calls) == 1
    assert mock_async_abort.mock_calls[0][1][0] == "mock_flow_id"


@pytest.mark.usefixtures("mock_async_zeroconf")
@pytest.mark.parametrize(
    (
        "entry_domain",
        "entry_discovery_keys",
    ),
    [
        # Matching discovery key
        (
            "shelly",
            {
                "zeroconf": (
                    DiscoveryKey(
                        domain="zeroconf",
                        key=("_http._tcp.local.", "Shelly108._http._tcp.local."),
                        version=1,
                    ),
                )
            },
        ),
        # Matching discovery key
        (
            "shelly",
            {
                "zeroconf": (
                    DiscoveryKey(
                        domain="zeroconf",
                        key=("_http._tcp.local.", "Shelly108._http._tcp.local."),
                        version=1,
                    ),
                ),
                "other": (
                    DiscoveryKey(
                        domain="other",
                        key="blah",
                        version=1,
                    ),
                ),
            },
        ),
        # Matching discovery key, other domain
        # Note: Rediscovery is not currently restricted to the domain of the removed
        # entry. Such a check can be added if needed.
        (
            "comp",
            {
                "zeroconf": (
                    DiscoveryKey(
                        domain="zeroconf",
                        key=("_http._tcp.local.", "Shelly108._http._tcp.local."),
                        version=1,
                    ),
                )
            },
        ),
    ],
)
@pytest.mark.parametrize(
    "entry_source",
    [
        config_entries.SOURCE_IGNORE,
        config_entries.SOURCE_USER,
        config_entries.SOURCE_ZEROCONF,
    ],
)
async def test_zeroconf_rediscover(
    hass: HomeAssistant,
    entry_domain: str,
    entry_discovery_keys: dict[str, tuple[DiscoveryKey, ...]],
    entry_source: str,
) -> None:
    """Test we reinitiate flows when an ignored config entry is removed."""

    def http_only_service_update_mock(zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_http._tcp.local.",
            "Shelly108._http._tcp.local.",
            ServiceStateChange.Added,
        )

    entry = MockConfigEntry(
        domain=entry_domain,
        discovery_keys=entry_discovery_keys,
        unique_id="mock-unique-id",
        state=config_entries.ConfigEntryState.LOADED,
        source=entry_source,
    )
    entry.add_to_hass(hass)

    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {
                "_http._tcp.local.": [
                    {
                        "domain": "shelly",
                        "name": "shelly*",
                        "properties": {"macaddress": "ffaadd*"},
                    }
                ]
            },
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf, "AsyncServiceBrowser", side_effect=http_only_service_update_mock
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_zeroconf_info_mock("FFAADDCC11DD"),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        expected_context = {
            "discovery_key": DiscoveryKey(
                domain="zeroconf",
                key=("_http._tcp.local.", "Shelly108._http._tcp.local."),
                version=1,
            ),
            "source": "zeroconf",
        }
        assert len(mock_service_browser.mock_calls) == 1
        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "shelly"
        assert mock_config_flow.mock_calls[0][2]["context"] == expected_context

        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()

        assert len(mock_service_browser.mock_calls) == 1
        assert len(mock_config_flow.mock_calls) == 2
        assert mock_config_flow.mock_calls[1][1][0] == "shelly"
        assert mock_config_flow.mock_calls[1][2]["context"] == expected_context


@pytest.mark.usefixtures("mock_async_zeroconf")
@pytest.mark.parametrize(
    (
        "entry_domain",
        "entry_discovery_keys",
        "entry_source",
        "entry_unique_id",
    ),
    [
        # Discovery key from other domain
        (
            "shelly",
            {
                "bluetooth": (
                    DiscoveryKey(
                        domain="bluetooth",
                        key=("_http._tcp.local.", "Shelly108._http._tcp.local."),
                        version=1,
                    ),
                )
            },
            config_entries.SOURCE_IGNORE,
            "mock-unique-id",
        ),
        # Discovery key from the future
        (
            "shelly",
            {
                "zeroconf": (
                    DiscoveryKey(
                        domain="zeroconf",
                        key=("_http._tcp.local.", "Shelly108._http._tcp.local."),
                        version=2,
                    ),
                )
            },
            config_entries.SOURCE_IGNORE,
            "mock-unique-id",
        ),
    ],
)
async def test_zeroconf_rediscover_no_match(
    hass: HomeAssistant,
    entry_domain: str,
    entry_discovery_keys: dict[str, tuple[DiscoveryKey, ...]],
    entry_source: str,
    entry_unique_id: str,
) -> None:
    """Test we don't reinitiate flows when a non matching config entry is removed."""

    def http_only_service_update_mock(zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_http._tcp.local.",
            "Shelly108._http._tcp.local.",
            ServiceStateChange.Added,
        )

    hass.config.components.add(entry_domain)
    mock_integration(hass, MockModule(entry_domain))

    entry = MockConfigEntry(
        domain=entry_domain,
        discovery_keys=entry_discovery_keys,
        unique_id=entry_unique_id,
        state=config_entries.ConfigEntryState.LOADED,
        source=entry_source,
    )
    entry.add_to_hass(hass)

    with (
        patch.dict(
            zc_gen.ZEROCONF,
            {
                "_http._tcp.local.": [
                    {
                        "domain": "shelly",
                        "name": "shelly*",
                        "properties": {"macaddress": "ffaadd*"},
                    }
                ]
            },
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
        patch.object(
            zeroconf, "AsyncServiceBrowser", side_effect=http_only_service_update_mock
        ) as mock_service_browser,
        patch(
            "homeassistant.components.zeroconf.AsyncServiceInfo",
            side_effect=get_zeroconf_info_mock("FFAADDCC11DD"),
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        expected_context = {
            "discovery_key": DiscoveryKey(
                domain="zeroconf",
                key=("_http._tcp.local.", "Shelly108._http._tcp.local."),
                version=1,
            ),
            "source": "zeroconf",
        }
        assert len(mock_service_browser.mock_calls) == 1
        assert len(mock_config_flow.mock_calls) == 1
        assert mock_config_flow.mock_calls[0][1][0] == "shelly"
        assert mock_config_flow.mock_calls[0][2]["context"] == expected_context

        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()

        assert len(mock_service_browser.mock_calls) == 1
        assert len(mock_config_flow.mock_calls) == 1
