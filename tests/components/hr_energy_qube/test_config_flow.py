"""Test the Qube Heat Pump config flow."""

from dataclasses import replace
from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import WebSocketGenerator
from python_qube_heatpump import QubeDeviceInfo

from homeassistant.components.hr_energy_qube.const import DOMAIN, MDNS_LOOKUP_TIMEOUT
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import DEVICE_INFO, async_shared_connections, setup_integration


def patch_answering_hosts(*hosts: str):
    """Patch the config flow's Modbus client so only ``hosts`` answer."""

    def client(host: str, *args: Any, **kwargs: Any) -> MagicMock:
        mock = MagicMock()
        mock.async_verify_device = AsyncMock(return_value=host in hosts)
        mock.is_connected = host in hosts
        return mock

    return patch(
        "homeassistant.components.hr_energy_qube.config_flow.QubeClient",
        side_effect=client,
    )


@pytest.mark.parametrize(
    ("device_info", "unique_id"),
    [
        pytest.param(DEVICE_INFO, DEVICE_INFO.uuid, id="mdns"),
        pytest.param(None, None, id="no_mdns"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_device_info: AsyncMock,
    mock_async_zeroconf: MagicMock,
    device_info: QubeDeviceInfo | None,
    unique_id: str | None,
) -> None:
    """Test the user flow, with and without the controller's mDNS record."""
    mock_device_info.return_value = device_info

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "qube.local"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Qube heat pump"
    assert result["data"] == {CONF_HOST: "qube.local", CONF_PORT: 502}
    assert result["result"].unique_id == unique_id
    mock_device_info.assert_awaited_once_with(
        "qube.local", mock_async_zeroconf, timeout=MDNS_LOOKUP_TIMEOUT
    )


@pytest.mark.parametrize(
    ("connected", "error"),
    [
        pytest.param(False, "cannot_connect", id="cannot_connect"),
        pytest.param(True, "not_qube_device", id="not_qube_device"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_errors(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    connected: bool,
    error: str,
) -> None:
    """Test flow error handling with recovery."""
    mock_qube_client.async_verify_device = AsyncMock(return_value=False)
    mock_qube_client.is_connected = connected

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Reset mocks for successful retry
    mock_qube_client.is_connected = True
    mock_qube_client.async_verify_device = AsyncMock(return_value=True)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "mock_qube_client")
async def test_flow_link_settings_in_use(hass: HomeAssistant) -> None:
    """Test the flow reports the device in use over other link settings."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.hr_energy_qube.config_flow.async_get_temporary_unit",
        side_effect=HomeAssistantError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "1.2.3.4"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_already_configured(
    hass: HomeAssistant, mock_qube_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_already_configured_by_unique_id(
    hass: HomeAssistant, mock_device_info: AsyncMock
) -> None:
    """Test re-adding a controller that moved to a new host updates the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.5.100", CONF_PORT: 502},
        unique_id=DEVICE_INFO.uuid,
    )
    entry.add_to_hass(hass)
    mock_device_info.return_value = DEVICE_INFO

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch_answering_hosts("1.2.3.4"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.2.3.4"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_HOST: "1.2.3.4", CONF_PORT: 502}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_second_qube_with_the_same_uuid(
    hass: HomeAssistant, mock_device_info: AsyncMock
) -> None:
    """Test a second Qube reporting a configured uuid is added without it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.5.100", CONF_PORT: 502},
        unique_id=DEVICE_INFO.uuid,
    )
    entry.add_to_hass(hass)
    mock_device_info.return_value = DEVICE_INFO

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch_answering_hosts("192.168.5.100", "192.168.5.208"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.5.208"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.168.5.208", CONF_PORT: 502}
    assert result["result"].unique_id is None
    assert entry.data == {CONF_HOST: "192.168.5.100", CONF_PORT: 502}


async def test_validation_reuses_the_entry_connection(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_qube_client_cls: MagicMock,
    mock_qube_client: MagicMock,
    mock_device_info: AsyncMock,
) -> None:
    """Test checking a loaded entry's host reuses its connection and keeps it open."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 502},
        unique_id=DEVICE_INFO.uuid,
    )
    await setup_integration(hass, entry)
    held = [(["tcp", "1.2.3.4", 502], {entry.entry_id: [1]})]
    assert await async_shared_connections(hass_ws_client) == held

    # A second Qube reporting the entry's uuid makes the flow check that the
    # entry's heat pump still answers, over the connection the entry holds
    seen: list[list[tuple[list[str | int], dict[str, list[int]]]]] = []

    async def verify() -> bool:
        seen.append(await async_shared_connections(hass_ws_client))
        return True

    mock_qube_client.async_verify_device.side_effect = verify
    mock_device_info.return_value = DEVICE_INFO

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.hr_energy_qube.async_setup_entry", return_value=None
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.5.208"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None
    assert len(seen) == 2
    assert seen[1] == held
    # Setup and both checks build the client on a borrowed unit
    assert len(mock_qube_client_cls.call_args_list) == 3
    assert all(
        call.kwargs["unit"] is not None for call in mock_qube_client_cls.call_args_list
    )
    assert await async_shared_connections(hass_ws_client) == held


ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.5.208"),
    ip_addresses=[ip_address("192.168.5.208")],
    hostname="Qube.local.",
    name="Qube._workstation._tcp.local.",
    port=9,
    type="_workstation._tcp.local.",
    properties={
        "Vendor": "000A5C",
        "MachineType": "312",
        "Uuid": "000100000007B5EA",
        "FWRelease": "v5.1.007",
        "ProjectRelease": "4.1.00",
        "ProjectName": "DEQSIHPB000CR",
    },
)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow(hass: HomeAssistant, mock_qube_client: MagicMock) -> None:
    """Test a discovered Qube is set up after confirmation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {"host": "192.168.5.208"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Qube heat pump"
    assert result["data"] == {CONF_HOST: "192.168.5.208", CONF_PORT: 502}
    assert result["result"].unique_id == DEVICE_INFO.uuid


@pytest.mark.parametrize(
    ("connected", "error"),
    [
        pytest.param(False, "cannot_connect", id="cannot_connect"),
        pytest.param(True, "not_qube_device", id="not_qube_device"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_confirm_errors(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    connected: bool,
    error: str,
) -> None:
    """Test the confirm step reports Modbus errors and can be retried."""
    mock_qube_client.async_verify_device = AsyncMock(return_value=False)
    mock_qube_client.is_connected = connected

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_qube_client.is_connected = True
    mock_qube_client.async_verify_device = AsyncMock(return_value=True)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_updates_host(hass: HomeAssistant) -> None:
    """Test rediscovery of a configured Qube updates its host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.5.100", CONF_PORT: 502},
        unique_id=DEVICE_INFO.uuid,
    )
    entry.add_to_hass(hass)

    with patch_answering_hosts():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_HOST: "192.168.5.208", CONF_PORT: 502}


@pytest.mark.parametrize(
    ("other_host", "answering"),
    [
        pytest.param(None, ("192.168.5.100",), id="old_address_answers"),
        pytest.param("192.168.5.208", (), id="address_of_other_entry"),
    ],
)
async def test_zeroconf_other_qube_with_the_same_uuid(
    hass: HomeAssistant, other_host: str | None, answering: tuple[str, ...]
) -> None:
    """Test an announcement from another Qube with the same uuid moves nothing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.5.100", CONF_PORT: 502},
        unique_id=DEVICE_INFO.uuid,
    )
    entry.add_to_hass(hass)
    if other_host:
        MockConfigEntry(
            domain=DOMAIN, data={CONF_HOST: other_host, CONF_PORT: 502}
        ).add_to_hass(hass)

    with patch_answering_hosts(*answering):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_HOST: "192.168.5.100", CONF_PORT: 502}


@pytest.mark.parametrize(
    "host",
    [
        pytest.param("192.168.5.208", id="ip"),
        pytest.param("qube.local", id="hostname"),
        pytest.param("Qube.local", id="hostname_case"),
        pytest.param("qube.local.", id="hostname_trailing_dot"),
        pytest.param("fd00::208", id="secondary_address"),
    ],
)
async def test_zeroconf_sets_unique_id_on_existing_entry(
    hass: HomeAssistant, host: str
) -> None:
    """Test an entry created without mDNS adopts the discovered uuid."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: host, CONF_PORT: 502})
    entry.add_to_hass(hass)
    discovery = replace(
        ZEROCONF_DISCOVERY,
        ip_addresses=[ip_address("192.168.5.208"), ip_address("fd00::208")],
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == DEVICE_INFO.uuid
    assert entry.data == {CONF_HOST: host, CONF_PORT: 502}


async def test_zeroconf_other_entry_without_unique_id(
    hass: HomeAssistant, mock_qube_client: MagicMock
) -> None:
    """Test an entry for another host is left alone and discovery continues."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.5.100", CONF_PORT: 502}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert entry.unique_id is None


async def test_zeroconf_not_qube(hass: HomeAssistant) -> None:
    """Test a record without a Carel vendor or uuid is rejected."""
    discovery = replace(
        ZEROCONF_DISCOVERY, properties={"Vendor": "000A5C", "ProjectName": "X"}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_qube_device"


@pytest.mark.parametrize(
    ("unique_id", "device_info"),
    [
        pytest.param(DEVICE_INFO.uuid, DEVICE_INFO, id="same_controller"),
        pytest.param(DEVICE_INFO.uuid, None, id="no_mdns"),
        pytest.param(None, DEVICE_INFO, id="no_unique_id"),
    ],
)
async def test_reconfigure(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_device_info: AsyncMock,
    unique_id: str | None,
    device_info: QubeDeviceInfo | None,
) -> None:
    """Test changing the host of an existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.5.100", CONF_PORT: 502},
        unique_id=unique_id,
    )
    entry.add_to_hass(hass)
    mock_device_info.return_value = device_info

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.5.208"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_HOST: "192.168.5.208", CONF_PORT: 502}
    assert entry.unique_id == unique_id


async def test_reconfigure_other_controller(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_device_info: AsyncMock,
) -> None:
    """Test reconfiguring to a different Qube is refused."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.5.100", CONF_PORT: 502},
        unique_id="0001000000000001",
    )
    entry.add_to_hass(hass)
    mock_device_info.return_value = DEVICE_INFO

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.5.208"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data == {CONF_HOST: "192.168.5.100", CONF_PORT: 502}


async def test_reconfigure_host_of_other_entry(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
) -> None:
    """Test reconfiguring to the host of another entry is refused."""
    other_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.5.208", CONF_PORT: 502}
    )
    other_entry.add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.5.100", CONF_PORT: 502}
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.5.208"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_HOST: "192.168.5.100", CONF_PORT: 502}


@pytest.mark.parametrize(
    ("connected", "error"),
    [
        pytest.param(False, "cannot_connect", id="cannot_connect"),
        pytest.param(True, "not_qube_device", id="not_qube_device"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    connected: bool,
    error: str,
) -> None:
    """Test reconfigure reports Modbus errors and can be retried."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.5.100", CONF_PORT: 502}
    )
    entry.add_to_hass(hass)
    mock_qube_client.async_verify_device = AsyncMock(return_value=False)
    mock_qube_client.is_connected = connected

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.5.208"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_qube_client.is_connected = True
    mock_qube_client.async_verify_device = AsyncMock(return_value=True)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.5.208"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.168.5.208"
