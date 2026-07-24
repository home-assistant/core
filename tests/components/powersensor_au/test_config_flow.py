"""Tests for the powersensor_au config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, Mock

from powersensor_local import VirtualHousehold
import pytest

from homeassistant import config_entries
import homeassistant.components.powersensor_au
from homeassistant.components.powersensor_au.config_flow import PowersensorConfigFlow
from homeassistant.components.powersensor_au.const import (
    DOMAIN,
    ROLE_UNKNOWN,
    ROLE_UPDATE_SIGNAL,
    ROLE_WATER,
)
from homeassistant.components.powersensor_au.models import PowersensorRuntimeData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

PLUG_MAC = "a4cf1218f158"
SECOND_MAC = "a4cf1218f160"


@pytest.fixture(autouse=True)
def bypass_setup(
    monkeypatch: pytest.MonkeyPatch,
    mock_async_zeroconf: MagicMock,
) -> None:
    """Bypass actual entry setup and prevent real zeroconf socket from opening."""
    monkeypatch.setattr(
        homeassistant.components.powersensor_au,
        "async_setup_entry",
        AsyncMock(return_value=True),
    )


def _zc_info(mac: str, ip: str = "192.168.0.33") -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address=ip_address(ip),
        ip_addresses=[ip_address(ip)],
        hostname=f"Powersensor-gateway-{mac}-civet.local",
        name=f"Powersensor-gateway-{mac}-civet._powersensor._udp.local",
        port=49476,
        type="_powersensor._udp.local.",
        properties={"version": "1", "id": mac},
    )


# ---------------------------------------------------------------------------
# User flow
# ---------------------------------------------------------------------------


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """User-initiated flow reaches the confirm form then creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert isinstance(result["data"]["roles"], dict)


async def test_user_flow_aborts_when_already_configured(hass: HomeAssistant) -> None:
    """A second user flow aborts with single_instance_allowed once an entry exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "single_instance_allowed"


async def test_user_flow_aborts_when_already_in_progress(hass: HomeAssistant) -> None:
    """A second user flow aborts if the first is still on the confirm form."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"


# ---------------------------------------------------------------------------
# Zeroconf flow
# ---------------------------------------------------------------------------


async def test_zeroconf_flow_creates_entry(hass: HomeAssistant) -> None:
    """Zeroconf discovery reaches confirm form then creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zc_info(PLUG_MAC),
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert isinstance(result["data"]["roles"], dict)


async def test_zeroconf_second_plug_aborts_when_configured(hass: HomeAssistant) -> None:
    """A second plug discovery aborts once the entry exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zc_info(PLUG_MAC),
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zc_info(SECOND_MAC, ip="192.168.0.37"),
    )
    assert result2["type"] == FlowResultType.ABORT


async def test_zeroconf_simultaneous_discoveries_deduplicate(
    hass: HomeAssistant,
) -> None:
    """Two simultaneous discoveries only produce one flow; the second aborts."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zc_info(PLUG_MAC),
    )
    assert result1["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zc_info(SECOND_MAC, ip="192.168.0.37"),
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"

    result1 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], user_input={}
    )
    assert result1["type"] == FlowResultType.CREATE_ENTRY


async def test_zeroconf_missing_id_aborts(hass: HomeAssistant) -> None:
    """Discovery aborts when the plug advertises without an 'id' property."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.0.33"),
            ip_addresses=[ip_address("192.168.0.33")],
            hostname="Powersensor-gateway.local",
            name="Powersensor-gateway._powersensor._udp.local",
            port=49476,
            type="_powersensor._udp.local.",
            properties={"version": "1"},  # no 'id'
        ),
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "firmware_not_compatible"


# ---------------------------------------------------------------------------
# Reconfigure flow
# ---------------------------------------------------------------------------


@pytest.fixture
def loaded_entry(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> MockConfigEntry:
    """A LOADED config entry with a mock dispatcher containing known sensors."""
    dispatcher = Mock()
    dispatcher.sensors = {
        "c001eat5": "house-net",
        "cafebabe": "solar",
        "d3adB33f": None,
    }
    dispatcher.plugs = set()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "roles": {"c001eat5": "house-net", "cafebabe": "solar", "d3adB33f": None}
        },
        entry_id="test_reconfig",
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
    )
    entry.runtime_data = PowersensorRuntimeData(
        vhh=VirtualHousehold(False),
        dispatcher=dispatcher,
        devices=Mock(),
    )
    object.__setattr__(entry, "state", ConfigEntryState.LOADED)

    monkeypatch.setattr(hass.config_entries, "async_get_entry", lambda _: entry)
    monkeypatch.setattr(
        hass.config_entries, "async_update_entry", lambda *a, **kw: True
    )
    return entry


@pytest.mark.parametrize("check_translations", [None])
async def test_reconfigure_applies_role(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Reconfigure form sends ROLE_UPDATE_SIGNAL for the submitted role."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": loaded_entry.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM

    received: list[tuple[str, str | None]] = []

    async def capture(mac, role):
        received.append((mac, role))

    unsub = async_dispatcher_connect(hass, ROLE_UPDATE_SIGNAL, capture)

    mac2name = {
        mac: f"Powersensor Sensor ({mac})"
        for mac in loaded_entry.runtime_data.dispatcher.sensors
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={mac2name["cafebabe"]: ROLE_WATER},
    )
    unsub()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "roles_applied"
    assert ("cafebabe", "water") in received


@pytest.mark.parametrize("check_translations", [None])
async def test_reconfigure_unknown_role_sends_none(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Selecting ROLE_UNKNOWN in the form sends None via ROLE_UPDATE_SIGNAL."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": loaded_entry.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM

    received: list[tuple[str, str | None]] = []

    async def capture(mac, role):
        received.append((mac, role))

    unsub = async_dispatcher_connect(hass, ROLE_UPDATE_SIGNAL, capture)
    mac2name = {
        mac: f"Powersensor Sensor ({mac})"
        for mac in loaded_entry.runtime_data.dispatcher.sensors
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={mac2name["d3adB33f"]: ROLE_UNKNOWN},
    )
    unsub()

    assert result["type"] == FlowResultType.ABORT
    assert ("d3adB33f", None) in received


async def test_reconfigure_aborts_when_entry_not_loaded(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reconfigure aborts with cannot_reconfigure when the entry is not LOADED."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="x",
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
    )
    object.__setattr__(entry, "state", ConfigEntryState.NOT_LOADED)
    monkeypatch.setattr(hass.config_entries, "async_get_entry", lambda _: entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": "x"},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_reconfigure"


@pytest.mark.parametrize("check_translations", [None])
async def test_reconfigure_skips_sensor_that_disappeared(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """A sensor removed from dispatcher.sensors between form render and submit is silently skipped."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": loaded_entry.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM

    # Capture the name for cafebabe before removing it from the dispatcher.
    mac2name = {
        mac: f"Powersensor Sensor ({mac})"
        for mac in loaded_entry.runtime_data.dispatcher.sensors
    }
    loaded_entry.runtime_data.dispatcher.sensors = {"c001eat5": "house-net"}

    fired: list[str] = []

    async def capture(mac, role):
        fired.append(mac)

    unsub = async_dispatcher_connect(hass, ROLE_UPDATE_SIGNAL, capture)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={mac2name["cafebabe"]: ROLE_WATER},
    )
    unsub()

    assert result["type"] == FlowResultType.ABORT
    assert "cafebabe" not in fired


@pytest.mark.parametrize("check_translations", [None])
async def test_reconfigure_none_role_shown_as_unknown(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """A None persisted role is shown as ROLE_UNKNOWN in the suggested_value."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": loaded_entry.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM

    assert result["data_schema"] is not None
    schema = result["data_schema"].schema
    sensor_name = "Powersensor Sensor (d3adB33f)"
    matching = [k for k in schema if getattr(k, "schema", None) == sensor_name]
    assert matching, f"No schema key for '{sensor_name}'"

    suggested = (matching[0].description or {}).get("suggested_value")
    assert suggested == ROLE_UNKNOWN


async def test_reconfigure_aborts_when_runtime_data_missing(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reconfigure aborts when runtime_data has not been set (AttributeError path)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"roles": {}},
        entry_id="x",
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
    )
    # Entry appears LOADED but runtime_data was never set.
    object.__setattr__(entry, "state", ConfigEntryState.LOADED)
    monkeypatch.setattr(hass.config_entries, "async_get_entry", lambda _: entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": "x"},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_reconfigure"


async def test_reconfigure_aborts_when_dispatcher_is_none(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reconfigure aborts when runtime_data.dispatcher is None."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"roles": {}},
        entry_id="x",
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
    )
    entry.runtime_data = PowersensorRuntimeData(
        vhh=VirtualHousehold(False),
        dispatcher=None,  # type: ignore[arg-type]
        devices=Mock(),
    )
    object.__setattr__(entry, "state", ConfigEntryState.LOADED)
    monkeypatch.setattr(hass.config_entries, "async_get_entry", lambda _: entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": "x"},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_reconfigure"
