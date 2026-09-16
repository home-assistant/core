"""Tests for the Zentraly integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from zentraly import (
    ClimateCapability,
    ClimateOperationMode,
    DeviceModel,
    ZentralyApi,
    ZentralyAuthenticationError,
    ZentralyClimateApi,
    ZentralyConnectionError,
    ZentralyDeviceInfo,
    get_device_commands,
)

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_PRESET_MODE,
    PRESET_AWAY,
)
from homeassistant.components.zentraly import _async_refresh_device_info, create_device
from homeassistant.components.zentraly.const import DOMAIN
from homeassistant.components.zentraly.platforms import get_device_platforms
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

PARENT_DEVICE_ID = "ZTTIN0100000631"
HOST = "192.168.1.42"
PORT = 80
PARENT_MAC = "dcda0c58c8d8"
PASSWORD = "test-password"


@pytest.mark.parametrize(
    ("error", "expected", "key"),
    [
        pytest.param(
            ZentralyAuthenticationError,
            ConfigEntryState.SETUP_ERROR,
            "authentication_failed",
            id="authentication",
        ),
        pytest.param(
            ZentralyConnectionError,
            ConfigEntryState.SETUP_RETRY,
            "setup_cannot_connect",
            id="connection",
        ),
    ],
)
async def test_translated_setup_error(
    hass: HomeAssistant,
    error: type[Exception],
    expected: ConfigEntryState,
    key: str,
) -> None:
    """Setup failures expose translated messages with the device identifier."""
    entry = _parent_entry()
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.zentraly.ZentralyApi.async_validate_password",
            side_effect=error,
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is expected
    assert entry.error_reason_translation_key == key
    assert entry.error_reason_translation_placeholders == {
        "device_id": PARENT_DEVICE_ID
    }


def test_translated_unsupported_model() -> None:
    """Unsupported models expose a translation key instead of hardcoded UI text."""
    api = ZentralyApi(HOST, PORT, PASSWORD, "UNKNOWN")
    with pytest.raises(ConfigEntryError) as exc:
        create_device(api, "UNKNOWN", PARENT_MAC)
    assert exc.value.translation_key == "unsupported_model"
    assert exc.value.translation_placeholders == {"device_id": "UNKNOWN"}


def _parent_entry() -> MockConfigEntry:
    """Return a mock Zentraly config entry."""

    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=PARENT_DEVICE_ID,
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_DEVICE_ID: PARENT_DEVICE_ID,
            CONF_PASSWORD: PASSWORD,
            CONF_MAC: PARENT_MAC,
        },
    )


async def test_setup_parent_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test setting up a Zentraly parent device."""

    entry = _parent_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.zentraly.ZentralyApi.async_validate_password",
            new_callable=AsyncMock,
            return_value=PARENT_MAC,
        ),
        patch(
            "homeassistant.components.zentraly.ZentralyApi.async_connect",
            new_callable=AsyncMock,
        ) as mock_connect,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new_callable=AsyncMock,
        ) as mock_forward,
    ):
        result = await hass.config_entries.async_setup(
            entry.entry_id,
        )

    assert result is True
    assert entry.state is ConfigEntryState.LOADED

    runtime_device = entry.runtime_data.device

    assert entry.runtime_data.api is runtime_device.api

    assert runtime_device.device_id == PARENT_DEVICE_ID
    assert runtime_device.mac == PARENT_MAC
    assert runtime_device.device_model is DeviceModel.ZTTIN

    assert get_device_platforms(PARENT_DEVICE_ID) == frozenset(
        {
            Platform.CLIMATE,
        }
    )

    parent_device = device_registry.async_get_device_by_identifier(
        (
            DOMAIN,
            PARENT_DEVICE_ID,
        ),
        entry.entry_id,
    )

    assert parent_device is not None
    assert parent_device.manufacturer == "Zentraly"
    assert parent_device.model == "Termostato Inalámbrico Wi-Fi"
    assert parent_device.model_id == "ZTTIN"
    assert parent_device.name == PARENT_DEVICE_ID
    assert parent_device.serial_number == PARENT_DEVICE_ID
    assert (
        dr.CONNECTION_NETWORK_MAC,
        dr.format_mac(PARENT_MAC),
    ) in parent_device.connections

    mock_connect.assert_awaited_once()

    mock_forward.assert_awaited_once_with(
        entry,
        [
            Platform.CLIMATE,
        ],
    )


async def test_setup_unexpected_mac(
    hass: HomeAssistant,
) -> None:
    """Test setup retries when the discovered MAC does not match."""

    entry = _parent_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.zentraly.ZentralyApi.async_validate_password",
            new_callable=AsyncMock,
            return_value="001122334455",
        ),
        patch(
            "homeassistant.components.zentraly.ZentralyApi.async_connect",
            new_callable=AsyncMock,
        ) as mock_connect,
    ):
        result = await hass.config_entries.async_setup(
            entry.entry_id,
        )

    assert result is False
    assert entry.state is ConfigEntryState.SETUP_RETRY

    mock_connect.assert_not_awaited()


async def test_climate_lifecycle(hass: HomeAssistant) -> None:
    """Expose only climate, process a report and release listeners on unload."""

    entry = _parent_entry()
    entry.add_to_hass(hass)
    api = MagicMock(spec=ZentralyApi)
    api.device_id = PARENT_DEVICE_ID
    api.host = HOST
    api.port = PORT
    api.connected = True
    api.async_validate_password.return_value = PARENT_MAC
    climate_api = MagicMock(spec=ZentralyClimateApi)
    commands = get_device_commands(DeviceModel.ZTTIN)
    climate_api.configuration = commands.climate_configuration
    climate_api.supports.side_effect = lambda capability: (
        capability in commands.capabilities
    )
    climate_api.async_get_humidity.return_value = 45.0
    climate_api.async_get_current_temperature.return_value = 19.0
    climate_api.async_get_target_temperature.return_value = 21.0
    climate_api.async_get_operation_mode.return_value = ClimateOperationMode.MANUAL
    climate_api.async_get_heat_demand.return_value = False
    climate_api.async_set_target_temperature.return_value = True
    climate_api.async_set_operation_mode.return_value = True
    with (
        patch("homeassistant.components.zentraly.ZentralyApi", return_value=api),
        patch(
            "homeassistant.components.zentraly.climate.ZentralyClimateApi",
            return_value=climate_api,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        states = hass.states.async_all()
        assert len(states) == 1
        state = states[0]
        assert state.domain == "climate"
        assert state.state == "heat"
        assert state.attributes[ATTR_CURRENT_HUMIDITY] == 45
        assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 19
        assert state.attributes[ATTR_TEMPERATURE] == 21
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": state.entity_id, ATTR_TEMPERATURE: 22},
            blocking=True,
        )
        climate_api.async_set_target_temperature.assert_awaited_once_with(22)
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {"entity_id": state.entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
            blocking=True,
        )
        climate_api.async_set_operation_mode.assert_awaited_once_with(
            ClimateOperationMode.AWAY
        )
        listener = climate_api.add_state_listener.call_args.args[0]
        listener(
            {
                ClimateCapability.TARGET_TEMPERATURE: 17.0,
                ClimateCapability.HEAT_DEMAND: True,
                ClimateCapability.HUMIDITY: 52.0,
            }
        )
        state = hass.states.get(state.entity_id)
        assert state is not None
        assert state.attributes[ATTR_CURRENT_HUMIDITY] == 52
        assert state.attributes[ATTR_TEMPERATURE] == 17
        assert state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY
        api.connected = False
        api.add_connection_state_listener.call_args.args[0](False)
        assert hass.states.get(state.entity_id).state == STATE_UNAVAILABLE
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    api.async_disconnect.assert_awaited_once()
    climate_api.add_state_listener.return_value.assert_called_once()
    api.add_connection_state_listener.return_value.assert_called_once()


async def test_refresh_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Update registry versions via the public API and retain last known values."""
    entry = _parent_entry()
    entry.add_to_hass(hass)
    api = MagicMock(spec=ZentralyApi)
    api.connected = True
    api.host = HOST
    api.port = PORT
    device = create_device(api, PARENT_DEVICE_ID, PARENT_MAC)
    registered = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, **device.device_info
    )
    with patch.object(
        type(device),
        "async_get_device_info",
        side_effect=[
            ZentralyDeviceInfo("1.0", "2.0"),
            ZentralyDeviceInfo(hardware_version="2.1"),
            ZentralyDeviceInfo(),
        ],
    ) as read_info:
        await _async_refresh_device_info(device, device_registry, registered.id)
        assert device_registry.async_get(registered.id).sw_version == "1.0"
        assert device_registry.async_get(registered.id).hw_version == "2.0"
        await _async_refresh_device_info(device, device_registry, registered.id)
        assert device_registry.async_get(registered.id).sw_version == "1.0"
        assert device_registry.async_get(registered.id).hw_version == "2.1"
        with patch.object(device_registry, "async_update_device") as update:
            await _async_refresh_device_info(device, device_registry, registered.id)
            api.connected = False
            await _async_refresh_device_info(device, device_registry, registered.id)
        update.assert_not_called()
        assert read_info.await_count == 3
