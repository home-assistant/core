"""Sensor platform for Inepro Metering."""

from inepro_metering.runtime import VERSION_CRC_KEYS, format_meter_version_value

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_FAMILY,
    CONF_TRANSPORT,
    CONF_VARIANT,
    FAMILY_LABELS,
    MANUFACTURER,
    TRANSPORT_LABELS,
    MeterFamily,
    TransportType,
)
from .coordinator import (
    IneproMeteringCoordinator,
    IneproSerialBusCoordinator,
    MeterCoordinatorData,
)
from .device_identity import configured_entry_serial, meter_device_identifier
from .entry_data import (
    ConfiguredMeter,
    build_meter_key,
    get_configured_meters,
    is_bus_entry,
)
from .gateway_support import (
    build_gateway_device_info,
    downstream_meter_via_device,
    entry_supports_gateway_management,
)
from .models import (
    MeterProfile,
    MeterSensorDescription,
    decode_grow_error_code,
    format_grow_error_summary,
    get_profile,
    get_profile_for_variant,
)

MODBUS_DEVICE_INFO_SENSORS = (
    ("manufacturer_name", "Manufacturer Name"),
    ("product_name", "Product Name"),
    ("device_version", "Device Version"),
)

TCP_GATEWAY_INFO_SENSORS = (
    ("device_type", "Device Type"),
    ("hardware_version", "Hardware Version"),
    ("serial_number", "Serial Number"),
    ("firmware_version", "Firmware Version"),
    ("bootloader_version", "Bootloader Version"),
)


def _grow_error_attributes(
    readings: dict[str, str | int | float],
) -> dict[str, str | list[str]] | None:
    """Return decoded GROW error details for the raw error-code entity."""
    error_code = readings.get("error_code")
    summary = format_grow_error_summary(error_code)
    if summary is None:
        return None

    decoded_errors = list(decode_grow_error_code(error_code))
    return {
        "decoded_error_summary": summary,
        "decoded_errors": decoded_errors,
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Inepro Metering sensors from a config entry."""
    coordinator = entry.runtime_data
    transport = TransportType(entry.data[CONF_TRANSPORT])

    if is_bus_entry(entry.data):
        bus_coordinator: IneproSerialBusCoordinator = coordinator
        entities: list[SensorEntity] = []
        configured_meters = get_configured_meters(entry.data, title=entry.title)
        primary_meter = configured_meters[0] if configured_meters else None

        if entry_supports_gateway_management(entry):
            entities.extend(
                IneproBusGatewayInfoSensor(
                    bus_coordinator,
                    entry,
                    field=field,
                    name=name,
                )
                for field, name in TCP_GATEWAY_INFO_SENSORS
            )

        for meter in configured_meters:
            use_legacy_identity = meter == primary_meter
            profile = get_profile_for_variant(meter.variant)
            entities.extend(
                IneproBusDynamicInfoSensor(
                    bus_coordinator,
                    entry,
                    meter,
                    profile,
                    field=field,
                    name=name,
                    use_legacy_identity=use_legacy_identity,
                )
                for field, name in MODBUS_DEVICE_INFO_SENSORS
            )
            entities.extend(
                [
                    IneproBusStatusSensor(
                        bus_coordinator,
                        entry,
                        meter,
                        profile,
                        use_legacy_identity=use_legacy_identity,
                    ),
                    IneproBusLastSuccessfulUpdateSensor(
                        bus_coordinator,
                        entry,
                        meter,
                        profile,
                        use_legacy_identity=use_legacy_identity,
                    ),
                    IneproBusStaticInfoSensor(
                        bus_coordinator,
                        entry,
                        meter,
                        profile,
                        use_legacy_identity=use_legacy_identity,
                        key="meter_family",
                        name="Meter Family",
                        value=FAMILY_LABELS[profile.family],
                    ),
                    IneproBusStaticInfoSensor(
                        bus_coordinator,
                        entry,
                        meter,
                        profile,
                        use_legacy_identity=use_legacy_identity,
                        key="meter_model",
                        name="Meter Model",
                        value=profile.title,
                    ),
                    IneproBusStaticInfoSensor(
                        bus_coordinator,
                        entry,
                        meter,
                        profile,
                        use_legacy_identity=use_legacy_identity,
                        key="transport",
                        name="Transport",
                        value=TRANSPORT_LABELS[transport],
                    ),
                ]
            )
            if profile.family == MeterFamily.GROW:
                entities.append(
                    IneproBusErrorSummarySensor(
                        bus_coordinator,
                        entry,
                        meter,
                        profile,
                        use_legacy_identity=use_legacy_identity,
                    )
                )
            entities.extend(
                IneproBusRegisterSensor(
                    bus_coordinator,
                    entry,
                    meter,
                    profile,
                    description,
                    use_legacy_identity=use_legacy_identity,
                )
                for description in profile.measurement_sensors
            )
            entities.extend(
                IneproBusRegisterSensor(
                    bus_coordinator,
                    entry,
                    meter,
                    profile,
                    description,
                    use_legacy_identity=use_legacy_identity,
                )
                for description in profile.diagnostic_sensors
            )

        async_add_entities(entities)
        return

    single_coordinator: IneproMeteringCoordinator = coordinator
    profile = get_profile(entry.data[CONF_FAMILY], entry.data[CONF_VARIANT])
    entities = [
        IneproStatusSensor(single_coordinator, entry, profile),
        IneproLastSuccessfulUpdateSensor(single_coordinator, entry, profile),
        IneproStaticInfoSensor(
            single_coordinator,
            entry,
            profile,
            key="meter_family",
            name="Meter Family",
            value=FAMILY_LABELS[profile.family],
        ),
        IneproStaticInfoSensor(
            single_coordinator,
            entry,
            profile,
            key="meter_model",
            name="Meter Model",
            value=profile.title,
        ),
        IneproStaticInfoSensor(
            single_coordinator,
            entry,
            profile,
            key="transport",
            name="Transport",
            value=TRANSPORT_LABELS[transport],
        ),
    ]
    entities.extend(
        IneproDynamicInfoSensor(
            single_coordinator, entry, profile, field=field, name=name
        )
        for field, name in MODBUS_DEVICE_INFO_SENSORS
    )
    if entry_supports_gateway_management(entry):
        entities.extend(
            IneproGatewayInfoSensor(
                single_coordinator, entry, profile, field=field, name=name
            )
            for field, name in TCP_GATEWAY_INFO_SENSORS
        )
    if profile.family == MeterFamily.GROW:
        entities.append(IneproErrorSummarySensor(single_coordinator, entry, profile))

    entities.extend(
        IneproRegisterSensor(single_coordinator, entry, profile, description)
        for description in profile.measurement_sensors
    )
    entities.extend(
        IneproRegisterSensor(single_coordinator, entry, profile, description)
        for description in profile.diagnostic_sensors
    )
    async_add_entities(entities)


class IneproBaseEntity(CoordinatorEntity[IneproMeteringCoordinator], SensorEntity):
    """Shared base entity for Inepro Metering."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IneproMeteringCoordinator,
        entry: ConfigEntry,
        profile: MeterProfile,
    ) -> None:
        """Initialize the shared entity base."""
        super().__init__(coordinator)
        self._entry = entry
        self._profile = profile

    @property
    def device_info(self) -> DeviceInfo:
        """Return the shared device information."""
        meter = (
            self.coordinator.data.meter if self.coordinator.data is not None else None
        )
        serial_number = (
            None if meter is None else meter.identity.device_serial
        ) or configured_entry_serial(self._entry)

        return DeviceInfo(
            identifiers={
                meter_device_identifier(
                    self._entry,
                    serial_number=(
                        serial_number
                        if entry_supports_gateway_management(self._entry)
                        else configured_entry_serial(self._entry) or serial_number
                    ),
                )
            },
            manufacturer=MANUFACTURER,
            model=(
                self._profile.device_model
                if meter is None or meter.device_identification.product_name is None
                else meter.device_identification.product_name
            ),
            name=self._entry.title,
            configuration_url="https://www.ineprometering.com/",
            serial_number=serial_number,
            sw_version=None if meter is None else meter.firmware.software_version,
            hw_version=None if meter is None else meter.firmware.hardware_version,
            via_device=downstream_meter_via_device(self._entry),
        )


class IneproDiagnosticEntity(IneproBaseEntity):
    """Diagnostic sensors that remain visible during communication failures."""

    @property
    def available(self) -> bool:
        """Keep diagnostic entities visible with their last known state."""
        return True


class IneproGatewayDiagnosticEntity(IneproDiagnosticEntity):
    """Diagnostic sensors bound to the TCP gateway rather than the meter."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information for the gateway endpoint."""
        gateway = (
            self.coordinator.data.gateway if self.coordinator.data is not None else None
        )
        return build_gateway_device_info(
            self._entry,
            name=f"{self._entry.title} Gateway",
            gateway=gateway,
        )


class IneproStatusSensor(IneproDiagnosticEntity):
    """Expose the current polling status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: IneproMeteringCoordinator,
        entry: ConfigEntry,
        profile: MeterProfile,
    ) -> None:
        """Initialize the status sensor."""
        super().__init__(coordinator, entry, profile)
        self._attr_name = "Status"
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str:
        """Return online/offline status based on the last refresh result."""
        return "online" if self.coordinator.last_update_success else "offline"


class IneproLastSuccessfulUpdateSensor(IneproDiagnosticEntity):
    """Expose the last successful poll timestamp."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: IneproMeteringCoordinator,
        entry: ConfigEntry,
        profile: MeterProfile,
    ) -> None:
        """Initialize the timestamp sensor."""
        super().__init__(coordinator, entry, profile)
        self._attr_name = "Last Successful Update"
        self._attr_unique_id = f"{entry.entry_id}_last_successful_update"

    @property
    def native_value(self):
        """Return the timestamp from the latest successful poll."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.last_successful_update


class IneproStaticInfoSensor(IneproDiagnosticEntity):
    """Expose static configuration information as diagnostic sensors."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: IneproMeteringCoordinator,
        entry: ConfigEntry,
        profile: MeterProfile,
        *,
        key: str,
        name: str,
        value: str,
    ) -> None:
        """Initialize the static info sensor."""
        super().__init__(coordinator, entry, profile)
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._value = value

    @property
    def native_value(self) -> str:
        """Return the configured static value."""
        return self._value


class IneproDynamicInfoSensor(IneproDiagnosticEntity):
    """Expose runtime device-identification details from the shared model."""

    def __init__(
        self,
        coordinator: IneproMeteringCoordinator,
        entry: ConfigEntry,
        profile: MeterProfile,
        *,
        field: str,
        name: str,
    ) -> None:
        """Initialize the dynamic info sensor."""
        super().__init__(coordinator, entry, profile)
        self._field = field
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{field}"

    @property
    def native_value(self) -> str | None:
        """Return the latest device-identification value."""
        if self.coordinator.data is None:
            return None
        value = getattr(self.coordinator.data.meter.device_identification, self._field)
        return value if isinstance(value, str) else None


class IneproGatewayInfoSensor(IneproGatewayDiagnosticEntity):
    """Expose runtime TCP gateway details from the shared coordinator data."""

    def __init__(
        self,
        coordinator: IneproMeteringCoordinator,
        entry: ConfigEntry,
        profile: MeterProfile,
        *,
        field: str,
        name: str,
    ) -> None:
        """Initialize the gateway info sensor."""
        super().__init__(coordinator, entry, profile)
        self._field = field
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_gateway_{field}"

    @property
    def native_value(self) -> str | None:
        """Return the latest gateway value."""
        if self.coordinator.data is None or self.coordinator.data.gateway is None:
            return None
        value = getattr(self.coordinator.data.gateway, self._field)
        return value if isinstance(value, str) else None


class IneproErrorSummarySensor(IneproDiagnosticEntity):
    """Expose a friendly decoded GROW error summary."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: IneproMeteringCoordinator,
        entry: ConfigEntry,
        profile: MeterProfile,
    ) -> None:
        """Initialize the decoded GROW error summary sensor."""
        super().__init__(coordinator, entry, profile)
        self._attr_name = "Error Summary"
        self._attr_unique_id = f"{entry.entry_id}_error_summary"

    @property
    def native_value(self) -> str | None:
        """Return the decoded GROW error summary."""
        if self.coordinator.data is None:
            return None
        return format_grow_error_summary(
            self.coordinator.data.meter.readings.get("error_code")
        )


class IneproRegisterSensor(IneproBaseEntity):
    """A register-backed sensor backed by coordinator data."""

    def __init__(
        self,
        coordinator: IneproMeteringCoordinator,
        entry: ConfigEntry,
        profile: MeterProfile,
        description: MeterSensorDescription,
    ) -> None:
        """Initialize a Modbus register sensor."""
        super().__init__(coordinator, entry, profile)
        self._description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = description.name
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_suggested_display_precision = description.suggested_display_precision
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )
        if description.entity_category is not None:
            self._attr_entity_category = EntityCategory(description.entity_category)

    @property
    def available(self) -> bool:
        """Keep diagnostic register entities visible with their last known state."""
        if self._description.entity_category == EntityCategory.DIAGNOSTIC:
            return True
        return super().available

    @property
    def native_value(self) -> str | int | float | None:
        """Return the latest decoded meter value."""
        if self.coordinator.data is None:
            return None

        meter = self.coordinator.data.meter
        readings = meter.readings
        if self._description.key in VERSION_CRC_KEYS:
            return meter.firmware.formatted_version(self._description.key)
        if self._description.key.endswith("version"):
            return format_meter_version_value(readings.get(self._description.key))

        return readings.get(self._description.key)

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Expose CRC context for decoded firmware version sensors."""
        if self.coordinator.data is None:
            return None

        meter = self.coordinator.data.meter
        readings = meter.readings
        if (
            self._description.key == "error_code"
            and self._profile.family == MeterFamily.GROW
        ):
            return _grow_error_attributes(readings)

        if self._description.key not in VERSION_CRC_KEYS:
            return None

        return meter.firmware.version_attributes(self._description.key)


class IneproBusBaseEntity(CoordinatorEntity[IneproSerialBusCoordinator], SensorEntity):
    """Shared base entity for one meter on a serial RTU bus."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IneproSerialBusCoordinator,
        entry: ConfigEntry,
        meter: ConfiguredMeter,
        profile: MeterProfile,
        *,
        use_legacy_identity: bool = False,
    ) -> None:
        """Initialize the shared bus entity base."""
        super().__init__(coordinator)
        self._entry = entry
        self._meter = meter
        self._profile = profile
        self._meter_key = build_meter_key(meter)
        self._use_legacy_identity = use_legacy_identity

    @property
    def _unique_id_prefix(self) -> str:
        """Return the unique-id prefix for this meter."""
        if self._use_legacy_identity:
            return self._entry.entry_id
        return f"{self._entry.entry_id}_{self._meter_key}"

    @property
    def _meter_data(self) -> MeterCoordinatorData | None:
        """Return the latest runtime data for this meter."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.meters.get(self._meter_key)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this meter on the bus."""
        meter_data = self._meter_data
        meter = meter_data.meter if meter_data is not None else None
        serial_number = (
            None if meter is None else meter.identity.device_serial
        ) or self._meter.serial_number

        return DeviceInfo(
            identifiers={
                meter_device_identifier(
                    self._entry,
                    serial_number=self._meter.serial_number or serial_number,
                    fallback_key=(
                        self._entry.entry_id
                        if self._use_legacy_identity
                        else f"{self._entry.entry_id}:{self._meter_key}"
                    ),
                )
            },
            manufacturer=MANUFACTURER,
            model=(
                self._profile.device_model
                if meter is None or meter.device_identification.product_name is None
                else meter.device_identification.product_name
            ),
            name=self._meter.name,
            configuration_url="https://www.ineprometering.com/",
            serial_number=serial_number,
            sw_version=None if meter is None else meter.firmware.software_version,
            hw_version=None if meter is None else meter.firmware.hardware_version,
            via_device=downstream_meter_via_device(self._entry),
        )

    @property
    def available(self) -> bool:
        """Return meter availability from the per-device runtime data."""
        meter_data = self._meter_data
        return meter_data.available if meter_data is not None else False


class IneproBusDiagnosticEntity(IneproBusBaseEntity):
    """Diagnostic sensors that remain visible during communication failures."""

    @property
    def available(self) -> bool:
        """Keep diagnostic bus entities visible with their last known state."""
        return True


class IneproBusGatewayBaseEntity(
    CoordinatorEntity[IneproSerialBusCoordinator],
    SensorEntity,
):
    """Shared base entity for bus-level TCP gateway diagnostics."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: IneproSerialBusCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the shared gateway entity base."""
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return the shared gateway device information."""
        gateway = (
            self.coordinator.data.gateway if self.coordinator.data is not None else None
        )
        return build_gateway_device_info(
            self._entry,
            name=f"{self._entry.title} Gateway",
            gateway=gateway,
        )

    @property
    def available(self) -> bool:
        """Keep bus-level gateway diagnostics visible with last known values."""
        return True


class IneproBusStatusSensor(IneproBusDiagnosticEntity):
    """Expose the current status for one meter on a serial bus."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: IneproSerialBusCoordinator,
        entry: ConfigEntry,
        meter: ConfiguredMeter,
        profile: MeterProfile,
        *,
        use_legacy_identity: bool = False,
    ) -> None:
        """Initialize the status sensor."""
        super().__init__(
            coordinator,
            entry,
            meter,
            profile,
            use_legacy_identity=use_legacy_identity,
        )
        self._attr_name = "Status"
        self._attr_unique_id = f"{self._unique_id_prefix}_status"

    @property
    def native_value(self) -> str:
        """Return online/offline status based on the last per-meter refresh result."""
        meter_data = self._meter_data
        return (
            "online" if meter_data is not None and meter_data.available else "offline"
        )


class IneproBusGatewayInfoSensor(IneproBusGatewayBaseEntity):
    """Expose bus-level TCP gateway details from the coordinator."""

    def __init__(
        self,
        coordinator: IneproSerialBusCoordinator,
        entry: ConfigEntry,
        *,
        field: str,
        name: str,
    ) -> None:
        """Initialize the bus gateway info sensor."""
        super().__init__(coordinator, entry)
        self._field = field
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_gateway_{field}"

    @property
    def native_value(self) -> str | None:
        """Return the latest bus gateway value."""
        if self.coordinator.data is None or self.coordinator.data.gateway is None:
            return None
        value = getattr(self.coordinator.data.gateway, self._field)
        return value if isinstance(value, str) else None


class IneproBusLastSuccessfulUpdateSensor(IneproBusDiagnosticEntity):
    """Expose the last successful poll timestamp for one meter on the bus."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: IneproSerialBusCoordinator,
        entry: ConfigEntry,
        meter: ConfiguredMeter,
        profile: MeterProfile,
        *,
        use_legacy_identity: bool = False,
    ) -> None:
        """Initialize the timestamp sensor."""
        super().__init__(
            coordinator,
            entry,
            meter,
            profile,
            use_legacy_identity=use_legacy_identity,
        )
        self._attr_name = "Last Successful Update"
        self._attr_unique_id = f"{self._unique_id_prefix}_last_successful_update"

    @property
    def native_value(self):
        """Return the latest successful timestamp for this meter."""
        meter_data = self._meter_data
        if meter_data is None:
            return None
        return meter_data.last_successful_update


class IneproBusStaticInfoSensor(IneproBusDiagnosticEntity):
    """Expose static configuration information for one bus meter."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: IneproSerialBusCoordinator,
        entry: ConfigEntry,
        meter: ConfiguredMeter,
        profile: MeterProfile,
        *,
        use_legacy_identity: bool = False,
        key: str,
        name: str,
        value: str,
    ) -> None:
        """Initialize the static info sensor."""
        super().__init__(
            coordinator,
            entry,
            meter,
            profile,
            use_legacy_identity=use_legacy_identity,
        )
        self._attr_name = name
        self._attr_unique_id = f"{self._unique_id_prefix}_{key}"
        self._value = value

    @property
    def native_value(self) -> str:
        """Return the configured static value."""
        return self._value


class IneproBusDynamicInfoSensor(IneproBusDiagnosticEntity):
    """Expose runtime device-identification details for one bus meter."""

    def __init__(
        self,
        coordinator: IneproSerialBusCoordinator,
        entry: ConfigEntry,
        meter: ConfiguredMeter,
        profile: MeterProfile,
        *,
        field: str,
        name: str,
        use_legacy_identity: bool = False,
    ) -> None:
        """Initialize the dynamic bus info sensor."""
        super().__init__(
            coordinator,
            entry,
            meter,
            profile,
            use_legacy_identity=use_legacy_identity,
        )
        self._field = field
        self._attr_name = name
        self._attr_unique_id = f"{self._unique_id_prefix}_{field}"

    @property
    def native_value(self) -> str | None:
        """Return the latest device-identification value for this meter."""
        meter_data = self._meter_data
        if meter_data is None:
            return None
        value = getattr(meter_data.meter.device_identification, self._field)
        return value if isinstance(value, str) else None


class IneproBusErrorSummarySensor(IneproBusDiagnosticEntity):
    """Expose a friendly decoded GROW error summary for one bus meter."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: IneproSerialBusCoordinator,
        entry: ConfigEntry,
        meter: ConfiguredMeter,
        profile: MeterProfile,
        *,
        use_legacy_identity: bool = False,
    ) -> None:
        """Initialize the decoded GROW error summary bus sensor."""
        super().__init__(
            coordinator,
            entry,
            meter,
            profile,
            use_legacy_identity=use_legacy_identity,
        )
        self._attr_name = "Error Summary"
        self._attr_unique_id = f"{self._unique_id_prefix}_error_summary"

    @property
    def native_value(self) -> str | None:
        """Return the decoded GROW error summary for this meter."""
        meter_data = self._meter_data
        if meter_data is None:
            return None
        return format_grow_error_summary(meter_data.meter.readings.get("error_code"))


class IneproBusRegisterSensor(IneproBusBaseEntity):
    """A register-backed sensor for one meter on a serial bus."""

    def __init__(
        self,
        coordinator: IneproSerialBusCoordinator,
        entry: ConfigEntry,
        meter: ConfiguredMeter,
        profile: MeterProfile,
        description: MeterSensorDescription,
        *,
        use_legacy_identity: bool = False,
    ) -> None:
        """Initialize one serial-bus register sensor."""
        super().__init__(
            coordinator,
            entry,
            meter,
            profile,
            use_legacy_identity=use_legacy_identity,
        )
        self._description = description
        self._attr_unique_id = f"{self._unique_id_prefix}_{description.key}"
        self._attr_name = description.name
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_suggested_display_precision = description.suggested_display_precision
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )
        if description.entity_category is not None:
            self._attr_entity_category = EntityCategory(description.entity_category)

    @property
    def available(self) -> bool:
        """Keep diagnostic register entities visible with their last known state."""
        if self._description.entity_category == EntityCategory.DIAGNOSTIC:
            return True
        meter_data = self._meter_data
        return meter_data.available if meter_data is not None else False

    @property
    def native_value(self) -> str | int | float | None:
        """Return the latest decoded value for this meter."""
        meter_data = self._meter_data
        if meter_data is None:
            return None

        meter = meter_data.meter
        readings = meter.readings
        if self._description.key in VERSION_CRC_KEYS:
            return meter.firmware.formatted_version(self._description.key)
        if self._description.key.endswith("version"):
            return format_meter_version_value(readings.get(self._description.key))

        return readings.get(self._description.key)

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Expose CRC context for decoded firmware version sensors."""
        meter_data = self._meter_data
        if meter_data is None:
            return None

        meter = meter_data.meter
        readings = meter.readings
        if (
            self._description.key == "error_code"
            and self._profile.family == MeterFamily.GROW
        ):
            return _grow_error_attributes(readings)

        if self._description.key not in VERSION_CRC_KEYS:
            return None

        return meter.firmware.version_attributes(self._description.key)
