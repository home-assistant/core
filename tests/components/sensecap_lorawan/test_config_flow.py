"""Test user setup and LoRaWAN discovery."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import patch

from lorawan_connection import (
    AddedEvent,
    ConnectionUnavailable,
    DeviceDescriptor,
    RemovedEvent,
)
from lorawan_connection.mock import MockConnection
import pytest
from pytest_homeassistant.common import MockConfigEntry
from sensecap_lorawan import S2100, S2101, SenseCapDevice

from homeassistant.components.lorawan import (
    LoRaWANDiscoveryInfo,
    async_register_connection,
)
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util

from .const import CATALOG_MODELS


@pytest.fixture(autouse=True)
def mock_discovery() -> Generator[None]:
    """Start flows explicitly instead of scheduling them during registration."""
    with patch(
        "homeassistant.components.lorawan.connection.discovery_flow.async_create_flow"
    ):
        yield


@pytest.mark.parametrize(
    ("source", "data"),
    [(SOURCE_USER, None), (SOURCE_INTEGRATION_DISCOVERY, LoRaWANDiscoveryInfo())],
)
@pytest.mark.parametrize(("stack", "model"), CATALOG_MODELS)
async def test_setup(
    hass: HomeAssistant,
    source: str,
    data: LoRaWANDiscoveryInfo | None,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
    descriptor: DeviceDescriptor,
    stack: str,
    model: type[SenseCapDevice],
) -> None:
    """Both entry points require a supported device on either backend."""
    mock_connection.emit(
        AddedEvent(
            descriptor=replace(
                descriptor,
                brand_id=model.identifiers[stack][0],
                model_id=model.identifiers[stack][1],
            ),
            received_at=dt_util.utcnow(),
        )
    )
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    result = await hass.config_entries.flow.async_init(
        "sensecap_lorawan", context={"source": source}, data=data
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    with patch(
        "homeassistant.components.sensecap_lorawan.async_setup_entry", return_value=True
    ) as setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SenseCAP"
    assert result["data"] == {}
    assert result["result"].unique_id == "sensecap_lorawan"
    setup.assert_called_once()


@pytest.mark.parametrize(
    ("source", "data"),
    [(SOURCE_USER, None), (SOURCE_INTEGRATION_DISCOVERY, LoRaWANDiscoveryInfo())],
)
@pytest.mark.usefixtures("config_entry")
async def test_already_configured(
    hass: HomeAssistant, source: str, data: LoRaWANDiscoveryInfo | None
) -> None:
    """Only one SenseCAP entry is needed for all connections."""
    result = await hass.config_entries.flow.async_init(
        "sensecap_lorawan", context={"source": source}, data=data
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_duplicate_discovery(
    hass: HomeAssistant, connection_entry: MockConfigEntry
) -> None:
    """Concurrent discoveries share one confirmation flow."""
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    await hass.config_entries.flow.async_init(
        "sensecap_lorawan",
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data=LoRaWANDiscoveryInfo(),
    )
    result = await hass.config_entries.flow.async_init(
        "sensecap_lorawan",
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data=LoRaWANDiscoveryInfo(),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.parametrize(
    ("source", "data"),
    [(SOURCE_USER, None), (SOURCE_INTEGRATION_DISCOVERY, LoRaWANDiscoveryInfo())],
)
async def test_no_connections(
    hass: HomeAssistant, source: str, data: LoRaWANDiscoveryInfo | None
) -> None:
    """Explain that a LoRaWAN backend must be configured first."""
    result = await hass.config_entries.flow.async_init(
        "sensecap_lorawan", context={"source": source}, data=data
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_lorawan_connections"


async def test_empty_connection(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
) -> None:
    """An empty backend cannot create a SenseCAP entry."""
    mock_connection.devices.clear()
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    result = await hass.config_entries.flow.async_init(
        "sensecap_lorawan", context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_supported_devices"


@pytest.mark.parametrize(
    ("brand_id", "model_id"),
    [
        S2100.identifiers["chirpstack"],
        (744, "unknown"),
        (999, S2101.identifiers["chirpstack"][1]),
    ],
)
async def test_unsupported_device(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
    descriptor: DeviceDescriptor,
    brand_id: int,
    model_id: str,
) -> None:
    """Only models exposed by the sensor platform allow setup."""
    mock_connection.emit(
        AddedEvent(
            descriptor=replace(descriptor, brand_id=brand_id, model_id=model_id),
            received_at=dt_util.utcnow(),
        )
    )
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    result = await hass.config_entries.flow.async_init(
        "sensecap_lorawan", context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_supported_devices"


async def test_connection_removed_before_confirmation(
    hass: HomeAssistant, connection_entry: MockConfigEntry
) -> None:
    """Recheck connection availability before creating the entry."""
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    result = await hass.config_entries.flow.async_init(
        "sensecap_lorawan", context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert await hass.config_entries.async_unload(connection_entry.entry_id)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_lorawan_connections"


async def test_device_removed_before_confirmation(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
    descriptor: DeviceDescriptor,
) -> None:
    """A removed device cannot leave an empty integration configured."""
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    result = await hass.config_entries.flow.async_init(
        "sensecap_lorawan", context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    mock_connection.emit(
        RemovedEvent(descriptor=descriptor, received_at=dt_util.utcnow())
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_supported_devices"


async def test_connection_unavailable(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
) -> None:
    """Explain a backend failure while reading its devices."""
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    with patch.object(
        mock_connection, "async_subscribe", side_effect=ConnectionUnavailable
    ):
        result = await hass.config_entries.flow.async_init(
            "sensecap_lorawan", context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_lorawan_connections"


@pytest.mark.parametrize("error", [None, ConnectionUnavailable])
async def test_supported_device_on_another_connection(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
    descriptor: DeviceDescriptor,
    error: type[ConnectionUnavailable] | None,
) -> None:
    """Check later connections when the first is empty or unavailable."""
    mock_connection.devices.clear()
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    other_entry = MockConfigEntry(domain="test_connection", entry_id="other")
    other_entry.add_to_hass(hass)
    other_connection = MockConnection([replace(descriptor, network_id="other")])
    unsubscribe = await async_register_connection(
        hass, other_entry, connection=other_connection
    )
    with patch.object(
        mock_connection,
        "async_subscribe",
        wraps=mock_connection.async_subscribe,
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_init(
            "sensecap_lorawan", context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    unsubscribe()
