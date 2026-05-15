"""Tests for the iTach IP2IR config flow."""

from typing import cast
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.itachip2ir.config_flow import (
    CONF_DEVICE_ID,
    CONF_IR_CONNECTOR_MODES,
    CONF_IR_ENABLED_PORTS,
    CONF_IR_MODULE,
    CONF_IR_PORTS,
    CannotConnect,
    CannotIdentify,
    InvalidDeviceId,
    NoIrPorts,
    _get_discovery,
    _identify_device,
    _normalize_device_id,
    _validate_device,
    _validate_discovered_input,
    _validate_manual_input,
)
from homeassistant.components.itachip2ir.const import DISCOVERY, DOMAIN
from homeassistant.components.itachip2ir.discovery import ItachDiscovery
from homeassistant.components.itachip2ir.pyitach import DEFAULT_PORT, ItachError
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry

HOST = "192.168.1.211"
PORT = DEFAULT_PORT
NEW_HOST = "192.168.1.250"
NEW_PORT = 5998
UNIQUE_ID = "GlobalCache_000C1E123456"
MAC = "000C1E123456"
DHCP_MAC = "000c1e123456"


def _dhcp_info(
    *,
    host: str = HOST,
    macaddress: str = DHCP_MAC,
    hostname: str = "itachip2ir",
) -> DhcpServiceInfo:
    """Return fake DHCP discovery info."""
    return DhcpServiceInfo(
        ip=host,
        hostname=hostname,
        macaddress=macaddress,
    )


class FakeClient:
    """Fake iTach client."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        ir_module: int = 1,
        ir_ports: int = 3,
        connector_modes: dict[int, str] | None = None,
        module_error: Exception | None = None,
        modes_error: Exception | None = None,
    ) -> None:
        """Initialize fake client."""
        self.host = host
        self.port = port
        self.ir_module = ir_module
        self.ir_ports = ir_ports
        self.connector_modes = (
            {1: "IR", 2: "SENSOR", 3: "IR_BLASTER"}
            if connector_modes is None
            else connector_modes
        )
        self.module_error = module_error
        self.modes_error = modes_error
        self.close = AsyncMock()

    async def async_get_ir_module(self) -> tuple[int, int]:
        """Return fake IR module information."""
        if self.module_error is not None:
            raise self.module_error

        return self.ir_module, self.ir_ports

    async def async_get_ir_connector_modes(
        self,
        module: int,
        ports: int,
    ) -> dict[int, str]:
        """Return fake IR connector modes."""
        if self.modes_error is not None:
            raise self.modes_error

        return self.connector_modes


def _patch_client(
    monkeypatch,
    *,
    ir_module: int = 1,
    ir_ports: int = 3,
    connector_modes: dict[int, str] | None = None,
    module_error: Exception | None = None,
    modes_error: Exception | None = None,
) -> None:
    """Patch config flow ItachClient."""

    class PatchedFakeClient(FakeClient):
        def __init__(self, host: str, port: int) -> None:
            super().__init__(
                host,
                port,
                ir_module=ir_module,
                ir_ports=ir_ports,
                connector_modes=connector_modes,
                module_error=module_error,
                modes_error=modes_error,
            )

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow.ItachClient",
        PatchedFakeClient,
    )


def _make_entry(
    *,
    data: dict | None = None,
    options: dict | None = None,
    unique_id: str = UNIQUE_ID,
) -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        data=data
        or {
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_IR_MODULE: 1,
            CONF_IR_PORTS: 3,
            CONF_IR_ENABLED_PORTS: [1, 3],
            CONF_IR_CONNECTOR_MODES: {
                "1": "IR",
                "2": "SENSOR",
                "3": "IR_BLASTER",
            },
        },
        options=options or {},
        title="iTach IP2IR",
    )


def test_normalize_device_id_accepts_plain_mac() -> None:
    """Test normalizing a plain MAC address."""
    assert _normalize_device_id(MAC) == UNIQUE_ID


def test_normalize_device_id_accepts_colon_mac() -> None:
    """Test normalizing a colon-separated MAC address."""
    assert _normalize_device_id("00:0c:1e:12:34:56") == UNIQUE_ID


def test_normalize_device_id_accepts_dash_mac() -> None:
    """Test normalizing a dash-separated MAC address."""
    assert _normalize_device_id("00-0c-1e-12-34-56") == UNIQUE_ID


def test_normalize_device_id_accepts_globalcache_prefix() -> None:
    """Test normalizing a GlobalCache-prefixed device ID."""
    assert _normalize_device_id("GlobalCache_000c1e123456") == UNIQUE_ID


def test_normalize_device_id_empty_returns_none() -> None:
    """Test empty device ID returns None."""
    assert _normalize_device_id(None) is None
    assert _normalize_device_id("") is None
    assert _normalize_device_id("   ") is None


@pytest.mark.parametrize(
    "value",
    [
        "not-a-mac",
        "000C1E12345",
        "000C1E1234567",
        "GG0C1E123456",
        "000000000000",
    ],
)
def test_normalize_device_id_rejects_invalid_values(value: str) -> None:
    """Test invalid MAC values are rejected."""
    with pytest.raises(InvalidDeviceId):
        _normalize_device_id(value)


async def test_validate_device_filters_ir_output_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test device validation returns only IR output ports."""
    _patch_client(
        monkeypatch,
        connector_modes={
            1: "IR",
            2: "SENSOR",
            3: "IR_BLASTER",
        },
    )

    result = await _validate_device(HOST, PORT)

    assert result == {
        CONF_IR_MODULE: 1,
        CONF_IR_PORTS: 3,
        CONF_IR_CONNECTOR_MODES: {
            "1": "IR",
            "2": "SENSOR",
            "3": "IR_BLASTER",
        },
        CONF_IR_ENABLED_PORTS: [1, 3],
    }


async def test_validate_device_get_ir_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test device validation falls back when get_IR returns no modes."""
    _patch_client(
        monkeypatch,
        ir_module=1,
        ir_ports=3,
        connector_modes={},
    )

    result = await _validate_device(HOST, PORT)

    assert result == {
        CONF_IR_MODULE: 1,
        CONF_IR_PORTS: 3,
        CONF_IR_CONNECTOR_MODES: {
            "1": "UNKNOWN",
            "2": "UNKNOWN",
            "3": "UNKNOWN",
        },
        CONF_IR_ENABLED_PORTS: [1, 2, 3],
    }


async def test_validate_device_no_output_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test device validation fails when no connector is an IR output."""
    _patch_client(
        monkeypatch,
        connector_modes={
            1: "SENSOR",
            2: "SENSOR",
            3: "SENSOR",
        },
    )

    with pytest.raises(NoIrPorts):
        await _validate_device(HOST, PORT)


async def test_user_flow_success_with_manual_mac(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test manual user flow succeeds with a provided MAC address."""
    _patch_client(monkeypatch)

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow.async_wait_for_device_id",
        AsyncMock(return_value=None),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_DEVICE_ID: MAC,
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == f"iTach IP2IR ({HOST})"
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_IR_MODULE: 1,
        CONF_IR_PORTS: 3,
        CONF_IR_ENABLED_PORTS: [1, 3],
        CONF_IR_CONNECTOR_MODES: {
            "1": "IR",
            "2": "SENSOR",
            "3": "IR_BLASTER",
        },
    }


async def test_user_flow_invalid_mac(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test manual user flow shows invalid_device_id for invalid MAC."""
    _patch_client(monkeypatch)

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow.async_wait_for_device_id",
        AsyncMock(return_value=None),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_DEVICE_ID: "not-a-mac",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {
        CONF_DEVICE_ID: "invalid_device_id",
    }


async def test_user_flow_cannot_identify_without_discovery_or_mac(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test manual user flow fails when no discovery ID or MAC is available."""
    _patch_client(monkeypatch)

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow.async_wait_for_device_id",
        AsyncMock(return_value=None),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {
        "base": "cannot_identify",
    }


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test manual user flow shows cannot_connect when validation fails."""
    _patch_client(
        monkeypatch,
        module_error=ItachError("cannot connect"),
    )

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow.async_wait_for_device_id",
        AsyncMock(return_value=UNIQUE_ID),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_DEVICE_ID: MAC,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {
        "base": "cannot_connect",
    }


async def test_user_flow_no_ir_ports(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test user flow shows no_ir_ports when no usable IR outputs."""
    _patch_client(
        monkeypatch,
        connector_modes={
            1: "SENSOR",
            2: "SENSOR",
            3: "SENSOR",
        },
    )

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow.async_wait_for_device_id",
        AsyncMock(return_value=UNIQUE_ID),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_DEVICE_ID: MAC,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_ir_ports"}


async def test_user_flow_duplicate_abort(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test manual user flow aborts for an already configured device."""
    _patch_client(monkeypatch)

    entry = _make_entry()
    entry.add_to_hass(hass)

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow.async_wait_for_device_id",
        AsyncMock(return_value=UNIQUE_ID),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_DEVICE_ID: MAC,
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_dhcp_flow_success(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test DHCP discovery confirms and creates an entry."""
    _patch_client(monkeypatch)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=_dhcp_info(),
    )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm_discovery"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == f"iTach IP2IR ({HOST})"
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_IR_MODULE: 1,
        CONF_IR_PORTS: 3,
        CONF_IR_ENABLED_PORTS: [1, 3],
        CONF_IR_CONNECTOR_MODES: {
            "1": "IR",
            "2": "SENSOR",
            "3": "IR_BLASTER",
        },
    }


async def test_dhcp_flow_updates_existing_host(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test DHCP discovery updates an existing entry host by unique ID."""
    _patch_client(monkeypatch)

    entry = _make_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=_dhcp_info(host=NEW_HOST),
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == NEW_HOST


async def test_dhcp_flow_invalid_mac_aborts(hass: HomeAssistant) -> None:
    """Test DHCP discovery aborts when the MAC address cannot be normalized."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=_dhcp_info(macaddress="not-a-mac"),
    )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_identify"


async def test_dhcp_flow_cannot_connect_aborts(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test DHCP discovery aborts when validation cannot connect."""
    _patch_client(
        monkeypatch,
        module_error=ItachError("cannot connect"),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=_dhcp_info(),
    )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_dhcp_flow_no_ir_ports_aborts(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test DHCP discovery aborts for non-IR Global Caché devices."""
    _patch_client(monkeypatch, connector_modes={1: "SENSOR", 2: "SENSOR", 3: "SENSOR"})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=_dhcp_info(),
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_ir_ports"


async def test_discovery_flow_success(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test discovery flow confirms and creates an entry."""
    _patch_client(monkeypatch)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DISCOVERY},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            "unique_id": UNIQUE_ID,
            "model": "iTachIP2IR",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm_discovery"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == f"iTach IP2IR ({HOST})"
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_IR_MODULE: 1,
        CONF_IR_PORTS: 3,
        CONF_IR_ENABLED_PORTS: [1, 3],
        CONF_IR_CONNECTOR_MODES: {
            "1": "IR",
            "2": "SENSOR",
            "3": "IR_BLASTER",
        },
    }


async def test_discovery_flow_duplicate_abort(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test discovery flow aborts for an already configured device."""
    _patch_client(monkeypatch)

    entry = _make_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DISCOVERY},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            "unique_id": UNIQUE_ID,
            "model": "iTachIP2IR",
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_discovery_confirm_cannot_connect(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test discovered device confirmation shows cannot_connect on validation error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DISCOVERY},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            "unique_id": UNIQUE_ID,
            "model": "iTachIP2IR",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm_discovery"

    _patch_client(
        monkeypatch,
        module_error=ItachError("cannot connect"),
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm_discovery"
    assert result["errors"] == {
        "base": "cannot_connect",
    }


async def test_discovery_confirm_no_ir_ports(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test discovery confirm shows no_ir_ports when no usable IR outputs."""
    _patch_client(
        monkeypatch,
        connector_modes={
            1: "SENSOR",
            2: "SENSOR",
            3: "SENSOR",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DISCOVERY},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            "unique_id": UNIQUE_ID,
            "model": "iTachIP2IR",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm_discovery"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm_discovery"
    assert result["errors"] == {"base": "no_ir_ports"}


async def test_reconfigure_flow_success(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test reconfigure flow updates host, port, and IR capability data."""
    _patch_client(
        monkeypatch,
        connector_modes={
            1: "IR",
            2: "IR",
            3: "SENSOR",
        },
    )

    entry = _make_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
        data=None,
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: NEW_HOST,
            CONF_PORT: NEW_PORT,
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"

    assert entry.data[CONF_HOST] == NEW_HOST
    assert entry.data[CONF_PORT] == NEW_PORT
    assert entry.data[CONF_IR_MODULE] == 1
    assert entry.data[CONF_IR_PORTS] == 3
    assert entry.data[CONF_IR_ENABLED_PORTS] == [1, 2]
    assert entry.data[CONF_IR_CONNECTOR_MODES] == {
        "1": "IR",
        "2": "IR",
        "3": "SENSOR",
    }


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test reconfigure flow keeps form open when validation fails."""
    _patch_client(
        monkeypatch,
        module_error=ItachError("cannot connect"),
    )

    entry = _make_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
        data=None,
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: NEW_HOST,
            CONF_PORT: NEW_PORT,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {
        "base": "cannot_connect",
    }

    assert entry.data[CONF_HOST] == HOST
    assert entry.data[CONF_PORT] == PORT


async def test_reconfigure_flow_no_ir_ports(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test reconfigure shows no_ir_ports when no usable IR outputs."""
    _patch_client(
        monkeypatch,
        connector_modes={
            1: "SENSOR",
            2: "SENSOR",
            3: "SENSOR",
        },
    )

    entry = _make_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
        data=None,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: NEW_HOST,
            CONF_PORT: NEW_PORT,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "no_ir_ports"}


async def test_reconfigure_flow_uses_existing_defaults(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test reconfigure form defaults come from existing entry data."""
    _patch_client(monkeypatch)

    entry = _make_entry(
        data={
            CONF_HOST: NEW_HOST,
            CONF_PORT: NEW_PORT,
            CONF_IR_MODULE: 1,
            CONF_IR_PORTS: 3,
            CONF_IR_ENABLED_PORTS: [1, 3],
            CONF_IR_CONNECTOR_MODES: {
                "1": "IR",
                "2": "SENSOR",
                "3": "IR_BLASTER",
            },
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
        data=None,
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"

    data_schema = result["data_schema"]
    assert data_schema is not None

    schema = data_schema.schema
    defaults = {key.schema: key.default() for key in schema}

    assert defaults[CONF_HOST] == NEW_HOST
    assert defaults[CONF_PORT] == NEW_PORT


async def test_validate_device_closes_client_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test device validation closes the client after a successful probe."""
    clients: list[FakeClient] = []

    class PatchedFakeClient(FakeClient):
        def __init__(self, host: str, port: int) -> None:
            super().__init__(host, port)
            clients.append(self)

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow.ItachClient",
        PatchedFakeClient,
    )

    await _validate_device(HOST, PORT)

    clients[0].close.assert_awaited_once()


async def test_validate_device_closes_client_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test device validation closes the client after a failed probe."""
    clients: list[FakeClient] = []

    class PatchedFakeClient(FakeClient):
        def __init__(self, host: str, port: int) -> None:
            super().__init__(host, port, module_error=ItachError("boom"))
            clients.append(self)

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow.ItachClient",
        PatchedFakeClient,
    )

    with pytest.raises(CannotConnect):
        await _validate_device(HOST, PORT)

    clients[0].close.assert_awaited_once()


async def test_identify_device_uses_manual_id_without_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test manual device ID is used before discovery is attempted."""
    wait = AsyncMock(return_value="GlobalCache_SHOULDNOTUSE")
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow.async_wait_for_device_id",
        wait,
    )

    assert await _identify_device(HOST, MAC) == UNIQUE_ID
    wait.assert_not_awaited()


async def test_identify_device_uses_discovery_when_manual_id_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test discovery is used when no manual device ID is supplied."""
    wait = AsyncMock(return_value=UNIQUE_ID)
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow.async_wait_for_device_id",
        wait,
    )
    discovery = cast(ItachDiscovery, object())

    assert await _identify_device(HOST, None, discovery) == UNIQUE_ID
    wait.assert_awaited_once_with(HOST, timeout=10.0, discovery=discovery)


async def test_identify_device_raises_when_missing_manual_and_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test identification fails when neither manual ID nor discovery are available."""
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow.async_wait_for_device_id",
        AsyncMock(return_value=None),
    )

    with pytest.raises(CannotIdentify):
        await _identify_device(HOST, None)


async def test_validate_manual_input_returns_capability_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test manual validation returns title, unique ID, and capability data."""
    _patch_client(monkeypatch)
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow.async_wait_for_device_id",
        AsyncMock(return_value=UNIQUE_ID),
    )

    result = await _validate_manual_input(HOST, PORT, None)

    assert result == {
        "title": f"iTach IP2IR ({HOST})",
        "unique_id": UNIQUE_ID,
        CONF_IR_MODULE: 1,
        CONF_IR_PORTS: 3,
        CONF_IR_CONNECTOR_MODES: {
            "1": "IR",
            "2": "SENSOR",
            "3": "IR_BLASTER",
        },
        CONF_IR_ENABLED_PORTS: [1, 3],
    }


async def test_validate_discovered_input_rejects_invalid_unique_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test discovered validation rejects invalid unique IDs."""
    _patch_client(monkeypatch)

    with pytest.raises(InvalidDeviceId):
        await _validate_discovered_input(HOST, PORT, "not-a-device-id")


async def test_get_discovery_returns_listener_when_available(
    hass: HomeAssistant,
) -> None:
    """Test running discovery listener is returned from hass data."""
    discovery = ItachDiscovery(hass)
    hass.data.setdefault(DOMAIN, {})[DISCOVERY] = discovery

    assert _get_discovery(hass) is discovery


async def test_get_discovery_returns_none_for_missing_or_wrong_type(
    hass: HomeAssistant,
) -> None:
    """Test discovery lookup ignores missing or invalid data."""
    assert _get_discovery(hass) is None

    hass.data.setdefault(DOMAIN, {})[DISCOVERY] = object()
    assert _get_discovery(hass) is None


async def test_user_flow_initial_form(hass: HomeAssistant) -> None:
    """Test the initial user step shows the setup form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_flow_unknown_error(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test manual user flow handles unexpected errors."""
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow._validate_manual_input",
        AsyncMock(side_effect=RuntimeError("boom")),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_DEVICE_ID: MAC,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_reconfigure_flow_no_change_aborts(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test reconfigure aborts when host and port are unchanged."""
    _patch_client(monkeypatch)
    entry = _make_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
        data=None,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_changes"


async def test_reconfigure_flow_unknown_error(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test reconfigure handles unexpected validation errors."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow._validate_device",
        AsyncMock(side_effect=RuntimeError("boom")),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
        data=None,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: NEW_HOST,
            CONF_PORT: NEW_PORT,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "unknown"}


async def test_discovery_flow_invalid_unique_id_aborts(hass: HomeAssistant) -> None:
    """Test discovery flow aborts when unique ID is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DISCOVERY},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            "unique_id": "not-a-device-id",
            "model": "iTachIP2IR",
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_identify"


async def test_discovery_confirm_unknown_error(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test discovery confirmation handles unexpected errors."""
    _patch_client(monkeypatch)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DISCOVERY},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            "unique_id": UNIQUE_ID,
            "model": "iTachIP2IR",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm_discovery"

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow._validate_discovered_input",
        AsyncMock(side_effect=RuntimeError("boom")),
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm_discovery"
    assert result["errors"] == {"base": "unknown"}


async def test_dhcp_flow_cannot_identify_after_validation_aborts(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test DHCP discovery aborts if validation cannot identify the device."""
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow._validate_discovered_input",
        AsyncMock(side_effect=CannotIdentify),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=_dhcp_info(),
    )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_identify"


async def test_dhcp_flow_unknown_error_aborts(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test DHCP discovery aborts cleanly for unexpected validation errors."""
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow._validate_discovered_input",
        AsyncMock(side_effect=RuntimeError("boom")),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=_dhcp_info(),
    )

    assert result["type"] == "abort"
    assert result["reason"] == "unknown"


async def test_dhcp_flow_missing_mac_aborts(hass: HomeAssistant) -> None:
    """Test DHCP discovery aborts when DHCP does not provide a MAC address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=_dhcp_info(macaddress=""),
    )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_identify"


async def test_reconfigure_flow_preserves_entry_data_on_validation_failure(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test failed reconfigure attempts do not mutate stored entry data."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.config_flow._validate_device",
        AsyncMock(side_effect=CannotConnect),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
        data=None,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: NEW_HOST, CONF_PORT: NEW_PORT},
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data[CONF_HOST] == HOST
    assert entry.data[CONF_PORT] == PORT
