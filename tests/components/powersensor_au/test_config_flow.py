"""Tests for the powersensor_au config flow."""

from collections.abc import Callable, Coroutine
from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant import config_entries
from homeassistant.components.powersensor_au.config_flow import (
    CONF_ROLE,
    PowersensorConfigFlow,
)
from homeassistant.components.powersensor_au.const import (
    CFG_ROLES,
    DOMAIN,
    ROLE_APPLIANCE,
    ROLE_HOUSENET,
    ROLE_SOLAR,
    ROLE_UNKNOWN,
    ROLE_WATER,
)
from homeassistant.config_entries import ConfigEntryState, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.setup import async_setup_component

PLUG_MAC = "a4cf1218f158"
SECOND_MAC = "a4cf1218f160"
MAINS_MAC = "c001eat5"
SOLAR_MAC = "cafebabe"
UNKNOWN_MAC = "d3adb33f"
LATE_MAC = "0a0b0c0d0e0f"
# A role newer firmware might report that this integration does not know.
UNRECOGNISED_ROLE = "gas"


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


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_user_flow_creates_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """User-initiated flow reaches the confirm form then creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOMAIN
    assert result["data"] == {CFG_ROLES: {}}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    mock_setup_entry.assert_called_once()


@pytest.mark.usefixtures("mock_setup_entry", "mock_async_zeroconf")
async def test_user_flow_aborts_when_already_configured(hass: HomeAssistant) -> None:
    """A second user flow aborts with single_instance_allowed once an entry exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "single_instance_allowed"


@pytest.mark.usefixtures("mock_setup_entry", "mock_async_zeroconf")
async def test_user_flow_aborts_when_already_in_progress(hass: HomeAssistant) -> None:
    """A second user flow aborts if the first is still on the confirm form."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_zeroconf_flow_creates_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Zeroconf discovery reaches confirm form then creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zc_info(PLUG_MAC),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOMAIN
    assert result["data"] == {CFG_ROLES: {}}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    mock_setup_entry.assert_called_once()


@pytest.mark.usefixtures("mock_setup_entry", "mock_async_zeroconf")
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
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "single_instance_allowed"


@pytest.mark.usefixtures("mock_setup_entry", "mock_async_zeroconf")
async def test_zeroconf_discovery_can_be_ignored(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """A discovered installation can be ignored, which needs the flow's unique ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zc_info(PLUG_MAC),
    )
    assert result["type"] is FlowResultType.FORM

    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "config_entries/ignore_flow",
            "flow_id": result["flow_id"],
            "title": "Powersensor",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    entries = hass.config_entries.async_entries(DOMAIN, include_ignore=True)
    assert [entry.source for entry in entries] == [config_entries.SOURCE_IGNORE]


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_zeroconf_simultaneous_discoveries_deduplicate(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Two simultaneous discoveries only produce one flow; the second aborts."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zc_info(PLUG_MAC),
    )
    assert result1["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zc_info(SECOND_MAC, ip="192.168.0.37"),
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"

    result1 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], user_input={}
    )
    assert result1["type"] is FlowResultType.CREATE_ENTRY
    assert result1["result"].unique_id == DOMAIN
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    mock_setup_entry.assert_called_once()


@pytest.mark.usefixtures("mock_setup_entry", "mock_async_zeroconf")
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
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "firmware_not_compatible"


@pytest.fixture
async def reconfigure_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> MockConfigEntry:
    """A loaded entry with a house-net, a solar and an unassigned sensor discovered."""
    await fire({"event": "device_found", "mac": MAINS_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": MAINS_MAC,
            "role": ROLE_HOUSENET,
        }
    )
    await fire({"event": "device_found", "mac": SOLAR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SOLAR_MAC,
            "role": ROLE_SOLAR,
        }
    )
    await fire({"event": "device_found", "mac": UNKNOWN_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()
    return config_entry


async def _start_reconfigure(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    """Start the reconfigure flow and return its flow id."""
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor_role"
    return result["flow_id"]


async def test_reconfigure_persists_every_sensor_role_and_reloads(
    hass: HomeAssistant,
    reconfigure_entry: MockConfigEntry,
    mock_devices: MagicMock,
) -> None:
    """Each sensor gets its own step and all roles land in entry.data in one update."""
    flow_id = await _start_reconfigure(hass, reconfigure_entry)

    result = await hass.config_entries.flow.async_configure(
        flow_id, user_input={CONF_ROLE: ROLE_HOUSENET}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor_role"

    result = await hass.config_entries.flow.async_configure(
        flow_id, user_input={CONF_ROLE: ROLE_UNKNOWN}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["last_step"] is True

    result = await hass.config_entries.flow.async_configure(
        flow_id, user_input={CONF_ROLE: ROLE_WATER}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert reconfigure_entry.data[CFG_ROLES] == {
        MAINS_MAC: ROLE_HOUSENET,
        SOLAR_MAC: None,
        UNKNOWN_MAC: ROLE_WATER,
    }
    assert reconfigure_entry.state is ConfigEntryState.LOADED
    mock_devices.stop.assert_awaited_once()
    assert mock_devices.start.await_count == 2


def _suggested_values(result: ConfigFlowResult) -> list[Any]:
    """Return the suggested value of each field on a form."""
    assert result["data_schema"] is not None
    return [key.description["suggested_value"] for key in result["data_schema"].schema]


async def test_reconfigure_uses_roles_saved_while_it_is_open(
    hass: HomeAssistant,
    reconfigure_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Roles reported while the flow is open are suggested, and not overwritten."""
    result = await reconfigure_entry.start_reconfigure_flow(hass)

    # While the first step is shown, the unassigned sensor reports a role and a
    # sensor the flow doesn't know about appears with one.
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": UNKNOWN_MAC,
            "role": ROLE_WATER,
        }
    )
    await fire({"event": "device_found", "mac": LATE_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": LATE_MAC,
            "role": ROLE_APPLIANCE,
        }
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ROLE: ROLE_HOUSENET}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ROLE: ROLE_SOLAR}
    )
    assert _suggested_values(result) == [ROLE_WATER]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ROLE: ROLE_WATER}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert reconfigure_entry.data[CFG_ROLES] == {
        MAINS_MAC: ROLE_HOUSENET,
        SOLAR_MAC: ROLE_SOLAR,
        UNKNOWN_MAC: ROLE_WATER,
        LATE_MAC: ROLE_APPLIANCE,
    }


async def test_reconfigure_steps_show_current_role_and_device_name(
    hass: HomeAssistant,
    reconfigure_entry: MockConfigEntry,
) -> None:
    """Each step suggests the sensor's current role and names it as the device registry does."""
    # Steps follow the order the sensors were discovered in.
    result = await reconfigure_entry.start_reconfigure_flow(hass)
    assert result["description_placeholders"]["sensor"] == f"Mains sensor ({MAINS_MAC})"
    assert _suggested_values(result) == [ROLE_HOUSENET]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ROLE: ROLE_HOUSENET}
    )
    assert result["description_placeholders"]["sensor"] == f"Solar sensor ({SOLAR_MAC})"
    assert _suggested_values(result) == [ROLE_SOLAR]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ROLE: ROLE_SOLAR}
    )
    assert result["description_placeholders"]["sensor"] == f"Sensor ({UNKNOWN_MAC})"
    assert _suggested_values(result) == [ROLE_UNKNOWN]


@pytest.mark.parametrize(
    ("change_device", "expected_name"),
    [
        pytest.param(
            lambda registry, device: registry.async_update_device(
                device.id, name_by_user="Kitchen meter"
            ),
            "Kitchen meter",
            id="renamed_by_user",
        ),
        pytest.param(
            lambda registry, device: registry.async_remove_device(device.id),
            UNKNOWN_MAC,
            id="no_device",
        ),
    ],
)
async def test_reconfigure_step_names_sensor_from_device_registry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    device_registry: dr.DeviceRegistry,
    change_device: Callable[[dr.DeviceRegistry, dr.DeviceEntry], Any],
    expected_name: str,
) -> None:
    """The step uses the user's name for the sensor's device, or the MAC without one."""
    await fire({"event": "device_found", "mac": UNKNOWN_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, UNKNOWN_MAC), config_entry.entry_id
    )
    assert device is not None
    change_device(device_registry, device)

    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"]["sensor"] == expected_name


async def test_reconfigure_suggests_unknown_for_unrecognised_role(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """A persisted role that is not a selector option is suggested as unknown."""
    await fire({"event": "device_found", "mac": UNKNOWN_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": UNKNOWN_MAC,
            "role": UNRECOGNISED_ROLE,
        }
    )
    await hass.async_block_till_done()
    assert config_entry.data[CFG_ROLES][UNKNOWN_MAC] == UNRECOGNISED_ROLE

    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert _suggested_values(result) == [ROLE_UNKNOWN]


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_reconfigure_aborts_when_entry_not_loaded(hass: HomeAssistant) -> None:
    """Reconfigure aborts when the entry is not loaded, as sensors are only known at runtime."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CFG_ROLES: {}},
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


@pytest.mark.parametrize(
    "events",
    [
        pytest.param([], id="nothing_discovered"),
        pytest.param(
            [
                {"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"},
                # Plugs report a role too; that must not make them a sensor.
                {
                    "event": "average_power",
                    "mac": PLUG_MAC,
                    "role": ROLE_APPLIANCE,
                    "watts": 50.0,
                    "starttime_utc": 1700000000,
                    "duration_s": 10,
                },
            ],
            id="only_plugs",
        ),
    ],
)
async def test_reconfigure_aborts_when_no_sensors_discovered(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    events: list[dict[str, Any]],
) -> None:
    """Reconfigure aborts when the entry is loaded but no sensor has been seen yet."""
    for event in events:
        await fire(event)
    await hass.async_block_till_done()

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_sensors_found"
