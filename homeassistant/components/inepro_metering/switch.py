"""Switch platform for Inepro Metering."""

from inepro_metering.gateway_settings import (
    GatewaySettingDescription,
    get_gateway_settings,
)
from inepro_metering.settings import WritableSettingDescription, get_writable_settings

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_FAMILY, CONF_SLAVE_ID, CONF_VARIANT, MANUFACTURER
from .coordinator import IneproMeteringCoordinator, IneproSerialBusCoordinator
from .device_identity import configured_entry_serial, meter_device_identifier
from .entry_data import (
    ConfiguredMeter,
    build_meter_key,
    get_configured_meters,
    is_bus_entry,
)
from .gateway_support import (
    IneproGatewayEntity,
    downstream_meter_via_device,
    entry_supports_gateway_management,
)
from .models import MeterProfile, get_profile, get_profile_for_variant


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Inepro Metering switches from a config entry."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = []

    if entry_supports_gateway_management(entry):
        entities.extend(
            IneproGatewaySwitch(coordinator, entry, setting)
            for setting in get_gateway_settings(entity_platform="switch")
        )

    if is_bus_entry(entry.data):
        bus_coordinator: IneproSerialBusCoordinator = coordinator
        configured_meters = get_configured_meters(entry.data, title=entry.title)
        primary_meter = configured_meters[0] if configured_meters else None

        for meter in configured_meters:
            profile = get_profile_for_variant(meter.variant)
            use_legacy_identity = meter == primary_meter
            entities.extend(
                IneproBusWritableSwitch(
                    bus_coordinator,
                    entry,
                    meter,
                    profile,
                    setting,
                    use_legacy_identity=use_legacy_identity,
                )
                for setting in get_writable_settings(profile, entity_platform="switch")
            )

        async_add_entities(entities)
        return

    single_coordinator: IneproMeteringCoordinator = coordinator
    profile = get_profile(entry.data[CONF_FAMILY], entry.data[CONF_VARIANT])
    settings = get_writable_settings(profile, entity_platform="switch")
    if not settings and not entities:
        return

    entities.extend(
        IneproWritableSwitch(single_coordinator, entry, profile, setting)
        for setting in settings
    )
    async_add_entities(entities)


class IneproGatewaySwitch(
    IneproGatewayEntity,
    SwitchEntity,
):
    """Expose one shared-library gateway switch setting."""

    def __init__(
        self,
        coordinator: IneproMeteringCoordinator | IneproSerialBusCoordinator,
        entry: ConfigEntry,
        setting: GatewaySettingDescription,
    ) -> None:
        """Initialize the gateway switch entity."""
        super().__init__(coordinator, entry)
        self._setting = setting
        self._optimistic_value: bool | None = None
        self._attr_name = setting.name
        self._attr_unique_id = f"{entry.entry_id}_gateway_{setting.key}_switch"

    @property
    def is_on(self) -> bool | None:
        """Return the current logical gateway setting state."""
        actual_value: bool | None = None
        state = self.gateway_setting_state(self._setting.key)
        if state is not None and state.value is not None:
            actual_value = bool(state.value)

        if actual_value is not None and self._optimistic_value == actual_value:
            self._optimistic_value = None

        return (
            self._optimistic_value
            if self._optimistic_value is not None
            else actual_value
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the gateway setting."""
        del kwargs
        self._optimistic_value = True
        self.async_write_ha_state()
        try:
            await self.coordinator.async_write_gateway_setting(
                setting_key=self._setting.key,
                value=True,
            )
            await self.coordinator.async_request_refresh()
        except Exception:
            self._optimistic_value = None
            self.async_write_ha_state()
            raise
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the gateway setting."""
        del kwargs
        self._optimistic_value = False
        self.async_write_ha_state()
        try:
            await self.coordinator.async_write_gateway_setting(
                setting_key=self._setting.key,
                value=False,
            )
            await self.coordinator.async_request_refresh()
        except Exception:
            self._optimistic_value = None
            self.async_write_ha_state()
            raise
        self.async_write_ha_state()


class IneproWritableSwitch(
    CoordinatorEntity[IneproMeteringCoordinator],
    SwitchEntity,
):
    """Expose one shared-library writable switch for a single-meter entry."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IneproMeteringCoordinator,
        entry: ConfigEntry,
        profile: MeterProfile,
        setting: WritableSettingDescription,
    ) -> None:
        """Initialize the shared writable switch."""
        super().__init__(coordinator)
        self._entry = entry
        self._profile = profile
        self._setting = setting
        self._optimistic_value: bool | None = None
        self._attr_name = setting.name
        self._attr_unique_id = f"{entry.entry_id}_{setting.key}_switch"

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

    @property
    def is_on(self) -> bool | None:
        """Return the current logical setting state."""
        actual_value: bool | None = None
        if self.coordinator.data is None:
            return self._optimistic_value
        state = self.coordinator.data.meter.writable_settings.get(self._setting.key)
        if state is not None and state.value is not None:
            actual_value = bool(state.value)

        if actual_value is not None and self._optimistic_value == actual_value:
            self._optimistic_value = None

        return (
            self._optimistic_value
            if self._optimistic_value is not None
            else actual_value
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the logical setting on the meter."""
        self._optimistic_value = True
        self.async_write_ha_state()
        try:
            await self.coordinator.async_write_setting(
                profile=self._profile,
                slave_id=int(self._entry.data[CONF_SLAVE_ID]),
                setting_key=self._setting.key,
                value=True,
            )
            await self.coordinator.async_request_refresh()
        except Exception:
            self._optimistic_value = None
            self.async_write_ha_state()
            raise
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the logical setting on the meter."""
        self._optimistic_value = False
        self.async_write_ha_state()
        try:
            await self.coordinator.async_write_setting(
                profile=self._profile,
                slave_id=int(self._entry.data[CONF_SLAVE_ID]),
                setting_key=self._setting.key,
                value=False,
            )
            await self.coordinator.async_request_refresh()
        except Exception:
            self._optimistic_value = None
            self.async_write_ha_state()
            raise
        self.async_write_ha_state()


class IneproBusWritableSwitch(
    CoordinatorEntity[IneproSerialBusCoordinator],
    SwitchEntity,
):
    """Expose one shared-library writable switch for a bus meter."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IneproSerialBusCoordinator,
        entry: ConfigEntry,
        meter: ConfiguredMeter,
        profile: MeterProfile,
        setting: WritableSettingDescription,
        *,
        use_legacy_identity: bool = False,
    ) -> None:
        """Initialize the shared writable bus switch."""
        super().__init__(coordinator)
        self._entry = entry
        self._meter = meter
        self._profile = profile
        self._setting = setting
        self._meter_key = build_meter_key(meter)
        self._use_legacy_identity = use_legacy_identity
        self._optimistic_value: bool | None = None
        self._attr_name = setting.name
        self._attr_unique_id = f"{self._unique_id_prefix}_{setting.key}_switch"

    @property
    def _unique_id_prefix(self) -> str:
        """Return the unique-id prefix for this meter."""
        if self._use_legacy_identity:
            return self._entry.entry_id
        return f"{self._entry.entry_id}_{self._meter_key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this meter on the bus."""
        meter_data = (
            self.coordinator.data.meters.get(self._meter_key)
            if self.coordinator.data is not None
            else None
        )
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
        if self.coordinator.data is None:
            return False
        meter_data = self.coordinator.data.meters.get(self._meter_key)
        return meter_data.available if meter_data is not None else False

    @property
    def is_on(self) -> bool | None:
        """Return the current logical setting state."""
        actual_value: bool | None = None
        if self.coordinator.data is None:
            return self._optimistic_value
        meter_data = self.coordinator.data.meters.get(self._meter_key)
        if meter_data is None:
            return self._optimistic_value
        state = meter_data.meter.writable_settings.get(self._setting.key)
        if state is not None and state.value is not None:
            actual_value = bool(state.value)

        if actual_value is not None and self._optimistic_value == actual_value:
            self._optimistic_value = None

        return (
            self._optimistic_value
            if self._optimistic_value is not None
            else actual_value
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the logical setting on this bus meter."""
        self._optimistic_value = True
        self.async_write_ha_state()
        try:
            await self.coordinator.async_write_setting(
                profile=self._profile,
                slave_id=self._meter.slave_id,
                setting_key=self._setting.key,
                value=True,
            )
            await self.coordinator.async_request_refresh()
        except Exception:
            self._optimistic_value = None
            self.async_write_ha_state()
            raise
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the logical setting on this bus meter."""
        self._optimistic_value = False
        self.async_write_ha_state()
        try:
            await self.coordinator.async_write_setting(
                profile=self._profile,
                slave_id=self._meter.slave_id,
                setting_key=self._setting.key,
                value=False,
            )
            await self.coordinator.async_request_refresh()
        except Exception:
            self._optimistic_value = None
            self.async_write_ha_state()
            raise
        self.async_write_ha_state()
