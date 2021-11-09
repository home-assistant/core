"""Test Zeroconf component setup process."""
from ipaddress import ip_address
from typing import Any
from unittest.mock import call, patch

from zeroconf import InterfaceChoice, IPVersion, ServiceStateChange
from zeroconf.asyncio import AsyncServiceInfo

from homeassistant.components import zeroconf
from homeassistant.components.zeroconf import (
    CONF_DEFAULT_INTERFACE,
    CONF_IPV6,
    _get_announced_addresses,
)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.generated import zeroconf as zc_gen
from homeassistant.setup import async_setup_component

NON_UTF8_VALUE = b"ABCDEF\x8a"
NON_ASCII_KEY = b"non-ascii-key\x8a"
PROPERTIES = {
    b"macaddress": b"ABCDEF012345",
    b"non-utf8-value": NON_UTF8_VALUE,
    NON_ASCII_KEY: None,
}

HOMEKIT_STATUS_UNPAIRED = b"1"
HOMEKIT_STATUS_PAIRED = b"0"


def service_update_mock(ipv6, zeroconf, services, handlers, *, limit_service=None):
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


async def test_setup(hass, mock_async_zeroconf):
    """Test configured options for a device are loaded via config entry."""
    with patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=service_update_mock
    ) as mock_service_browser, patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_service_info_mock,
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    expected_flow_calls = 0
    for matching_components in zc_gen.ZEROCONF.values():
        domains = set()
        for component in matching_components:
            if len(component) == 1:
                domains.add(component["domain"])
        expected_flow_calls += len(domains)
    assert len(mock_config_flow.mock_calls) == expected_flow_calls

    # Test instance is set.
    assert "zeroconf" in hass.data
    assert (
        await hass.components.zeroconf.async_get_async_instance() is mock_async_zeroconf
    )


async def test_setup_with_overly_long_url_and_name(hass, mock_async_zeroconf, caplog):
    """Test we still setup with long urls and names."""
    with patch.object(hass.config_entries.flow, "async_init"), patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=service_update_mock
    ), patch(
        "homeassistant.components.zeroconf.get_url",
        return_value="https://this.url.is.way.too.long/very/deep/path/that/will/make/us/go/over/the/maximum/string/length/and/would/cause/zeroconf/to/fail/to/startup/because/the/key/and/value/can/only/be/255/bytes/and/this/string/is/a/bit/longer/than/the/maximum/length/that/we/allow/for/a/value",
    ), patch.object(
        hass.config,
        "location_name",
        "\u00dcBER \u00dcber German Umlaut long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string long string",
    ), patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo.request",
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    assert "https://this.url.is.way.too.long" in caplog.text
    assert "German Umlaut" in caplog.text


async def test_setup_with_default_interface(hass, mock_async_zeroconf):
    """Test default interface config."""
    with patch.object(hass.config_entries.flow, "async_init"), patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=service_update_mock
    ), patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_service_info_mock,
    ):
        assert await async_setup_component(
            hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {CONF_DEFAULT_INTERFACE: True}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert mock_async_zeroconf.called_with(interface_choice=InterfaceChoice.Default)


async def test_setup_without_default_interface(hass, mock_async_zeroconf):
    """Test without default interface config."""
    with patch.object(hass.config_entries.flow, "async_init"), patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=service_update_mock
    ), patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_service_info_mock,
    ):
        assert await async_setup_component(
            hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {CONF_DEFAULT_INTERFACE: False}}
        )

    assert mock_async_zeroconf.called_with()


async def test_setup_without_ipv6(hass, mock_async_zeroconf):
    """Test without ipv6."""
    with patch.object(hass.config_entries.flow, "async_init"), patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=service_update_mock
    ), patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_service_info_mock,
    ):
        assert await async_setup_component(
            hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {CONF_IPV6: False}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert mock_async_zeroconf.called_with(ip_version=IPVersion.V4Only)


async def test_setup_with_ipv6(hass, mock_async_zeroconf):
    """Test without ipv6."""
    with patch.object(hass.config_entries.flow, "async_init"), patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=service_update_mock
    ), patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_service_info_mock,
    ):
        assert await async_setup_component(
            hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {CONF_IPV6: True}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert mock_async_zeroconf.called_with()


async def test_setup_with_ipv6_default(hass, mock_async_zeroconf):
    """Test without ipv6 as default."""
    with patch.object(hass.config_entries.flow, "async_init"), patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=service_update_mock
    ), patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_service_info_mock,
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert mock_async_zeroconf.called_with()


async def test_zeroconf_match_macaddress(hass, mock_async_zeroconf):
    """Test configured options for a device are loaded via config entry."""

    def http_only_service_update_mock(ipv6, zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_http._tcp.local.",
            "Shelly108._http._tcp.local.",
            ServiceStateChange.Added,
        )

    with patch.dict(
        zc_gen.ZEROCONF,
        {
            "_http._tcp.local.": [
                {"domain": "shelly", "name": "shelly*", "macaddress": "FFAADD*"}
            ]
        },
        clear=True,
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=http_only_service_update_mock
    ) as mock_service_browser, patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_zeroconf_info_mock("FFAADDCC11DD"),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "shelly"


async def test_zeroconf_match_manufacturer(hass, mock_async_zeroconf):
    """Test configured options for a device are loaded via config entry."""

    def http_only_service_update_mock(ipv6, zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_airplay._tcp.local.",
            "s1000._airplay._tcp.local.",
            ServiceStateChange.Added,
        )

    with patch.dict(
        zc_gen.ZEROCONF,
        {"_airplay._tcp.local.": [{"domain": "samsungtv", "manufacturer": "samsung*"}]},
        clear=True,
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=http_only_service_update_mock
    ) as mock_service_browser, patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_zeroconf_info_mock_manufacturer("Samsung Electronics"),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "samsungtv"


async def test_zeroconf_match_model(hass, mock_async_zeroconf):
    """Test matching a specific model in zeroconf."""

    def http_only_service_update_mock(ipv6, zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_airplay._tcp.local.",
            "s1000._airplay._tcp.local.",
            ServiceStateChange.Added,
        )

    with patch.dict(
        zc_gen.ZEROCONF,
        {"_airplay._tcp.local.": [{"domain": "appletv", "model": "appletv*"}]},
        clear=True,
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=http_only_service_update_mock
    ) as mock_service_browser, patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_zeroconf_info_mock_model("appletv"),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "appletv"


async def test_zeroconf_match_manufacturer_not_present(hass, mock_async_zeroconf):
    """Test matchers reject when a property is missing."""

    def http_only_service_update_mock(ipv6, zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_airplay._tcp.local.",
            "s1000._airplay._tcp.local.",
            ServiceStateChange.Added,
        )

    with patch.dict(
        zc_gen.ZEROCONF,
        {"_airplay._tcp.local.": [{"domain": "samsungtv", "manufacturer": "samsung*"}]},
        clear=True,
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=http_only_service_update_mock
    ) as mock_service_browser, patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_zeroconf_info_mock("aabbccddeeff"),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 0


async def test_zeroconf_no_match(hass, mock_async_zeroconf):
    """Test configured options for a device are loaded via config entry."""

    def http_only_service_update_mock(ipv6, zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_http._tcp.local.",
            "somethingelse._http._tcp.local.",
            ServiceStateChange.Added,
        )

    with patch.dict(
        zc_gen.ZEROCONF,
        {"_http._tcp.local.": [{"domain": "shelly", "name": "shelly*"}]},
        clear=True,
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=http_only_service_update_mock
    ) as mock_service_browser, patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_zeroconf_info_mock("FFAADDCC11DD"),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 0


async def test_zeroconf_no_match_manufacturer(hass, mock_async_zeroconf):
    """Test configured options for a device are loaded via config entry."""

    def http_only_service_update_mock(ipv6, zeroconf, services, handlers):
        """Call service update handler."""
        handlers[0](
            zeroconf,
            "_airplay._tcp.local.",
            "s1000._airplay._tcp.local.",
            ServiceStateChange.Added,
        )

    with patch.dict(
        zc_gen.ZEROCONF,
        {"_airplay._tcp.local.": [{"domain": "samsungtv", "manufacturer": "samsung*"}]},
        clear=True,
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=http_only_service_update_mock
    ) as mock_service_browser, patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_zeroconf_info_mock_manufacturer("Not Samsung Electronics"),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 0


async def test_homekit_match_partial_space(hass, mock_async_zeroconf):
    """Test configured options for a device are loaded via config entry."""
    with patch.dict(
        zc_gen.ZEROCONF,
        {"_hap._tcp.local.": [{"domain": "homekit_controller"}]},
        clear=True,
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf,
        "HaAsyncServiceBrowser",
        side_effect=lambda *args, **kwargs: service_update_mock(
            *args, **kwargs, limit_service="_hap._tcp.local."
        ),
    ) as mock_service_browser, patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_homekit_info_mock("LIFX bulb", HOMEKIT_STATUS_UNPAIRED),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "lifx"


async def test_homekit_match_partial_dash(hass, mock_async_zeroconf):
    """Test configured options for a device are loaded via config entry."""
    with patch.dict(
        zc_gen.ZEROCONF,
        {"_hap._udp.local.": [{"domain": "homekit_controller"}]},
        clear=True,
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf,
        "HaAsyncServiceBrowser",
        side_effect=lambda *args, **kwargs: service_update_mock(
            *args, **kwargs, limit_service="_hap._udp.local."
        ),
    ) as mock_service_browser, patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_homekit_info_mock("Rachio-fa46ba", HOMEKIT_STATUS_UNPAIRED),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "rachio"


async def test_homekit_match_partial_fnmatch(hass, mock_async_zeroconf):
    """Test matching homekit devices with fnmatch."""
    with patch.dict(
        zc_gen.ZEROCONF,
        {"_hap._tcp.local.": [{"domain": "homekit_controller"}]},
        clear=True,
    ), patch.dict(zc_gen.HOMEKIT, {"YLDP*": "yeelight"}, clear=True,), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf,
        "HaAsyncServiceBrowser",
        side_effect=lambda *args, **kwargs: service_update_mock(
            *args, **kwargs, limit_service="_hap._tcp.local."
        ),
    ) as mock_service_browser, patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_homekit_info_mock("YLDP13YL", HOMEKIT_STATUS_UNPAIRED),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "yeelight"


async def test_homekit_match_full(hass, mock_async_zeroconf):
    """Test configured options for a device are loaded via config entry."""
    with patch.dict(
        zc_gen.ZEROCONF,
        {"_hap._udp.local.": [{"domain": "homekit_controller"}]},
        clear=True,
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf,
        "HaAsyncServiceBrowser",
        side_effect=lambda *args, **kwargs: service_update_mock(
            *args, **kwargs, limit_service="_hap._udp.local."
        ),
    ) as mock_service_browser, patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_homekit_info_mock("BSB002", HOMEKIT_STATUS_UNPAIRED),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "hue"


async def test_homekit_already_paired(hass, mock_async_zeroconf):
    """Test that an already paired device is sent to homekit_controller."""
    with patch.dict(
        zc_gen.ZEROCONF,
        {"_hap._tcp.local.": [{"domain": "homekit_controller"}]},
        clear=True,
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf,
        "HaAsyncServiceBrowser",
        side_effect=lambda *args, **kwargs: service_update_mock(
            *args, **kwargs, limit_service="_hap._tcp.local."
        ),
    ) as mock_service_browser, patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_homekit_info_mock("tado", HOMEKIT_STATUS_PAIRED),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 2
    assert mock_config_flow.mock_calls[0][1][0] == "tado"
    assert mock_config_flow.mock_calls[1][1][0] == "homekit_controller"


async def test_homekit_invalid_paring_status(hass, mock_async_zeroconf):
    """Test that missing paring data is not sent to homekit_controller."""
    with patch.dict(
        zc_gen.ZEROCONF,
        {"_hap._tcp.local.": [{"domain": "homekit_controller"}]},
        clear=True,
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf,
        "HaAsyncServiceBrowser",
        side_effect=lambda *args, **kwargs: service_update_mock(
            *args, **kwargs, limit_service="_hap._tcp.local."
        ),
    ) as mock_service_browser, patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_homekit_info_mock("tado", b"invalid"),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "tado"


async def test_homekit_not_paired(hass, mock_async_zeroconf):
    """Test that an not paired device is sent to homekit_controller."""
    with patch.dict(
        zc_gen.ZEROCONF,
        {"_hap._tcp.local.": [{"domain": "homekit_controller"}]},
        clear=True,
    ), patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_config_flow, patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=service_update_mock
    ) as mock_service_browser, patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_homekit_info_mock(
            "this_will_not_match_any_integration", HOMEKIT_STATUS_UNPAIRED
        ),
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "homekit_controller"


async def test_info_from_service_non_utf8(hass):
    """Test info_from_service handles non UTF-8 property keys and values correctly."""
    service_type = "_test._tcp.local."
    info = zeroconf.info_from_service(
        get_service_info_mock(service_type, f"test.{service_type}")
    )
    raw_info = info["properties"].pop("_raw", False)
    assert raw_info
    assert len(raw_info) == len(PROPERTIES) - 1
    assert NON_ASCII_KEY not in raw_info
    assert len(info["properties"]) <= len(raw_info)
    assert "non-utf8-value" not in info["properties"]
    assert raw_info["non-utf8-value"] is NON_UTF8_VALUE


async def test_info_from_service_with_addresses(hass):
    """Test info_from_service does not throw when there are no addresses."""
    service_type = "_test._tcp.local."
    info = zeroconf.info_from_service(
        get_service_info_mock_without_an_address(service_type, f"test.{service_type}")
    )
    assert info is None


async def test_info_from_service_with_link_local_address_first(hass):
    """Test that the link local address is ignored."""
    service_type = "_test._tcp.local."
    service_info = get_service_info_mock(service_type, f"test.{service_type}")
    service_info.addresses = ["169.254.12.3", "192.168.66.12"]
    info = zeroconf.info_from_service(service_info)
    assert info["host"] == "192.168.66.12"


async def test_info_from_service_with_link_local_address_second(hass):
    """Test that the link local address is ignored."""
    service_type = "_test._tcp.local."
    service_info = get_service_info_mock(service_type, f"test.{service_type}")
    service_info.addresses = ["192.168.66.12", "169.254.12.3"]
    info = zeroconf.info_from_service(service_info)
    assert info["host"] == "192.168.66.12"


async def test_info_from_service_with_link_local_address_only(hass):
    """Test that the link local address is ignored."""
    service_type = "_test._tcp.local."
    service_info = get_service_info_mock(service_type, f"test.{service_type}")
    service_info.addresses = ["169.254.12.3"]
    info = zeroconf.info_from_service(service_info)
    assert info is None


async def test_info_from_service_prefers_ipv4(hass):
    """Test that ipv4 addresses are preferred."""
    service_type = "_test._tcp.local."
    service_info = get_service_info_mock(service_type, f"test.{service_type}")
    service_info.addresses = ["2001:db8:3333:4444:5555:6666:7777:8888", "192.168.66.12"]
    info = zeroconf.info_from_service(service_info)
    assert info["host"] == "192.168.66.12"


async def test_get_instance(hass, mock_async_zeroconf):
    """Test we get an instance."""
    assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
    assert (
        await hass.components.zeroconf.async_get_async_instance() is mock_async_zeroconf
    )
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert len(mock_async_zeroconf.ha_async_close.mock_calls) == 1


async def test_removed_ignored(hass, mock_async_zeroconf):
    """Test we remove it when a zeroconf entry is removed."""

    def service_update_mock(ipv6, zeroconf, services, handlers):
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

    with patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=service_update_mock
    ), patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_service_info_mock,
    ) as mock_service_info:
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


async def test_async_detect_interfaces_setting_non_loopback_route(
    hass, mock_async_zeroconf
):
    """Test without default interface config and the route returns a non-loopback address."""
    with patch("homeassistant.components.zeroconf.HaZeroconf") as mock_zc, patch.object(
        hass.config_entries.flow, "async_init"
    ), patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=service_update_mock
    ), patch(
        "homeassistant.components.zeroconf.network.async_get_adapters",
        return_value=_ADAPTER_WITH_DEFAULT_ENABLED,
    ), patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_service_info_mock,
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


async def test_async_detect_interfaces_setting_empty_route_linux(
    hass, mock_async_zeroconf
):
    """Test without default interface config and the route returns nothing on linux."""
    with patch("homeassistant.components.zeroconf.sys.platform", "linux"), patch(
        "homeassistant.components.zeroconf.HaZeroconf"
    ) as mock_zc, patch.object(hass.config_entries.flow, "async_init"), patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=service_update_mock
    ), patch(
        "homeassistant.components.zeroconf.network.async_get_adapters",
        return_value=_ADAPTERS_WITH_MANUAL_CONFIG,
    ), patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_service_info_mock,
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
    assert mock_zc.mock_calls[0] == call(
        interfaces=[
            "2001:db8::",
            "fe80::1234:5678:9abc:def0",
            "192.168.1.5",
            "172.16.1.5",
            "fe80::dead:beef:dead:beef",
        ],
        ip_version=IPVersion.All,
    )


async def test_async_detect_interfaces_setting_empty_route_freebsd(
    hass, mock_async_zeroconf
):
    """Test without default interface config and the route returns nothing on freebsd."""
    with patch("homeassistant.components.zeroconf.sys.platform", "freebsd"), patch(
        "homeassistant.components.zeroconf.HaZeroconf"
    ) as mock_zc, patch.object(hass.config_entries.flow, "async_init"), patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=service_update_mock
    ), patch(
        "homeassistant.components.zeroconf.network.async_get_adapters",
        return_value=_ADAPTERS_WITH_MANUAL_CONFIG,
    ), patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_service_info_mock,
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


async def test_get_announced_addresses(hass, mock_async_zeroconf):
    """Test addresses for mDNS announcement."""
    expected = {
        ip_address(ip).packed
        for ip in [
            "fe80::1234:5678:9abc:def0",
            "2001:db8::",
            "192.168.1.5",
            "fe80::dead:beef:dead:beef",
            "172.16.1.5",
        ]
    }
    first_ip = ip_address("172.16.1.5").packed
    actual = _get_announced_addresses(_ADAPTERS_WITH_MANUAL_CONFIG, first_ip)
    assert actual[0] == first_ip and set(actual) == expected

    first_ip = ip_address("192.168.1.5").packed
    actual = _get_announced_addresses(_ADAPTERS_WITH_MANUAL_CONFIG, first_ip)
    assert actual[0] == first_ip and set(actual) == expected


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


async def test_async_detect_interfaces_explicitly_set_ipv6_linux(
    hass, mock_async_zeroconf
):
    """Test interfaces are explicitly set when IPv6 is present on linux."""
    with patch("homeassistant.components.zeroconf.sys.platform", "linux"), patch(
        "homeassistant.components.zeroconf.HaZeroconf"
    ) as mock_zc, patch.object(hass.config_entries.flow, "async_init"), patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=service_update_mock
    ), patch(
        "homeassistant.components.zeroconf.network.async_get_adapters",
        return_value=_ADAPTER_WITH_DEFAULT_ENABLED_AND_IPV6,
    ), patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_service_info_mock,
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert mock_zc.mock_calls[0] == call(
        interfaces=["192.168.1.5", "fe80::dead:beef:dead:beef"],
        ip_version=IPVersion.All,
    )


async def test_async_detect_interfaces_explicitly_set_ipv6_freebsd(
    hass, mock_async_zeroconf
):
    """Test interfaces are explicitly set when IPv6 is present on freebsd."""
    with patch("homeassistant.components.zeroconf.sys.platform", "freebsd"), patch(
        "homeassistant.components.zeroconf.HaZeroconf"
    ) as mock_zc, patch.object(hass.config_entries.flow, "async_init"), patch.object(
        zeroconf, "HaAsyncServiceBrowser", side_effect=service_update_mock
    ), patch(
        "homeassistant.components.zeroconf.network.async_get_adapters",
        return_value=_ADAPTER_WITH_DEFAULT_ENABLED_AND_IPV6,
    ), patch(
        "homeassistant.components.zeroconf.AsyncServiceInfo",
        side_effect=get_service_info_mock,
    ):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert mock_zc.mock_calls[0] == call(
        interfaces=InterfaceChoice.Default,
        ip_version=IPVersion.V4Only,
    )


async def test_no_name(hass, mock_async_zeroconf):
    """Test fallback to Home for mDNS announcement if the name is missing."""
    hass.config.location_name = ""
    with patch("homeassistant.components.zeroconf.HaZeroconf"):
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    register_call = mock_async_zeroconf.async_register_service.mock_calls[-1]
    info = register_call.args[0]
    assert info.name == "Home._home-assistant._tcp.local."
