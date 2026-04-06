"""Tests for the ZHA helpers of Connectivity Monitor."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from homeassistant.components.connectivity_monitor.zha import (
    _build_registry_name_map,
    _get_zha_gateway,
    _last_seen_to_timestamp,
    async_get_zha_device_last_seen,
    async_get_zha_devices,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

ZHA_DOMAIN = "zha"


# ──────────────────────────────────────────────────────────────────────────────
# _last_seen_to_timestamp
# ──────────────────────────────────────────────────────────────────────────────


def test_last_seen_to_timestamp_none() -> None:
    """Returns None for None input."""
    assert _last_seen_to_timestamp(None) is None


def test_last_seen_to_timestamp_float() -> None:
    """Returns float unchanged for numeric input."""
    assert _last_seen_to_timestamp(1700000000.0) == 1700000000.0


def test_last_seen_to_timestamp_int() -> None:
    """Converts int to float."""
    result = _last_seen_to_timestamp(1700000000)
    assert result == 1700000000.0
    assert isinstance(result, float)


def test_last_seen_to_timestamp_datetime() -> None:
    """Converts datetime to Unix timestamp float."""
    dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
    result = _last_seen_to_timestamp(dt)
    assert result == dt.timestamp()


def test_last_seen_to_timestamp_unsupported_object() -> None:
    """Returns None for an object that is neither numeric nor datetime."""
    assert _last_seen_to_timestamp("not-a-timestamp") is None


# ──────────────────────────────────────────────────────────────────────────────
# _get_zha_gateway
# ──────────────────────────────────────────────────────────────────────────────


def test_get_zha_gateway_no_zha_data(hass: HomeAssistant) -> None:
    """Returns None when ZHA domain is not in hass.data."""
    hass.data.pop(ZHA_DOMAIN, None)
    result = _get_zha_gateway(hass)
    assert result is None


def test_get_zha_gateway_via_gateway_proxy(hass: HomeAssistant) -> None:
    """Returns gateway when found via entry_data.gateway_proxy.gateway."""
    mock_gateway = MagicMock()
    mock_gateway.devices = {}

    mock_proxy = MagicMock()
    mock_proxy.gateway = mock_gateway

    mock_entry_data = MagicMock(spec=[])
    mock_entry_data.gateway_proxy = mock_proxy
    # gateway_proxy.gateway has 'devices'

    hass.data[ZHA_DOMAIN] = {"entry1": mock_entry_data}

    result = _get_zha_gateway(hass)
    assert result is mock_gateway


def test_get_zha_gateway_via_direct_gateway(hass: HomeAssistant) -> None:
    """Returns gateway when found at entry_data.gateway."""
    mock_gateway = MagicMock()
    mock_gateway.devices = {}

    mock_entry_data = MagicMock(spec=[])
    mock_entry_data.gateway_proxy = None
    mock_entry_data.gateway = mock_gateway

    hass.data[ZHA_DOMAIN] = {"entry1": mock_entry_data}

    result = _get_zha_gateway(hass)
    assert result is mock_gateway


def test_get_zha_gateway_entry_data_is_gateway(hass: HomeAssistant) -> None:
    """Returns entry_data itself when it has a 'devices' attribute."""
    mock_entry_data = MagicMock()
    mock_entry_data.gateway_proxy = None
    mock_entry_data.gateway = None
    mock_entry_data.devices = {"ieee_1": MagicMock()}

    hass.data[ZHA_DOMAIN] = {"entry1": mock_entry_data}

    result = _get_zha_gateway(hass)
    assert result is mock_entry_data


def test_get_zha_gateway_not_found(hass: HomeAssistant) -> None:
    """Returns None when no suitable gateway path is found."""
    mock_entry_data = MagicMock(spec=[])
    mock_entry_data.gateway_proxy = None
    mock_entry_data.gateway = None

    hass.data[ZHA_DOMAIN] = {"entry1": mock_entry_data}

    result = _get_zha_gateway(hass)
    assert result is None


def test_get_zha_gateway_non_dict_zha_data(hass: HomeAssistant) -> None:
    """Handles the case where hass.data[ZHA_DOMAIN] is not a dict."""
    mock_gateway = MagicMock()
    mock_gateway.gateway_proxy = None
    mock_gateway.gateway = None
    mock_gateway.devices = {}

    # zha_data is the entry itself (not a dict of entries)
    hass.data[ZHA_DOMAIN] = mock_gateway

    result = _get_zha_gateway(hass)
    assert result is mock_gateway


# ──────────────────────────────────────────────────────────────────────────────
# _build_registry_name_map
# ──────────────────────────────────────────────────────────────────────────────


def test_build_registry_name_map_empty(hass: HomeAssistant) -> None:
    """Returns empty dict when no ZHA devices are in registry."""
    result = _build_registry_name_map(hass)
    assert result == {}


def test_build_registry_name_map_with_devices(hass: HomeAssistant) -> None:
    """Maps IEEE addresses to device names."""

    zha_entry = MockConfigEntry(
        domain=ZHA_DOMAIN, title="ZHA Entry", entry_id="zha_entry"
    )
    zha_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id="zha_entry",
        identifiers={(ZHA_DOMAIN, "00:11:22:33:44:55:66:77")},
        name="ZHA Bulb",
    )

    result = _build_registry_name_map(hass)
    assert result.get("00:11:22:33:44:55:66:77") == "ZHA Bulb"


def test_build_registry_name_map_name_by_user_priority(hass: HomeAssistant) -> None:
    """name_by_user takes priority over auto-generated name."""

    zha_entry2 = MockConfigEntry(
        domain=ZHA_DOMAIN, title="ZHA Entry 2", entry_id="zha_entry2"
    )
    zha_entry2.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    dev = device_registry.async_get_or_create(
        config_entry_id="zha_entry2",
        identifiers={(ZHA_DOMAIN, "AA:BB:CC:DD:EE:FF:00:11")},
        name="Auto Name",
    )
    device_registry.async_update_device(dev.id, name_by_user="User Name")

    result = _build_registry_name_map(hass)
    assert result.get("AA:BB:CC:DD:EE:FF:00:11") == "User Name"


def test_build_registry_name_map_error(hass: HomeAssistant) -> None:
    """Returns empty dict on AttributeError."""
    with patch(
        "homeassistant.components.connectivity_monitor.zha.dr.async_get",
        side_effect=AttributeError("boom"),
    ):
        result = _build_registry_name_map(hass)
    assert result == {}


# ──────────────────────────────────────────────────────────────────────────────
# async_get_zha_devices
# ──────────────────────────────────────────────────────────────────────────────


async def test_get_zha_devices_empty_no_gateway_no_registry(
    hass: HomeAssistant,
) -> None:
    """Returns empty list when no ZHA devices found anywhere."""
    hass.data.pop(ZHA_DOMAIN, None)
    devices = await async_get_zha_devices(hass)
    assert devices == []


async def test_get_zha_devices_from_gateway(hass: HomeAssistant) -> None:
    """Returns devices from ZHA gateway (primary path)."""
    mock_device = MagicMock()
    mock_device.is_coordinator = False
    mock_device.name = "Gateway Device"
    mock_device.model = "Model X"
    mock_device.manufacturer = "Mfr"
    mock_device.last_seen = 1700000000.0

    ieee = "00:11:22:33:44:55:66:77"
    mock_gateway = MagicMock()
    mock_gateway.gateway_proxy = None
    mock_gateway.gateway = None
    mock_gateway.devices = {ieee: mock_device}

    hass.data[ZHA_DOMAIN] = {"entry": mock_gateway}

    devices = await async_get_zha_devices(hass)

    assert len(devices) == 1
    assert devices[0]["ieee"] == ieee
    assert devices[0]["name"] == "Gateway Device"
    assert devices[0]["last_seen"] == 1700000000.0


async def test_get_zha_devices_skips_coordinator(hass: HomeAssistant) -> None:
    """Coordinator device is excluded from results."""
    mock_coordinator = MagicMock()
    mock_coordinator.is_coordinator = True

    mock_gateway = MagicMock()
    mock_gateway.gateway_proxy = None
    mock_gateway.gateway = None
    mock_gateway.devices = {"coordinator_ieee": mock_coordinator}

    hass.data[ZHA_DOMAIN] = {"entry": mock_gateway}

    devices = await async_get_zha_devices(hass)
    assert devices == []


async def test_get_zha_devices_registry_fallback(hass: HomeAssistant) -> None:
    """Falls back to device registry when gateway not found."""
    hass.data.pop(ZHA_DOMAIN, None)

    zha_fb_entry = MockConfigEntry(
        domain=ZHA_DOMAIN,
        title="ZHA Fallback Entry",
        entry_id="zha_fallback_entry",
    )
    zha_fb_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id="zha_fallback_entry",
        identifiers={(ZHA_DOMAIN, "AA:BB:CC:DD:EE:FF:11:22")},
        name="Registry ZHA Device",
        manufacturer="ZHA Corp",
        model="Z100",
    )

    devices = await async_get_zha_devices(hass)

    assert len(devices) == 1
    assert devices[0]["ieee"] == "AA:BB:CC:DD:EE:FF:11:22"
    assert devices[0]["name"] == "Registry ZHA Device"


async def test_get_zha_devices_registry_fallback_when_gateway_empty(
    hass: HomeAssistant,
) -> None:
    """Falls back to registry when gateway returns no devices."""
    mock_gateway = MagicMock()
    mock_gateway.gateway_proxy = None
    mock_gateway.gateway = None
    mock_gateway.devices = {}  # Empty — triggers fallback

    hass.data[ZHA_DOMAIN] = {"entry": mock_gateway}

    zha_empty_entry = MockConfigEntry(
        domain=ZHA_DOMAIN,
        title="ZHA Empty Entry",
        entry_id="zha_entry_empty",
    )
    zha_empty_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id="zha_entry_empty",
        identifiers={(ZHA_DOMAIN, "BB:CC:DD:EE:FF:00:11:22")},
        name="Fallback Device",
    )

    devices = await async_get_zha_devices(hass)

    assert len(devices) == 1
    assert devices[0]["ieee"] == "BB:CC:DD:EE:FF:00:11:22"


async def test_get_zha_devices_gateway_attribute_error(hass: HomeAssistant) -> None:
    """Falls back to registry when gateway enumeration raises AttributeError."""
    mock_gateway = MagicMock()
    type(mock_gateway).devices = property(
        lambda self: (_ for _ in ()).throw(AttributeError("explode"))
    )
    hass.data[ZHA_DOMAIN] = {"entry": mock_gateway}

    zha_err_entry = MockConfigEntry(
        domain=ZHA_DOMAIN,
        title="ZHA Err Entry",
        entry_id="zha_err_entry",
    )
    zha_err_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id="zha_err_entry",
        identifiers={(ZHA_DOMAIN, "CC:DD:EE:FF:00:11:22:33")},
        name="Error Fallback Device",
    )

    devices = await async_get_zha_devices(hass)
    assert any(d["ieee"] == "CC:DD:EE:FF:00:11:22:33" for d in devices)


async def test_get_zha_devices_uses_registry_name_over_zigpy(
    hass: HomeAssistant,
) -> None:
    """Registry name takes priority over zigpy device.name."""
    ieee = "11:22:33:44:55:66:77:88"
    mock_device = MagicMock()
    mock_device.is_coordinator = False
    mock_device.name = "Zigpy Name"
    mock_device.model = None
    mock_device.manufacturer = None
    mock_device.last_seen = None

    mock_gateway = MagicMock()
    mock_gateway.gateway_proxy = None
    mock_gateway.gateway = None
    mock_gateway.devices = {ieee: mock_device}
    hass.data[ZHA_DOMAIN] = {"entry": mock_gateway}

    # Also create a device registry entry with a different name
    zha_name_entry = MockConfigEntry(
        domain=ZHA_DOMAIN,
        title="ZHA Name Prio",
        entry_id="zha_name_prio",
    )
    zha_name_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id="zha_name_prio",
        identifiers={(ZHA_DOMAIN, ieee)},
        name="Registry Name",
    )

    devices = await async_get_zha_devices(hass)

    assert len(devices) == 1
    assert devices[0]["name"] == "Registry Name"


# ──────────────────────────────────────────────────────────────────────────────
# async_get_zha_device_last_seen
# ──────────────────────────────────────────────────────────────────────────────


async def test_get_zha_device_last_seen_from_gateway(hass: HomeAssistant) -> None:
    """Returns last_seen from gateway for the matching IEEE."""
    ieee = "00:AA:BB:CC:DD:EE:FF:01"
    mock_device = MagicMock()
    mock_device.last_seen = 1700005000.0

    mock_gateway = MagicMock()
    mock_gateway.gateway_proxy = None
    mock_gateway.gateway = None
    mock_gateway.devices = {ieee: mock_device}
    hass.data[ZHA_DOMAIN] = {"entry": mock_gateway}

    result = await async_get_zha_device_last_seen(hass, ieee)
    assert result == 1700005000.0


async def test_get_zha_device_last_seen_not_in_gateway(hass: HomeAssistant) -> None:
    """Falls back to registry when IEEE not in gateway."""
    ieee = "00:AA:BB:CC:DD:EE:FF:02"

    mock_gateway = MagicMock()
    mock_gateway.gateway_proxy = None
    mock_gateway.gateway = None
    mock_gateway.devices = {}
    hass.data[ZHA_DOMAIN] = {"entry": mock_gateway}

    # Register device in registry
    zha_ls_entry = MockConfigEntry(
        domain=ZHA_DOMAIN, title="ZHA LS Entry", entry_id="zha_ls"
    )
    zha_ls_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id="zha_ls",
        identifiers={(ZHA_DOMAIN, ieee)},
        name="LS Device",
    )

    result = await async_get_zha_device_last_seen(hass, ieee)
    # Device registry usually returns None for last_seen unless set
    assert result is None


async def test_get_zha_device_last_seen_no_gateway(hass: HomeAssistant) -> None:
    """Returns None when no gateway and IEEE not in registry."""
    hass.data.pop(ZHA_DOMAIN, None)
    result = await async_get_zha_device_last_seen(hass, "FF:EE:DD:CC:BB:AA:99:88")
    assert result is None


async def test_get_zha_device_last_seen_gateway_error(hass: HomeAssistant) -> None:
    """Falls back to registry when gateway raises AttributeError."""
    ieee = "00:AA:BB:CC:DD:EE:FF:03"

    mock_gateway = MagicMock()
    type(mock_gateway).devices = property(
        lambda self: (_ for _ in ()).throw(AttributeError("boom"))
    )
    hass.data[ZHA_DOMAIN] = {"entry": mock_gateway}

    # Result is None since device is also not in registry
    result = await async_get_zha_device_last_seen(hass, ieee)
    assert result is None


async def test_get_zha_device_last_seen_registry_error(hass: HomeAssistant) -> None:
    """Returns None when both gateway and registry raise errors."""
    ieee = "00:AA:BB:CC:DD:EE:FF:04"
    hass.data.pop(ZHA_DOMAIN, None)

    with patch(
        "homeassistant.components.connectivity_monitor.zha.dr.async_get",
        side_effect=AttributeError("registry boom"),
    ):
        result = await async_get_zha_device_last_seen(hass, ieee)

    assert result is None
