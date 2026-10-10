"""Tests for the Airobot VU coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection.mock import MockModbusConnection
from pyairobotmodbus.exceptions import (
    AirobotConnectionError,
    AirobotReadError,
    AirobotTimeoutError,
)
from pyairobotmodbus.models import AirobotIdentity
import pytest

from homeassistant.components.airobot.const import (
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_VENTILATION,
    DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator


@pytest.fixture
def platforms() -> list[Platform]:
    """No platforms for coordinator-only tests."""
    return []


async def _list_modbus_connections(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> list[dict]:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "modbus/connections/list"})
    return (await client.receive_json())["result"]["connections"]


@pytest.mark.usefixtures("init_vu_integration")
async def test_vu_setup_entry_success(
    hass: HomeAssistant, mock_vu_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of a VU config entry."""
    assert mock_vu_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("init_vu_integration")
async def test_vu_shares_modbus_connection(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_vu_config_entry: MockConfigEntry,
) -> None:
    """Test the unit is reached over the Modbus integration's shared connection."""
    assert await _list_modbus_connections(hass, hass_ws_client) == [
        {
            "endpoint": ["tcp", "192.168.1.200", 502],
            "connected": False,
            "source": "config_entry",
            "units": {mock_vu_config_entry.entry_id: [1]},
        }
    ]

    await hass.config_entries.async_unload(mock_vu_config_entry.entry_id)
    await hass.async_block_till_done()

    # Unloading releases the unit, closing the connection behind it
    assert await _list_modbus_connections(hass, hass_ws_client) == []


@pytest.mark.parametrize(
    ("method_name", "exception"),
    [
        pytest.param(
            "async_get_identity",
            AirobotConnectionError("Connection failed"),
            id="identity_connection_error",
        ),
        pytest.param(
            "async_get_data",
            AirobotConnectionError("Connection failed"),
            id="data_connection_error",
        ),
        pytest.param(
            "async_get_data",
            AirobotTimeoutError("Timeout"),
            id="data_timeout",
        ),
    ],
)
async def test_vu_setup_entry_exceptions(
    hass: HomeAssistant,
    mock_vu_client: AsyncMock,
    mock_vu_config_entry: MockConfigEntry,
    method_name: str,
    exception: Exception,
) -> None:
    """Test VU setup fails with connection exceptions."""
    mock_vu_config_entry.add_to_hass(hass)
    getattr(mock_vu_client, method_name).side_effect = exception

    await hass.config_entries.async_setup(mock_vu_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_vu_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_vu_setup_fails_on_modbus_link_conflict(
    hass: HomeAssistant, mock_vu_config_entry: MockConfigEntry
) -> None:
    """Test setup stops when the unit is held over different link settings."""
    mock_vu_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.airobot.async_get_unit",
        side_effect=HomeAssistantError("Modbus device is already in use"),
    ):
        await hass.config_entries.async_setup(mock_vu_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_vu_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_vu_config_entry.error_reason_translation_key == "modbus_link_conflict"
    assert mock_vu_config_entry.error_reason_translation_placeholders == {
        "host": mock_vu_config_entry.data[CONF_HOST]
    }


# The device is registered by its entities
@pytest.mark.parametrize("platforms", [[Platform.SENSOR]])
@pytest.mark.usefixtures("init_vu_integration")
async def test_vu_device_serial_number(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_vu_config_entry: MockConfigEntry,
) -> None:
    """Test the device carries the serial number read from the unit."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_vu_config_entry.entry_id), mock_vu_config_entry.entry_id
    )
    assert device is not None
    assert device.serial_number == "01234567"


async def test_vu_setup_without_identity_registers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_vu_client: AsyncMock,
    mock_vu_config_entry: MockConfigEntry,
) -> None:
    """Test firmware without the identity registers still sets up."""
    mock_vu_client.async_get_identity.side_effect = AirobotReadError("Illegal address")
    mock_vu_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.airobot.VU_PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_vu_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_vu_config_entry.state is ConfigEntryState.LOADED
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_vu_config_entry.entry_id), mock_vu_config_entry.entry_id
    )
    assert device is not None
    assert device.serial_number is None


async def test_vu_unique_ids_fall_back_to_entry_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_vu_client: AsyncMock,
) -> None:
    """Test entries without a MAC key their entities on the entry ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.200", CONF_DEVICE_TYPE: DEVICE_TYPE_VENTILATION},
        title="Airobot Ventilation",
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.airobot.VU_PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{entry.entry_id}_co2_level"
    )


async def test_vu_unique_ids_migrate_to_mac(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_vu_client: AsyncMock,
    mock_vu_config_entry: MockConfigEntry,
) -> None:
    """Test entities created before the MAC was known move to MAC unique IDs."""
    mock_vu_config_entry.add_to_hass(hass)
    old = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{mock_vu_config_entry.entry_id}_co2_level",
        config_entry=mock_vu_config_entry,
    )
    current = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aa:bb:cc:dd:ee:ff_voc",
        config_entry=mock_vu_config_entry,
    )

    with patch("homeassistant.components.airobot.VU_PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_vu_config_entry.entry_id)
        await hass.async_block_till_done()

    migrated = entity_registry.async_get(old.entity_id)
    assert migrated is not None
    assert migrated.unique_id == "aa:bb:cc:dd:ee:ff_co2_level"
    unchanged = entity_registry.async_get(current.entity_id)
    assert unchanged is not None
    assert unchanged.unique_id == "aa:bb:cc:dd:ee:ff_voc"


OTHER_UNIT = AirobotIdentity(serial_number="07654321", mac_address="11:22:33:44:55:66")


async def test_vu_setup_retries_when_another_unit_answers(
    hass: HomeAssistant,
    mock_vu_client: AsyncMock,
    mock_vu_config_entry: MockConfigEntry,
) -> None:
    """Test setup waits while a different unit answers at the entry's host."""
    mock_vu_client.async_get_identity.return_value = OTHER_UNIT
    mock_vu_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_vu_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_vu_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_vu_client.async_get_data.assert_not_called()


async def test_vu_identity_rechecked_after_link_drop(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vu_client: AsyncMock,
    mock_vu_config_entry: MockConfigEntry,
) -> None:
    """Test the unit's identity is checked again once the link drops."""
    connection = MockModbusConnection()
    mock_vu_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.airobot.async_get_unit",
            return_value=connection.for_unit(1),
        ),
        patch("homeassistant.components.airobot.VU_PLATFORMS", [Platform.SENSOR]),
    ):
        await hass.config_entries.async_setup(mock_vu_config_entry.entry_id)
        await hass.async_block_till_done()

    async def _poll() -> None:
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    entity_id = "sensor.airobot_ventilation_co2_level"
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    # While the link stays up, the identity is not read again
    await _poll()
    assert mock_vu_client.async_get_identity.call_count == 1

    # Another unit takes over the address and the link reconnects to it
    connection.simulate_connection_lost()
    mock_vu_client.async_get_identity.return_value = OTHER_UNIT
    await _poll()
    assert mock_vu_client.async_get_identity.call_count == 2
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # Once the configured unit answers again, its data is shown again
    mock_vu_client.async_get_identity.return_value = AirobotIdentity(
        serial_number="01234567", mac_address="aa:bb:cc:dd:ee:ff"
    )
    await _poll()
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE
