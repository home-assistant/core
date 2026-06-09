"""Tests for the Mitsubishi Comfort config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from mitsubishi_comfort.exceptions import AuthenticationError, DeviceConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.mitsubishi_comfort.const import (
    CONF_ADDRESSES,
    CONF_CREDENTIALS,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import MOCK_MAC, MOCK_PASSWORD, MOCK_SERIAL, MOCK_USERNAME

from tests.common import MockConfigEntry, get_schema_suggested_value


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry and async_unload_entry."""
    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.async_setup_entry",
            return_value=True,
        ) as mock,
        patch(
            "homeassistant.components.mitsubishi_comfort.async_unload_entry",
            return_value=True,
        ),
    ):
        yield mock


async def test_user_step_success(
    hass: HomeAssistant,
    mock_cloud_account: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test successful config flow shows form then creates entry."""
    # First call with no input shows form
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit credentials creates entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Mitsubishi Comfort ({MOCK_USERNAME})"
    # Per-device credentials from discovery are persisted so setup can skip the
    # rate-limited Socket.IO fetch.
    assert result["data"] == {
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
        CONF_CREDENTIALS: {
            MOCK_SERIAL: {
                "password": "dGVzdHBhc3M=",
                "crypto_serial": "0102030405060708090a",
                "mac": MOCK_MAC,
            }
        },
    }
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "discover_return", "expected_error"),
    [
        (AuthenticationError("bad creds"), None, "invalid_auth"),
        (DeviceConnectionError("nope"), None, "cannot_connect"),
        (RuntimeError("Unexpected"), None, "unknown"),
        (None, {}, "no_devices"),
    ],
    ids=["invalid_auth", "cannot_connect", "unknown_error", "no_devices"],
)
async def test_user_step_errors(
    hass: HomeAssistant,
    mock_cloud_account: AsyncMock,
    side_effect: Exception | None,
    discover_return: dict | None,
    expected_error: str,
) -> None:
    """Test config flow error handling."""
    if side_effect:
        mock_cloud_account.login.side_effect = side_effect
    elif discover_return is not None:
        mock_cloud_account.discover_devices.return_value = discover_return

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_user_step_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
) -> None:
    """Test that duplicate config is rejected."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _dhcp_info(ip: str, mac: str = MOCK_MAC) -> DhcpServiceInfo:
    """Build DHCP discovery info (DHCP reports MACs without separators)."""
    return DhcpServiceInfo(
        ip=ip, hostname="kumo", macaddress=mac.replace(":", "").lower()
    )


def _register_device(
    device_registry: dr.DeviceRegistry, entry: MockConfigEntry, mac: str = MOCK_MAC
) -> None:
    """Register a device with a MAC connection, as setup does."""
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, MOCK_SERIAL)},
        connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac))},
    )


async def test_dhcp_updates_address_and_reloads(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery records a new IP for a registered device and reloads."""
    mock_config_entry.add_to_hass(hass)
    _register_device(device_registry, mock_config_entry)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_schedule_reload"
    ) as mock_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=_dhcp_info("192.168.1.250"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_ADDRESSES][dr.format_mac(MOCK_MAC)] == (
        "192.168.1.250"
    )
    mock_reload.assert_called_once_with(mock_config_entry.entry_id)


async def test_dhcp_same_address_does_not_reload(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery of an unchanged IP does not trigger a reload."""
    mock_config_entry.add_to_hass(hass)
    _register_device(device_registry, mock_config_entry)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_schedule_reload"
    ) as mock_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=_dhcp_info("192.168.1.100"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_reload.assert_not_called()


async def test_dhcp_unregistered_device_ignored(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery of a MAC with no registered device changes nothing."""
    mock_config_entry.add_to_hass(hass)
    _register_device(device_registry, mock_config_entry)
    original = dict(mock_config_entry.data[CONF_ADDRESSES])

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_schedule_reload"
    ) as mock_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=_dhcp_info("192.168.1.251", mac="99:99:99:99:99:99"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_ADDRESSES] == original
    mock_reload.assert_not_called()


async def test_dhcp_device_without_current_entry_aborts(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test DHCP aborts when the registered device has no current owning entry.

    The device exists in the registry but belongs only to an ignored entry, so
    there is nothing to update.
    """
    ignored_entry = MockConfigEntry(
        domain=DOMAIN, source=config_entries.SOURCE_IGNORE, unique_id="ignored"
    )
    ignored_entry.add_to_hass(hass)
    _register_device(device_registry, ignored_entry)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_schedule_reload"
    ) as mock_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=_dhcp_info("192.168.1.253"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_reload.assert_not_called()


async def test_dhcp_no_account_aborts(hass: HomeAssistant) -> None:
    """Test DHCP discovery with no configured account aborts without a flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=_dhcp_info("192.168.1.252"),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


class TestOptionsFlow:
    """Options flow tests.

    The per-device IP fields are keyed by formatted MAC (dynamic), so they have
    no static label in strings.json; ignore that in the translation check.
    """

    @pytest.fixture(autouse=True)
    def ignore_missing_translations(self) -> list[str]:
        """Allow the dynamic, MAC-keyed device IP fields."""
        return [
            "component.mitsubishi_comfort.options.step.init.data.",
            "component.mitsubishi_comfort.options.step.init.data_description.",
        ]

    async def test_sets_device_ip(
        self,
        hass: HomeAssistant,
        device_registry: dr.DeviceRegistry,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test the options flow stores a manually entered device IP."""
        mock_config_entry.add_to_hass(hass)
        _register_device(device_registry, mock_config_entry)

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {dr.format_mac(MOCK_MAC): "192.168.1.50"}
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert mock_config_entry.data[CONF_ADDRESSES][dr.format_mac(MOCK_MAC)] == (
            "192.168.1.50"
        )

    async def test_clears_device_ip(
        self,
        hass: HomeAssistant,
        device_registry: dr.DeviceRegistry,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test submitting a blank field removes the device's stored IP."""
        mock_config_entry.add_to_hass(hass)
        _register_device(device_registry, mock_config_entry)
        # The fixture entry starts with a stored address for the device.
        assert dr.format_mac(MOCK_MAC) in mock_config_entry.data[CONF_ADDRESSES]

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {dr.format_mac(MOCK_MAC): ""}
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert dr.format_mac(MOCK_MAC) not in mock_config_entry.data[CONF_ADDRESSES]

    async def test_rejects_invalid_ip(
        self,
        hass: HomeAssistant,
        device_registry: dr.DeviceRegistry,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test the options flow rejects a non-IP entry."""
        mock_config_entry.add_to_hass(hass)
        _register_device(device_registry, mock_config_entry)

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {dr.format_mac(MOCK_MAC): "not-an-ip"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_ip"}
        # The submitted value is preserved so the user does not have to re-enter.
        schema = result["data_schema"].schema
        assert (
            get_schema_suggested_value(schema, dr.format_mac(MOCK_MAC)) == "not-an-ip"
        )


async def test_options_flow_aborts_without_devices(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the options flow aborts when no devices are registered yet."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices"
