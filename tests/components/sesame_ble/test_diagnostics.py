"""Tests for the sesame_ble diagnostics module."""

from unittest.mock import MagicMock, patch

from homeassistant.components.sesame_ble.const import (
    CONF_DEVICE_UUID,
    CONF_SECRET_KEY,
    DOMAIN,
)
from homeassistant.components.sesame_ble.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery_flow import DiscoveryKey

from tests.common import MockConfigEntry

_ENTRY_DATA = {
    "mac_address": "AA:BB:CC:DD:EE:FF",
    CONF_SECRET_KEY: "deadbeefdeadbeefdeadbeefdeadbeef",
    CONF_DEVICE_UUID: "12345678-1234-5678-1234-567812345678",
    CONF_MODEL: "SESAME5",
}

_REDACT_KEYS = {CONF_SECRET_KEY, "mac_address", CONF_DEVICE_UUID}


def _make_mock_wrapper(
    *,
    connected: bool = True,
    authenticated: bool = True,
    fw_version: str = "1.2.3",
) -> MagicMock:
    """Build a minimal SesameDeviceWrapper mock."""
    device = MagicMock()
    device.is_connected = connected
    device.is_logged_in = authenticated

    wrapper = MagicMock()
    wrapper.mac_address = "AA:BB:CC:DD:EE:FF"
    wrapper.model_name = "SESAME5"
    wrapper.device = device
    wrapper.fw_version = fw_version
    return wrapper


async def test_diagnostics_redacts_secrets(hass: HomeAssistant) -> None:
    """Diagnostics output must not expose secret_key, mac_address, device_uuid, unique_id, title, or discovery_keys."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Sesame 5 (ee:ff)",
        data=_ENTRY_DATA,
        unique_id="aa:bb:cc:dd:ee:ff",
        discovery_keys={
            "bluetooth": (
                DiscoveryKey(
                    domain="bluetooth",
                    key="aa:bb:cc:dd:ee:ff",
                    version=1,
                ),
            )
        },
    )
    entry.add_to_hass(hass)
    entry.runtime_data = _make_mock_wrapper()

    with patch(
        "homeassistant.components.bluetooth.async_last_service_info",
        return_value=None,
    ):
        result = await async_get_config_entry_diagnostics(hass, entry)

    entry_data = result["entry"].get("data", {})
    for key in _REDACT_KEYS:
        assert entry_data.get(key) == "**REDACTED**", (
            f"Expected data[{key!r}] to be redacted, got {entry_data.get(key)!r}"
        )
    assert result["entry"].get("unique_id") == "**REDACTED**"
    assert result["entry"].get("title") == "**REDACTED**"
    assert result["entry"].get("discovery_keys") == "**REDACTED**"


async def test_diagnostics_runtime_state(hass: HomeAssistant) -> None:
    """Runtime section reflects the wrapper state correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_ENTRY_DATA,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)
    entry.runtime_data = _make_mock_wrapper(
        connected=True,
        authenticated=True,
        fw_version="3.0.0",
    )

    with patch(
        "homeassistant.components.bluetooth.async_last_service_info",
        return_value=None,
    ):
        result = await async_get_config_entry_diagnostics(hass, entry)

    runtime = result["runtime"]
    assert runtime["connected"] is True
    assert runtime["authenticated"] is True
    assert runtime["firmware_version"] == "3.0.0"
    assert runtime["model"] == "SESAME5"


async def test_diagnostics_no_runtime_data(hass: HomeAssistant) -> None:
    """Diagnostics must not raise when the entry has no runtime_data yet."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_ENTRY_DATA,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)
    entry.runtime_data = None

    with patch(
        "homeassistant.components.bluetooth.async_last_service_info",
        return_value=None,
    ):
        result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["runtime"] == {}
    assert result["bluetooth"] is None


async def test_diagnostics_with_bluetooth_service_info(hass: HomeAssistant) -> None:
    """Test diagnostics with bluetooth service info present redacts address and manufacturer data."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_ENTRY_DATA,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)
    entry.runtime_data = _make_mock_wrapper()

    mock_service_info = MagicMock()
    mock_service_info.as_dict.return_value = {
        "address": "AA:BB:CC:DD:EE:FF",
        "rssi": -65,
        "manufacturer_data": {0x055A: b"test"},
        "device": {"address": "AA:BB:CC:DD:EE:FF", "name": "Sesame Lock"},
        "source": "hci0",
    }

    with patch(
        "homeassistant.components.bluetooth.async_last_service_info",
        return_value=mock_service_info,
    ):
        result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["bluetooth"] == {
        "address": "**REDACTED**",
        "rssi": -65,
        "manufacturer_data": "**REDACTED**",
        "device": "**REDACTED**",
        "source": "**REDACTED**",
    }
