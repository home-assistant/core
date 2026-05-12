"""Coordinator for Inepro Metering polling."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from inepro_metering.commands import (
    async_apply_register_writes,
    build_wifi_credential_writes,
)
from inepro_metering.gateway_settings import (
    GATEWAY_MANAGEMENT_SLAVE_ID,
    GatewaySettingState,
    build_gateway_setting_states,
    get_gateway_action,
    get_gateway_setting,
    supports_gateway_management,
)
from inepro_metering.reading import build_register_blocks, decode_sensor_value
from inepro_metering.runtime import (
    MeterGatewayInfo,
    MeterRoute,
    MeterRuntimeData,
    build_meter_runtime_data,
)
from inepro_metering.settings import WIFI_SUPPORT_SETTING_KEY, get_writable_setting

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .bluetooth import async_entry_data_with_ha_ble_device
from .const import (
    CONF_FAMILY,
    CONF_SLAVE_ID,
    CONF_TRANSPORT,
    CONF_VARIANT,
    DOMAIN,
    TransportType,
)
from .entry_data import (
    ConfiguredMeter,
    build_meter_key,
    get_configured_meters,
    is_bus_entry,
)
from .modbus import IneproMeteringError, IneproModbusClient
from .models import (
    MeterProfile,
    MeterSensorDescription,
    get_profile,
    get_profile_for_variant,
)

_LOGGER = logging.getLogger(__name__)
BLE_STALE_READ_GRACE_POLLS = 3


@dataclass(frozen=True, slots=True)
class CoordinatorData:
    """Coordinator payload shared by single-meter entities.

    The thin wrapper keeps existing entity code straightforward while the
    runtime model continues to live in the shared library.
    """

    meter: MeterRuntimeData
    gateway: MeterGatewayInfo | None = None
    gateway_settings: dict[str, GatewaySettingState] = field(default_factory=dict)

    @property
    def readings(self) -> dict[str, str | int | float]:
        """Backwards-compatible access to decoded meter readings."""
        return self.meter.readings

    @property
    def last_successful_update(self) -> datetime | None:
        """Backwards-compatible access to the last successful update timestamp."""
        return self.meter.connection.last_successful_update


@dataclass(frozen=True, slots=True)
class MeterCoordinatorData:
    """Per-meter payload inside one serial bus coordinator.

    This mirrors ``CoordinatorData`` so bus entities can keep the same access
    pattern as single-meter entries.
    """

    meter: MeterRuntimeData

    @property
    def readings(self) -> dict[str, str | int | float]:
        """Backwards-compatible access to decoded meter readings."""
        return self.meter.readings

    @property
    def last_successful_update(self) -> datetime | None:
        """Backwards-compatible access to the last successful update timestamp."""
        return self.meter.connection.last_successful_update

    @property
    def available(self) -> bool:
        """Backwards-compatible access to per-meter availability."""
        return self.meter.connection.available


@dataclass(frozen=True, slots=True)
class SerialBusCoordinatorData:
    """Coordinator payload shared by a serial bus entry."""

    meters: dict[str, MeterCoordinatorData]
    gateway: MeterGatewayInfo | None = None
    gateway_settings: dict[str, GatewaySettingState] = field(default_factory=dict)


class IneproMeteringCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Coordinate Modbus polling for one configured meter."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.profile = get_profile(entry.data[CONF_FAMILY], entry.data[CONF_VARIANT])
        self._transport = TransportType(entry.data[CONF_TRANSPORT])
        self._client = IneproModbusClient(
            _build_runtime_client_config(hass, entry.data)
        )
        self._last_data: CoordinatorData | None = None
        self._last_gateway: MeterGatewayInfo | None = None
        self._last_gateway_settings: dict[str, GatewaySettingState] = {}
        self._consecutive_failures = 0

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=int(entry.data[CONF_SCAN_INTERVAL])),
        )

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch the latest Modbus data."""
        try:
            slave_id = int(self.entry.data[CONF_SLAVE_ID])
            last_successful_update = dt_util.utcnow()
            gateway_info = await _async_read_gateway_metadata_if_supported(
                self._client,
                self._transport,
            )
            gateway_configuration = (
                await _async_read_gateway_configuration_if_supported(
                    self._client,
                    self._transport,
                )
            )
            gateway_readings: dict[str, str | int | float] = {}
            if gateway_info is not None:
                gateway_readings.update(gateway_info.as_readings())
            if gateway_configuration is not None:
                gateway_readings.update(gateway_configuration.as_readings())
            readings = await _async_read_profile(
                self._client,
                self.profile.all_sensors,
                slave_id,
            )
            if gateway_readings:
                readings.update(gateway_readings)

            meter_runtime = build_meter_runtime_data(
                profile=self.profile,
                route=MeterRoute(
                    transport=TransportType(self.entry.data[CONF_TRANSPORT]),
                    slave_id=slave_id,
                ),
                readings=readings,
                available=True,
                last_successful_update=last_successful_update,
            )
            gateway = self._last_gateway
            if gateway_info is not None:
                gateway = MeterGatewayInfo.from_readings(gateway_info.as_readings())
            gateway_settings = self._last_gateway_settings
            if gateway_configuration is not None:
                gateway_settings = build_gateway_setting_states(
                    gateway_configuration.as_readings()
                )
        except Exception as err:
            if _should_keep_ble_stale_data(
                self._transport,
                self._last_data,
                self._consecutive_failures,
            ):
                self._consecutive_failures += 1
                assert self._last_data is not None
                _LOGGER.warning(
                    "Transient BLE polling failure for %s; keeping last successful data (%s/%s): %s",
                    self.entry.title,
                    self._consecutive_failures,
                    BLE_STALE_READ_GRACE_POLLS,
                    err,
                )
                return self._last_data

            message = (
                str(err)
                if isinstance(err, IneproMeteringError)
                else "Unexpected Modbus read failure"
            )
            raise UpdateFailed(message) from err
        else:
            coordinator_data = CoordinatorData(
                meter=meter_runtime,
                gateway=gateway,
                gateway_settings=gateway_settings,
            )
            self._last_data = coordinator_data
            self._last_gateway = gateway
            self._last_gateway_settings = gateway_settings
            self._consecutive_failures = 0
            return coordinator_data

    async def async_shutdown(self) -> None:
        """Close transport resources."""
        await self._client.async_close()

    async def async_set_wifi_credentials(
        self,
        *,
        slave_id: int,
        ssid: str,
        password: str,
        apply: bool,
        meter_key: str | None = None,
    ) -> None:
        """Write GROW Wi-Fi credentials through this meter connection."""
        del meter_key
        await _async_write_wifi_credentials(
            self._client,
            slave_id=slave_id,
            ssid=ssid,
            password=password,
            apply=apply,
        )

    async def async_set_wifi_enabled(self, *, slave_id: int, enabled: bool) -> None:
        """Enable or disable GROW Wi-Fi support through this meter connection."""
        await self.async_write_setting(
            profile=self.profile,
            slave_id=slave_id,
            setting_key=WIFI_SUPPORT_SETTING_KEY,
            value=enabled,
        )

    async def async_write_setting(
        self,
        *,
        profile: MeterProfile,
        slave_id: int,
        setting_key: str,
        value: bool | float | str,
    ) -> None:
        """Apply one shared-library writable setting through this meter connection."""
        await _async_write_setting(
            self._client,
            profile=profile,
            slave_id=slave_id,
            setting_key=setting_key,
            value=value,
        )

    async def async_write_gateway_setting(
        self,
        *,
        setting_key: str,
        value: bool | float | str,
    ) -> None:
        """Apply one shared-library gateway setting through this gateway route."""
        await _async_write_gateway_setting(
            self._client,
            setting_key=setting_key,
            value=value,
        )

    async def async_execute_gateway_action(self, *, action_key: str) -> None:
        """Execute one shared-library gateway action through this gateway route."""
        await _async_execute_gateway_action(
            self._client,
            action_key=action_key,
        )


class IneproSerialBusCoordinator(DataUpdateCoordinator[SerialBusCoordinatorData]):
    """Coordinate Modbus polling for multiple meters on one RTU bus."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the serial bus coordinator."""
        self.entry = entry
        self._client = IneproModbusClient(
            _build_runtime_client_config(hass, entry.data)
        )
        self._meters = get_configured_meters(entry.data, title=entry.title)
        self._profiles = {
            build_meter_key(meter): get_profile_for_variant(meter.variant)
            for meter in self._meters
        }
        self._last_meter_data: dict[str, MeterCoordinatorData] = {}
        self._last_gateway: MeterGatewayInfo | None = None
        self._last_gateway_settings: dict[str, GatewaySettingState] = {}

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=int(entry.data[CONF_SCAN_INTERVAL])),
        )

    @property
    def configured_meters(self) -> tuple[ConfiguredMeter, ...]:
        """Return configured meters on this bus."""
        return self._meters

    def get_profile_for_meter(self, meter: ConfiguredMeter) -> MeterProfile:
        """Return the profile for one configured meter."""
        return self._profiles[build_meter_key(meter)]

    async def _async_update_data(self) -> SerialBusCoordinatorData:
        """Fetch the latest Modbus data for each configured bus meter."""
        meter_results: dict[str, MeterCoordinatorData] = {}
        successful_reads = 0
        gateway_info = await _async_read_gateway_metadata_if_supported(
            self._client,
            TransportType(self.entry.data[CONF_TRANSPORT]),
        )
        gateway_configuration = await _async_read_gateway_configuration_if_supported(
            self._client,
            TransportType(self.entry.data[CONF_TRANSPORT]),
        )
        gateway_readings: dict[str, str | int | float] = {}
        if gateway_info is not None:
            gateway_readings.update(gateway_info.as_readings())
        if gateway_configuration is not None:
            gateway_readings.update(gateway_configuration.as_readings())

        for meter in self._meters:
            meter_key = build_meter_key(meter)
            profile = self._profiles[meter_key]
            previous = self._last_meter_data.get(meter_key)

            try:
                readings = await _async_read_profile(
                    self._client,
                    profile.all_sensors,
                    meter.slave_id,
                )
                if gateway_readings:
                    readings.update(gateway_readings)
            except IneproMeteringError:
                previous_readings = previous.readings if previous is not None else {}
                last_successful_update = (
                    previous.last_successful_update if previous is not None else None
                )
                meter_results[meter_key] = MeterCoordinatorData(
                    meter=build_meter_runtime_data(
                        profile=profile,
                        route=MeterRoute(
                            transport=TransportType(self.entry.data[CONF_TRANSPORT]),
                            slave_id=meter.slave_id,
                        ),
                        readings=previous_readings,
                        available=False,
                        last_successful_update=last_successful_update,
                    )
                )
                continue

            successful_reads += 1
            last_successful_update = dt_util.utcnow()
            meter_results[meter_key] = MeterCoordinatorData(
                meter=build_meter_runtime_data(
                    profile=profile,
                    route=MeterRoute(
                        transport=TransportType(self.entry.data[CONF_TRANSPORT]),
                        slave_id=meter.slave_id,
                    ),
                    readings=readings,
                    available=True,
                    last_successful_update=last_successful_update,
                )
            )

        if (
            self._meters
            and successful_reads == 0
            and not any(
                meter_data.readings for meter_data in self._last_meter_data.values()
            )
        ):
            raise UpdateFailed("No configured meters responded on the serial bus")

        self._last_meter_data = meter_results
        gateway = self._last_gateway
        if gateway_info is not None:
            gateway = MeterGatewayInfo.from_readings(gateway_info.as_readings())
        gateway_settings = self._last_gateway_settings
        if gateway_configuration is not None:
            gateway_settings = build_gateway_setting_states(
                gateway_configuration.as_readings()
            )
        self._last_gateway = gateway
        self._last_gateway_settings = gateway_settings
        return SerialBusCoordinatorData(
            meters=meter_results,
            gateway=gateway,
            gateway_settings=gateway_settings,
        )

    async def async_shutdown(self) -> None:
        """Close transport resources."""
        await self._client.async_close()

    async def async_set_wifi_credentials(
        self,
        *,
        slave_id: int,
        ssid: str,
        password: str,
        apply: bool,
        meter_key: str | None = None,
    ) -> None:
        """Write GROW Wi-Fi credentials through this serial bus connection."""
        del meter_key
        await _async_write_wifi_credentials(
            self._client,
            slave_id=slave_id,
            ssid=ssid,
            password=password,
            apply=apply,
        )

    async def async_set_wifi_enabled(self, *, slave_id: int, enabled: bool) -> None:
        """Enable or disable GROW Wi-Fi support through this serial bus connection."""
        meter = next(
            configured for configured in self._meters if configured.slave_id == slave_id
        )
        await self.async_write_setting(
            profile=self.get_profile_for_meter(meter),
            slave_id=slave_id,
            setting_key=WIFI_SUPPORT_SETTING_KEY,
            value=enabled,
        )

    async def async_write_setting(
        self,
        *,
        profile: MeterProfile,
        slave_id: int,
        setting_key: str,
        value: bool | float | str,
    ) -> None:
        """Apply one shared-library writable setting through this serial bus connection."""
        await _async_write_setting(
            self._client,
            profile=profile,
            slave_id=slave_id,
            setting_key=setting_key,
            value=value,
        )

    async def async_write_gateway_setting(
        self,
        *,
        setting_key: str,
        value: bool | float | str,
    ) -> None:
        """Apply one shared-library gateway setting through this gateway route."""
        await _async_write_gateway_setting(
            self._client,
            setting_key=setting_key,
            value=value,
        )

    async def async_execute_gateway_action(self, *, action_key: str) -> None:
        """Execute one shared-library gateway action through this gateway route."""
        await _async_execute_gateway_action(
            self._client,
            action_key=action_key,
        )


def build_runtime_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> IneproMeteringCoordinator | IneproSerialBusCoordinator:
    """Build the runtime coordinator matching the entry shape."""
    if is_bus_entry(entry.data):
        return IneproSerialBusCoordinator(hass, entry)
    return IneproMeteringCoordinator(hass, entry)


def _build_runtime_client_config(
    hass: HomeAssistant,
    entry_data: dict[str, Any],
) -> dict[str, Any]:
    """Return client config enriched with runtime-only Home Assistant objects."""
    return async_entry_data_with_ha_ble_device(hass, entry_data, require_device=False)


def _should_keep_ble_stale_data(
    transport: TransportType,
    last_data: CoordinatorData | None,
    consecutive_failures: int,
) -> bool:
    """Return whether a transient BLE read failure should reuse cached data."""
    return (
        transport in {TransportType.BLUETOOTH, TransportType.BLUETOOTH_PROXY}
        and last_data is not None
        and consecutive_failures < BLE_STALE_READ_GRACE_POLLS
    )


async def _async_read_profile(
    client: IneproModbusClient,
    sensors: tuple[MeterSensorDescription, ...],
    slave_id: int,
) -> dict[str, str | int | float]:
    """Read all sensors for one profile and slave ID."""
    blocks = build_register_blocks(sensors)
    readings: dict[str, str | int | float] = {}
    successful_blocks = 0
    last_error: IneproMeteringError | None = None

    for block in blocks:
        try:
            block_registers = await client.async_read_registers(
                block.register_type,
                block.start_address,
                block.count,
                slave_id,
            )
        except IneproMeteringError as err:
            last_error = err
            _LOGGER.debug(
                "Skipping unreadable register block for slave %s at %s:%s (%s)",
                slave_id,
                block.register_type.value,
                block.start_address,
                err,
            )
            continue

        successful_blocks += 1

        for sensor in block.sensors:
            offset = sensor.address - block.start_address
            sensor_registers = block_registers[offset : offset + sensor.count]
            readings[sensor.key] = decode_sensor_value(sensor, sensor_registers)

    if successful_blocks == 0 and last_error is not None:
        raise last_error

    unsupported_slaves = getattr(
        client,
        "_inepro_unsupported_device_identification_slaves",
        set(),
    )
    if slave_id not in unsupported_slaves:
        try:
            # Device-identification data is transport-derived metadata layered onto
            # decoded register readings. Some GROW firmware closes the connection
            # on 43/14, so remember unsupported slaves after the first failure.
            readings.update(
                (await client.async_read_device_identification(slave_id)).as_readings()
            )
        except AttributeError:
            unsupported_slaves.add(slave_id)
            setattr(
                client,
                "_inepro_unsupported_device_identification_slaves",
                unsupported_slaves,
            )
        except IneproMeteringError as err:
            unsupported_slaves.add(slave_id)
            setattr(
                client,
                "_inepro_unsupported_device_identification_slaves",
                unsupported_slaves,
            )
            _LOGGER.debug(
                "Modbus device-identification read disabled for slave %s: %s",
                slave_id,
                err,
            )

    return readings


async def _async_read_gateway_metadata_if_supported(
    client: IneproModbusClient,
    transport: TransportType,
) -> dict[str, str | int] | None:
    """Read vendor-specific TCP gateway metadata for gateway-backed routes."""
    if not supports_gateway_management(transport):
        return None

    try:
        return await client.async_read_tcp_gateway_info()
    except AttributeError:
        return None
    except IneproMeteringError as err:
        _LOGGER.debug("TCP gateway metadata read failed: %s", err)
        return None


async def _async_read_gateway_configuration_if_supported(
    client: IneproModbusClient,
    transport: TransportType,
):
    """Read shared-library TCP gateway configuration for gateway-backed routes."""
    if not supports_gateway_management(transport):
        return None

    try:
        return await client.async_read_tcp_gateway_configuration()
    except AttributeError:
        return None
    except IneproMeteringError as err:
        _LOGGER.debug("TCP gateway configuration read failed: %s", err)
        return None


async def _async_write_wifi_credentials(
    client: IneproModbusClient,
    *,
    slave_id: int,
    ssid: str,
    password: str,
    apply: bool,
) -> None:
    """Write GROW Wi-Fi credentials using the confirmed register sequence."""
    await async_apply_register_writes(
        client,
        build_wifi_credential_writes(ssid, password, apply=apply),
        slave_id=slave_id,
    )


async def _async_write_setting(
    client: IneproModbusClient,
    *,
    profile: MeterProfile,
    slave_id: int,
    setting_key: str,
    value: bool | float | str,
) -> None:
    """Write one shared-library setting through the supplied Modbus client."""
    setting = get_writable_setting(profile, setting_key)
    await async_apply_register_writes(
        client,
        setting.build_writes(profile, value),
        slave_id=slave_id,
    )


async def _async_write_gateway_setting(
    client: IneproModbusClient,
    *,
    setting_key: str,
    value: bool | float | str,
) -> None:
    """Write one shared-library gateway setting through the supplied Modbus client."""
    setting = get_gateway_setting(setting_key)
    await async_apply_register_writes(
        client,
        setting.build_writes(value),
        slave_id=GATEWAY_MANAGEMENT_SLAVE_ID,
    )


async def _async_execute_gateway_action(
    client: IneproModbusClient,
    *,
    action_key: str,
) -> None:
    """Execute one shared-library gateway action through the supplied Modbus client."""
    action = get_gateway_action(action_key)
    await async_apply_register_writes(
        client,
        action.build_writes(),
        slave_id=GATEWAY_MANAGEMENT_SLAVE_ID,
    )
