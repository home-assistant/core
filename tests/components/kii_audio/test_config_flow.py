"""Tests for the Kii Audio config flow."""

from collections.abc import Callable, Generator
from ipaddress import ip_address
import json
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.kii_audio.config_flow import (
    CannotConnect,
    _async_get_system_info,
)
from homeassistant.components.kii_audio.const import CONF_SYSTEM_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import SYSTEM_ID

from tests.common import MockConfigEntry

HOST = "192.0.2.1"
DEVICE_ID = "device-id"


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.kii_audio.async_setup_entry",
        new=AsyncMock(return_value=True),
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(autouse=True)
def mock_get_system_info() -> Generator[AsyncMock]:
    """Mock fetching Kii Audio system info for manual setup."""
    with patch(
        "homeassistant.components.kii_audio.config_flow._async_get_system_info",
        new=AsyncMock(return_value={"systemId": SYSTEM_ID, "systemName": "Kii System"}),
    ) as mock_get_info:
        yield mock_get_info


def _zeroconf_info(data: dict[str, object]) -> ZeroconfServiceInfo:
    """Return Kii Audio zeroconf discovery info."""
    return ZeroconfServiceInfo(
        ip_address=ip_address(HOST),
        ip_addresses=[ip_address(HOST)],
        hostname="kii.local.",
        name="Kii._kii._tcp.local.",
        port=80,
        properties={"data": json.dumps(data)},
        type="_kii._tcp.local.",
    )


def _zeroconf_info_with_raw_data(data: object) -> ZeroconfServiceInfo:
    """Return Kii Audio zeroconf discovery info with raw data bytes."""
    return ZeroconfServiceInfo(
        ip_address=ip_address(HOST),
        ip_addresses=[ip_address(HOST)],
        hostname="kii.local.",
        name="Kii._kii._tcp.local.",
        port=80,
        properties={"data": data},
        type="_kii._tcp.local.",
    )


def _zeroconf_info_without_data() -> ZeroconfServiceInfo:
    """Return Kii Audio zeroconf discovery info without data."""
    return ZeroconfServiceInfo(
        ip_address=ip_address(HOST),
        ip_addresses=[ip_address(HOST)],
        hostname="kii.local.",
        name="Kii._kii._tcp.local.",
        port=80,
        properties={},
        type="_kii._tcp.local.",
    )


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the manual config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_SYSTEM_ID: SYSTEM_ID},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kii Audio"
    assert result["data"] == {CONF_HOST: HOST, CONF_SYSTEM_ID: SYSTEM_ID}
    assert result["result"].unique_id == SYSTEM_ID


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test the manual flow aborts for an existing system."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.99", CONF_SYSTEM_ID: SYSTEM_ID},
        unique_id=SYSTEM_ID,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_SYSTEM_ID: SYSTEM_ID},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test zeroconf discovery creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            {
                "deviceId": DEVICE_ID,
                "systemId": SYSTEM_ID,
                "version": 2,
                "ip": HOST,
            }
        ),
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kii Audio"
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_DEVICE_ID: DEVICE_ID,
        CONF_SYSTEM_ID: SYSTEM_ID,
    }
    assert result["result"].unique_id == SYSTEM_ID


async def test_zeroconf_flow_rejects_legacy_backend(hass: HomeAssistant) -> None:
    """Test zeroconf discovery aborts for legacy backends."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            {
                "deviceId": DEVICE_ID,
                "systemId": SYSTEM_ID,
                "version": 1,
            }
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_backend"


async def test_zeroconf_flow_rejects_invalid_bytes(hass: HomeAssistant) -> None:
    """Test zeroconf discovery aborts when bytes are not valid JSON."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info_with_raw_data(b"\xff\xfe"),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_zeroconf_flow_rejects_invalid_json(hass: HomeAssistant) -> None:
    """Test zeroconf discovery aborts when data is invalid JSON."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info_with_raw_data("{"),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_zeroconf_flow_rejects_missing_data(hass: HomeAssistant) -> None:
    """Test zeroconf discovery aborts without a data property."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info_without_data(),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_zeroconf_flow_rejects_missing_ids(hass: HomeAssistant) -> None:
    """Test zeroconf discovery aborts without required IDs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info({"version": 2}),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_zeroconf_flow_uses_discovery_host_when_payload_ip_is_empty(
    hass: HomeAssistant,
) -> None:
    """Test zeroconf discovery falls back to discovery host for empty IP data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            {
                "deviceId": DEVICE_ID,
                "systemId": SYSTEM_ID,
                "version": 2,
                "ip": "",
            }
        ),
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == HOST


async def test_zeroconf_flow_already_configured(hass: HomeAssistant) -> None:
    """Test zeroconf discovery aborts for an existing system."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.99", CONF_SYSTEM_ID: SYSTEM_ID},
        unique_id=SYSTEM_ID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_zeroconf_info(
            {
                "deviceId": DEVICE_ID,
                "systemId": SYSTEM_ID,
                "version": 2,
                "ip": HOST,
            }
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == HOST


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_get_system_info: AsyncMock
) -> None:
    """Test the manual flow handles connection failures."""
    mock_get_system_info.side_effect = CannotConnect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_SYSTEM_ID: SYSTEM_ID},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unknown_error(
    hass: HomeAssistant, mock_get_system_info: AsyncMock
) -> None:
    """Test the manual flow handles unexpected validation failures."""
    mock_get_system_info.side_effect = RuntimeError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_SYSTEM_ID: SYSTEM_ID},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_rejects_mismatched_system_id(
    hass: HomeAssistant, mock_get_system_info: AsyncMock
) -> None:
    """Test the manual flow rejects a mismatched system ID."""
    mock_get_system_info.return_value = {"systemId": "other-system-id"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_SYSTEM_ID: SYSTEM_ID},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_system_id"}


async def test_async_get_system_info(hass: HomeAssistant) -> None:
    """Test fetching system information starts and stops the validation client."""
    client = Mock(start=AsyncMock(), stop=AsyncMock())

    def add_listener(listener: Callable[[str, dict[str, Any]], None]) -> None:
        listener("pushSystemInfo", {"systemId": SYSTEM_ID})

    client.add_listener.side_effect = add_listener

    with patch(
        "homeassistant.components.kii_audio.config_flow.KiiAudioClient",
        return_value=client,
    ):
        assert await _async_get_system_info(hass, HOST) == {"systemId": SYSTEM_ID}

    client.start.assert_awaited_once_with()
    client.stop.assert_awaited_once_with()


async def test_async_get_system_info_timeout(hass: HomeAssistant) -> None:
    """Test fetching system information times out when the system does not respond."""
    client = Mock(start=AsyncMock(), stop=AsyncMock())

    class TimeoutContext:
        async def __aenter__(self) -> None:
            raise TimeoutError

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            traceback: object,
        ) -> None:
            return None

    with (
        patch(
            "homeassistant.components.kii_audio.config_flow.KiiAudioClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.kii_audio.config_flow.asyncio.timeout",
            return_value=TimeoutContext(),
        ),
        pytest.raises(CannotConnect),
    ):
        await _async_get_system_info(hass, HOST)

    client.start.assert_awaited_once_with()
    client.stop.assert_awaited_once_with()
