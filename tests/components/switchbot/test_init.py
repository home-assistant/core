"""Test the switchbot init."""

from collections.abc import Callable
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
import switchbot

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.switchbot.const import (
    CONF_CURTAIN_SPEED,
    CONF_RETRY_COUNT,
    DEFAULT_CURTAIN_SPEED,
    DEFAULT_RETRY_COUNT,
    DEPRECATED_SENSOR_TYPE_AIR_PURIFIER,
    DEPRECATED_SENSOR_TYPE_AIR_PURIFIER_TABLE,
    DOMAIN,
    HASS_SENSOR_TYPE_TO_SWITCHBOT_MODEL,
    SUPPORTED_MODEL_TYPES,
    SupportedModels,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_MAC, CONF_NAME, CONF_SENSOR_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    AIR_PURIFIER_JP_SERVICE_INFO,
    AIR_PURIFIER_TABLE_JP_SERVICE_INFO,
    AIR_PURIFIER_TABLE_US_SERVICE_INFO,
    AIR_PURIFIER_US_SERVICE_INFO,
    HUBMINI_MATTER_SERVICE_INFO,
    LOCK_SERVICE_INFO,
    STANDING_FAN_SERVICE_INFO,
    WOCURTAIN3_SERVICE_INFO,
    WOCURTAIN_SERVICE_INFO,
    WOMETERTHPC_SERVICE_INFO,
    WOSENSORTH_SERVICE_INFO,
    patch_async_ble_device_from_address,
    patch_async_setup_entry,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            ValueError("wrong model"),
            "Switchbot device initialization failed because of"
            " incorrect configuration parameters: wrong model",
        ),
    ],
)
async def test_exception_handling_for_device_initialization(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    exception: Exception,
    error_message: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test exception handling for lock initialization."""
    inject_bluetooth_service_info(hass, LOCK_SERVICE_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="lock")
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.switchbot.lock.switchbot.SwitchbotLock.__init__",
        side_effect=exception,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        # The Bluetooth discovery flow reloads the entry in a background task
        await hass.async_block_till_done(wait_background_tasks=True)
    assert error_message in caplog.text


async def test_setup_entry_without_ble_device(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup entry without ble device."""

    entry = mock_entry_factory("meter_pro_co2")
    entry.add_to_hass(hass)

    with patch_async_ble_device_from_address(None):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert (
        "Could not find Switchbot meter_pro_co2 with address aa:bb:cc:dd:ee:ff"
        in caplog.text
    )


async def test_setup_entry_meter_pro_co2_uses_non_connectable(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test that Meter Pro CO2 setup uses connectable=False for BLE lookup.

    Meter Pro CO2 is in both CONNECTABLE and NON_CONNECTABLE model types,
    so async_ble_device_from_address should be called with connectable=False
    to support passive BT proxies.
    """
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = mock_entry_factory("meter_pro_co2")
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
    ) as mock_ble:
        mock_ble.return_value = WOMETERTHPC_SERVICE_INFO.device
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Meter Pro CO2 supports both active and passive Bluetooth sources
        assert mock_ble.call_args_list[0][0][2] is False


async def test_coordinator_wait_ready_timeout(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the coordinator async_wait_ready timeout by calling it directly."""

    inject_bluetooth_service_info(hass, HUBMINI_MATTER_SERVICE_INFO)

    entry = mock_entry_factory("hubmini_matter")
    entry.add_to_hass(hass)

    timeout_mock = AsyncMock()
    timeout_mock.__aenter__.side_effect = TimeoutError
    timeout_mock.__aexit__.return_value = None

    with patch(
        "homeassistant.components.switchbot.coordinator.asyncio.timeout",
        return_value=timeout_mock,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert "aa:bb:cc:dd:ee:ff is not advertising state" in caplog.text


@pytest.mark.parametrize(
    ("sensor_type", "service_info", "expected_sensor_type", "expected_options"),
    [
        (
            "curtain",
            WOCURTAIN_SERVICE_INFO,
            "curtain",
            {
                CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT,
                CONF_CURTAIN_SPEED: DEFAULT_CURTAIN_SPEED,
            },
        ),
        (
            "hygrometer",
            WOSENSORTH_SERVICE_INFO,
            "meter",
            {CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT},
        ),
        pytest.param(
            "curtain",
            WOCURTAIN3_SERVICE_INFO,
            "curtain_3",
            {
                CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT,
                CONF_CURTAIN_SPEED: DEFAULT_CURTAIN_SPEED,
            },
            id="curtain_3",
        ),
    ],
)
@pytest.mark.parametrize("minor_version", [1, 2, 3])
async def test_migrate_entry_from_v1_to_v2(
    hass: HomeAssistant,
    sensor_type: str,
    service_info: BluetoothServiceInfoBleak,
    expected_sensor_type: str,
    expected_options: dict[str, int],
    minor_version: int,
) -> None:
    """Test migration from version 1 adds options and resolves the model."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: sensor_type,
        },
        unique_id="aabbccddeeff",
        version=1,
        minor_version=minor_version,
        options={},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.switchbot.bluetooth.async_last_service_info",
            return_value=service_info,
        ),
        patch_async_setup_entry(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.minor_version == 1
    assert entry.data[CONF_SENSOR_TYPE] == expected_sensor_type
    assert entry.options == expected_options


@pytest.mark.parametrize(
    ("old_sensor_type", "model", "expected_sensor_type"),
    [
        ("hygrometer", switchbot.SwitchbotModel.METER, "meter"),
        ("hygrometer", switchbot.SwitchbotModel.METER_PLUS, "meter_plus"),
        ("hygrometer", switchbot.SwitchbotModel.METER_PRO, "meter_pro"),
        (
            "hygrometer",
            switchbot.SwitchbotModel.INDOOR_OUTDOOR_THERMO_HYGROMETER,
            "indoor_outdoor_thermo_hygrometer",
        ),
        ("curtain", switchbot.SwitchbotModel.CURTAIN, "curtain"),
        ("curtain", switchbot.SwitchbotModel.CURTAIN_3, "curtain_3"),
        (
            "ceiling_light",
            switchbot.SwitchbotModel.CEILING_LIGHT,
            "ceiling_light",
        ),
        (
            "ceiling_light",
            switchbot.SwitchbotModel.CEILING_LIGHT_PRO,
            "ceiling_light_pro",
        ),
        ("plug", switchbot.SwitchbotModel.PLUG_MINI_US, "plug_mini_us"),
        ("plug", switchbot.SwitchbotModel.PLUG_MINI_JP, "plug_mini_jp"),
    ],
)
async def test_migrate_deprecated_model_sensor_type(
    hass: HomeAssistant,
    old_sensor_type: str,
    model: switchbot.SwitchbotModel,
    expected_sensor_type: str,
) -> None:
    """Test deprecated model types are resolved from BLE advertisements."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: old_sensor_type,
        },
        unique_id="aabbccddeeff",
        version=1,
        minor_version=2,
        options={CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT},
    )
    entry.add_to_hass(hass)

    parsed = MagicMock(data={"modelName": model})
    with (
        patch(
            "homeassistant.components.switchbot.bluetooth.async_last_service_info",
            return_value=WOCURTAIN_SERVICE_INFO,
        ),
        patch(
            "homeassistant.components.switchbot.switchbot.parse_advertisement_data",
            return_value=parsed,
        ) as mock_parse,
        patch_async_setup_entry(),
        patch(
            "homeassistant.components.switchbot.async_unload_entry", return_value=True
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.minor_version == 1
    assert entry.data[CONF_SENSOR_TYPE] == expected_sensor_type
    assert entry.unique_id == "aabbccddeeff"
    mock_parse.assert_called_once()


def test_model_type_maps_are_one_to_one() -> None:
    """Test every persisted type has one exact pySwitchbot model."""
    assert len(SUPPORTED_MODEL_TYPES) == len(set(SUPPORTED_MODEL_TYPES.values()))
    assert set(HASS_SENSOR_TYPE_TO_SWITCHBOT_MODEL) == set(SupportedModels)
    for model, sensor_type in SUPPORTED_MODEL_TYPES.items():
        assert HASS_SENSOR_TYPE_TO_SWITCHBOT_MODEL[sensor_type] is model


@pytest.mark.parametrize(
    ("address_key", "address", "expected_address"),
    [
        pytest.param(
            CONF_ADDRESS, "aa:bb:cc:dd:ee:ff", "AA:BB:CC:DD:EE:FF", id="address"
        ),
        pytest.param(CONF_MAC, "aabbccddeeff", "AA:BB:CC:DD:EE:FF", id="legacy_mac"),
        pytest.param(
            CONF_MAC,
            "12345678-1234-5678-90ab-1234567890ab",
            "12345678-1234-5678-90AB-1234567890AB",
            id="legacy_uuid",
        ),
    ],
)
async def test_migrate_passive_advertisement(
    hass: HomeAssistant,
    address_key: str,
    address: str,
    expected_address: str,
) -> None:
    """Test migration looks up passive advertisements using legacy addresses."""
    original_data = {address_key: address, CONF_SENSOR_TYPE: "hygrometer"}
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=original_data,
        unique_id="aabbccddeeff",
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.switchbot.bluetooth.async_last_service_info",
            side_effect=[None, WOSENSORTH_SERVICE_INFO],
        ) as mock_service_info,
        patch_async_setup_entry(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.minor_version == 1
    assert entry.data == {**original_data, CONF_SENSOR_TYPE: "meter"}
    assert entry.unique_id == "aabbccddeeff"
    assert mock_service_info.call_args_list == [
        call(hass, expected_address, connectable=True),
        call(hass, expected_address, connectable=False),
    ]


async def test_migration_preserves_registry_identifiers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    meter_service_info: BluetoothServiceInfoBleak,
) -> None:
    """Test migration does not change config, device, or entity unique IDs."""
    inject_bluetooth_service_info(hass, meter_service_info)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_SENSOR_TYPE: "hygrometer",
        },
        unique_id="aabbccddeeff",
        version=1,
        minor_version=2,
        options={CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT},
    )
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "aabbccddeeff")},
        connections={(dr.CONNECTION_BLUETOOTH, meter_service_info.address)},
    )
    entity = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="aabbccddeeff-temperature",
        config_entry=entry,
        device_id=device.id,
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.minor_version == 1
    assert entry.data[CONF_SENSOR_TYPE] == "meter"
    assert entry.unique_id == "aabbccddeeff"
    assert device_registry.async_get(device.id).identifiers == {
        (DOMAIN, "aabbccddeeff")
    }
    assert entity_registry.async_get(entity.entity_id).unique_id == (
        "aabbccddeeff-temperature"
    )
    assert entity_registry.async_get(entity.entity_id).device_id == device.id
    assert len(dr.async_entries_for_config_entry(device_registry, entry.entry_id)) == 1
    assert hass.states.get(entity.entity_id) is not None


@pytest.mark.parametrize("minor_version", [1, 2])
async def test_migrate_meter_pro_co2_without_advertisement(
    hass: HomeAssistant,
    minor_version: int,
) -> None:
    """Test the unambiguous Meter Pro CO2 migration needs no advertisement."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_SENSOR_TYPE: "hygrometer_co2",
        },
        unique_id="aabbccddeeff",
        version=1,
        minor_version=minor_version,
        options={CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.switchbot.bluetooth.async_last_service_info",
        ) as mock_service_info,
        patch_async_setup_entry(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.minor_version == 1
    assert entry.data[CONF_SENSOR_TYPE] == "meter_pro_co2"
    assert entry.unique_id == "aabbccddeeff"
    mock_service_info.assert_not_called()


@pytest.mark.parametrize(
    "sensor_type", ["hygrometer", "curtain", "ceiling_light", "plug"]
)
async def test_migrate_deprecated_model_device_not_in_range(
    hass: HomeAssistant,
    sensor_type: str,
) -> None:
    """Test an ambiguous model migration retries without modifying the entry."""
    original_data = {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_NAME: "test-name",
        CONF_SENSOR_TYPE: sensor_type,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=original_data,
        unique_id="aabbccddeeff",
        version=1,
        minor_version=2,
        options={},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.data == original_data
    assert entry.options == {}
    assert entry.unique_id == "aabbccddeeff"


async def test_migration_retries_when_device_returns(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    meter_service_info: BluetoothServiceInfoBleak,
) -> None:
    """Test an offline device migrates when its advertisement becomes available."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: "aa:bb:cc:dd:ee:ff", CONF_SENSOR_TYPE: "hygrometer"},
        unique_id="aabbccddeeff",
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.version == 1

    inject_bluetooth_service_info(hass, meter_service_info)
    with patch_async_setup_entry():
        freezer.tick(timedelta(seconds=60))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.minor_version == 1
    assert entry.data[CONF_SENSOR_TYPE] == "meter"
    assert entry.unique_id == "aabbccddeeff"


@pytest.mark.parametrize(
    "service_info",
    [
        pytest.param(WOCURTAIN_SERVICE_INFO, id="curtain"),
        pytest.param(WOCURTAIN3_SERVICE_INFO, id="curtain_3"),
    ],
)
async def test_migrate_entry_preserves_existing_options(
    hass: HomeAssistant,
    service_info: BluetoothServiceInfoBleak,
) -> None:
    """Test migration preserves existing options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "curtain",
        },
        unique_id="aabbccddeeff",
        version=1,
        minor_version=1,
        options={CONF_RETRY_COUNT: 5, CONF_CURTAIN_SPEED: 1},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.switchbot.bluetooth.async_last_service_info",
            return_value=service_info,
        ),
        patch_async_setup_entry(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.minor_version == 1
    assert entry.options[CONF_RETRY_COUNT] == 5
    assert entry.options[CONF_CURTAIN_SPEED] == 1


@pytest.mark.parametrize(
    ("entry_version", "flow_version"),
    [
        pytest.param(3, 2, id="future_version"),
        pytest.param(2, 1, id="downgrade_to_old_home_assistant"),
    ],
)
async def test_migrate_entry_fails_for_future_version(
    hass: HomeAssistant,
    entry_version: int,
    flow_version: int,
) -> None:
    """Test migration fails for future versions."""
    inject_bluetooth_service_info(hass, WOCURTAIN_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "curtain",
        },
        unique_id="aabbccddeeff",
        version=entry_version,
        minor_version=1,
        options={},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.switchbot.config_flow.SwitchbotConfigFlow.VERSION",
            flow_version,
        ),
        patch_async_setup_entry() as mock_setup_entry,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.version == entry_version
    assert entry.minor_version == 1
    assert entry.data[CONF_SENSOR_TYPE] == "curtain"
    mock_setup_entry.assert_not_called()


@pytest.mark.parametrize(
    ("old_sensor_type", "service_info", "expected_sensor_type"),
    [
        (
            DEPRECATED_SENSOR_TYPE_AIR_PURIFIER,
            AIR_PURIFIER_JP_SERVICE_INFO,
            "air_purifier_jp",
        ),
        (
            DEPRECATED_SENSOR_TYPE_AIR_PURIFIER,
            AIR_PURIFIER_US_SERVICE_INFO,
            "air_purifier_us",
        ),
        (
            DEPRECATED_SENSOR_TYPE_AIR_PURIFIER_TABLE,
            AIR_PURIFIER_TABLE_JP_SERVICE_INFO,
            "air_purifier_table_jp",
        ),
        (
            DEPRECATED_SENSOR_TYPE_AIR_PURIFIER_TABLE,
            AIR_PURIFIER_TABLE_US_SERVICE_INFO,
            "air_purifier_table_us",
        ),
    ],
)
async def test_migrate_deprecated_air_purifier_sensor_type(
    hass: HomeAssistant,
    old_sensor_type: str,
    service_info: BluetoothServiceInfoBleak,
    expected_sensor_type: str,
) -> None:
    """Test deprecated air_purifier types are migrated via BLE."""
    inject_bluetooth_service_info(hass, service_info)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: old_sensor_type,
        },
        unique_id="aabbccddeeff",
        version=1,
        minor_version=2,
        options={CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.data[CONF_SENSOR_TYPE] == expected_sensor_type


async def test_migrate_deprecated_air_purifier_sensor_type_device_not_in_range(
    hass: HomeAssistant,
) -> None:
    """Test deprecated air_purifier entry not loaded when out of range."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: DEPRECATED_SENSOR_TYPE_AIR_PURIFIER,
        },
        unique_id="aabbccddeeff",
        version=1,
        minor_version=2,
        options={CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # sensor_type unchanged and entry not loaded; will retry when device advertises
    assert entry.data[CONF_SENSOR_TYPE] == DEPRECATED_SENSOR_TYPE_AIR_PURIFIER
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_standing_fan_setup(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test the Standing Fan is recognized and set up."""
    inject_bluetooth_service_info(hass, STANDING_FAN_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="standing_fan")
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.switchbot.switchbot.SwitchbotStandingFan.get_basic_info",
        new=AsyncMock(return_value=None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data.device, switchbot.SwitchbotStandingFan)
