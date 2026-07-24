"""Sensor platform for the Powersensor integration.

Each physical Powersensor device (magnetic sensor, water sensor, smart plug) pushes
data to the integration over UDP via a Powersensor plug.  A single logical
"Virtual Household" device aggregates readings from mains and solar magnetic sensor
into whole-home power/energy figures.

Entity descriptions are declared as module-level tuples so the entity classes
themselves stay thin — each class simply reads ``entity_description`` fields
rather than containing dispatch logic.
"""

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from powersensor_local import VirtualHousehold

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import (
    CFG_ROLES,
    CREATE_PLUG_SIGNAL,
    CREATE_SENSOR_SIGNAL,
    DATA_UPDATE_SIGNAL_PREFIX,
    DOMAIN,
    ROLE_APPLIANCE,
    ROLE_HOUSENET,
    ROLE_SOLAR,
    ROLE_UPDATE_SIGNAL,
    ROLE_WATER,
    UPDATE_VHH_SIGNAL,
)
from .models import (
    PowersensorConfigEntry,
    PowersensorRuntimeData,
    PowersensorVirtualHouseholdState,
)
from .powersensor_message_dispatcher import PowersensorMessageDispatcher

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _volts_to_battery_pct(volts: float) -> float:
    """Convert a battery voltage reading to a percentage (3.3 V = 0 %, 4.15 V = 100 %)."""
    return max(min(100.0 * (volts - 3.3) / 0.85, 100), 0)


def _joules_to_kwh(joules: float) -> float:
    """Convert watt-seconds (joules) to kilowatt-hours."""
    return joules / 3_600_000.0


# ---------------------------------------------------------------------------
# Entity descriptions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class PowersensorSensorEntityDescription(SensorEntityDescription):
    """Describes a single measurement entity for an electricity/water sensor or plug.

    Attributes:
        conversion_function: Optional transform applied to the raw message value.
        event:               Required dispatcher event name this entity subscribes to.
        message_key:         Required key inside the event payload that carries the value.
        supported_roles:     When set, this entity is only created for sensors whose
                             role is in this set.  None means all roles.
    """

    event: str
    message_key: str
    conversion_function: Callable[[float], float] | None = None
    supported_roles: frozenset[str] | None = None


@dataclass(frozen=True, kw_only=True)
class PowersensorVirtualHouseholdSensorEntityDescription(SensorEntityDescription):
    """Entity description for a Virtual Household aggregated sensor.

    Attributes:
        formatter:   Function applied to the raw value before storing as state.
        event:       The VirtualHousehold event name this entity subscribes to.
        message_key: The key inside the VirtualHousehold event payload.
    """

    event: str
    message_key: str
    formatter: Callable[[float], int | float] = field(default=int)


# ---------------------------------------------------------------------------
# Module-level description tuples
# ---------------------------------------------------------------------------

SENSOR_DESCRIPTIONS: tuple[PowersensorSensorEntityDescription, ...] = (
    PowersensorSensorEntityDescription(
        key="battery_level",
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        event="battery_level",
        message_key="volts",
        conversion_function=_volts_to_battery_pct,
    ),
    PowersensorSensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        event="average_power",
        message_key="watts",
        supported_roles=frozenset({ROLE_HOUSENET, ROLE_SOLAR, ROLE_APPLIANCE}),
    ),
    PowersensorSensorEntityDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        # TOTAL (not TOTAL_INCREASING) is intentional: magnetic sensors do net
        # metering, so the cumulative joule value can decrease (e.g. a solar
        # sensor exporting more than it imports).  TOTAL with last_reset=None
        # is the HA-recommended state class for a lifetime counter that never
        # resets but can go up or down; HA statistics tracks deltas from the
        # first observed value.
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        event="summation_energy",
        message_key="summation_joules",
        conversion_function=_joules_to_kwh,
        supported_roles=frozenset({ROLE_HOUSENET, ROLE_SOLAR, ROLE_APPLIANCE}),
    ),
    PowersensorSensorEntityDescription(
        key="device_role",
        translation_key="device_role",
        device_class=SensorDeviceClass.ENUM,
        options=["appliance", "house_net", "solar", "unknown", "water"],
        entity_category=EntityCategory.DIAGNOSTIC,
        event="role",
        message_key="role",
    ),
    PowersensorSensorEntityDescription(
        key="rssi_ble",
        translation_key="rssi_ble",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        event="radio_signal_quality",
        message_key="average_rssi",
    ),
    PowersensorSensorEntityDescription(
        key="water_flow_rate",
        translation_key="water_flow_rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        suggested_display_precision=1,
        event="average_flow",
        message_key="litres_per_minute",
        supported_roles=frozenset({ROLE_WATER}),
    ),
    PowersensorSensorEntityDescription(
        key="total_water_consumption",
        translation_key="total_water_consumption",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=2,
        event="summation_volume",
        message_key="summation_litres",
        supported_roles=frozenset({ROLE_WATER}),
    ),
)

PLUG_DESCRIPTIONS: tuple[PowersensorSensorEntityDescription, ...] = (
    PowersensorSensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        event="average_power",
        message_key="watts",
    ),
    PowersensorSensorEntityDescription(
        key="volts",
        translation_key="volts",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        event="average_power_components",
        message_key="volts",
        entity_registry_enabled_default=False,
    ),
    PowersensorSensorEntityDescription(
        key="apparent_current",
        translation_key="apparent_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        event="average_power_components",
        message_key="apparent_current",
        entity_registry_enabled_default=False,
    ),
    PowersensorSensorEntityDescription(
        key="active_current",
        translation_key="active_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        event="average_power_components",
        message_key="active_current",
        entity_registry_enabled_default=False,
    ),
    PowersensorSensorEntityDescription(
        key="reactive_current",
        translation_key="reactive_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        event="average_power_components",
        message_key="reactive_current",
        entity_registry_enabled_default=False,
    ),
    PowersensorSensorEntityDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        # TOTAL_INCREASING (not TOTAL) is intentional: smart plugs measure
        # load-side consumption only.  Unlike the magnetic sensors,
        # plugs cannot measure reverse flow — their cumulative joule counter
        # is guaranteed monotonically increasing.  TOTAL_INCREASING allows
        # HA to detect meter resets and is the correct class for the Energy
        # dashboard.  Contrast with the magnetic sensor's total_energy
        # (SENSOR_DESCRIPTIONS above) which uses TOTAL because net metering
        # means the cumulative value can decrease.
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        event="summation_energy",
        message_key="summation_joules",
        conversion_function=_joules_to_kwh,
    ),
    PowersensorSensorEntityDescription(
        key="device_role",
        translation_key="device_role",
        device_class=SensorDeviceClass.ENUM,
        options=["appliance", "house_net", "solar", "unknown", "water"],
        entity_category=EntityCategory.DIAGNOSTIC,
        event="role",
        message_key="role",
    ),
)

# Consumption (mains-only) VHH entities — always created when a house-net sensor exists.
CONSUMPTION_DESCRIPTIONS: tuple[
    PowersensorVirtualHouseholdSensorEntityDescription, ...
] = (
    PowersensorVirtualHouseholdSensorEntityDescription(
        key="power_home_use",
        translation_key="power_home_use",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        formatter=int,
        event="home_usage",
        message_key="watts",
    ),
    PowersensorVirtualHouseholdSensorEntityDescription(
        key="power_from_grid",
        translation_key="power_from_grid",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        formatter=int,
        event="from_grid",
        message_key="watts",
    ),
    PowersensorVirtualHouseholdSensorEntityDescription(
        key="energy_home_use",
        translation_key="energy_home_use",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        formatter=_joules_to_kwh,
        event="home_usage_summation",
        message_key="summation_joules",
    ),
    PowersensorVirtualHouseholdSensorEntityDescription(
        key="energy_from_grid",
        translation_key="energy_from_grid",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        formatter=_joules_to_kwh,
        event="from_grid_summation",
        message_key="summation_joules",
    ),
)

# Production (solar) VHH entities — only created when a solar sensor exists.
PRODUCTION_DESCRIPTIONS: tuple[
    PowersensorVirtualHouseholdSensorEntityDescription, ...
] = (
    PowersensorVirtualHouseholdSensorEntityDescription(
        key="power_to_grid",
        translation_key="power_to_grid",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        formatter=int,
        event="to_grid",
        message_key="watts",
    ),
    PowersensorVirtualHouseholdSensorEntityDescription(
        key="power_solar_generation",
        translation_key="power_solar_generation",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        formatter=int,
        event="solar_generation",
        message_key="watts",
    ),
    PowersensorVirtualHouseholdSensorEntityDescription(
        key="energy_to_grid",
        translation_key="energy_to_grid",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        formatter=_joules_to_kwh,
        event="to_grid_summation",
        message_key="summation_joules",
    ),
    PowersensorVirtualHouseholdSensorEntityDescription(
        key="energy_solar_generation",
        translation_key="energy_solar_generation",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        formatter=_joules_to_kwh,
        event="solar_generation_summation",
        message_key="summation_joules",
    ),
)


# ---------------------------------------------------------------------------
# Base entity
# ---------------------------------------------------------------------------


class PowersensorEntity(SensorEntity):
    """Base class for all Powersensor sensor entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        config_entry_id: str,
        mac: str,
        role: str | None,
        description: PowersensorSensorEntityDescription,
        timeout_seconds: int = 60,
    ) -> None:
        """Initialize the entity."""
        self._role: str | None = role
        self._has_recently_received_update_message = False
        self._attr_native_value = None
        self._config_entry_id = config_entry_id
        self._mac = mac
        self._remove_unavailability_tracker: Callable[[], None] | None = None
        self._timeout = timedelta(seconds=timeout_seconds)

        self.entity_description: PowersensorSensorEntityDescription = description
        self._attr_unique_id = f"{mac}_{description.key}"
        self._signal = f"{DATA_UPDATE_SIGNAL_PREFIX}{mac}_{description.event}"

    @property
    @abstractmethod
    def device_info(self) -> DeviceInfo:
        """Return device info. Subclasses must implement."""

    @property
    def available(self) -> bool:
        """Return True when at least one update has been received recently."""
        return self._has_recently_received_update_message

    def _schedule_unavailable(self) -> None:
        """(Re-)schedule the unavailability timer."""
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()
        self._remove_unavailability_tracker = async_call_later(
            self.hass,
            self._timeout.total_seconds(),
            self._async_make_unavailable,
        )

    @callback
    def _async_make_unavailable(self, _now: datetime) -> None:
        """Mark entity as unavailable when the timeout fires."""
        self._has_recently_received_update_message = False
        self.async_write_ha_state()

    def _cancel_unavailability_tracker(self) -> None:
        """Cancel the unavailability timer if one is scheduled."""
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()
            self._remove_unavailability_tracker = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to the data-update signal and register the unavailability timer.

        Subclasses that need additional subscriptions (e.g. ROLE_UPDATE_SIGNAL)
        should call ``await super().async_added_to_hass()`` first and then add
        their own ``async_on_remove`` registrations.
        """
        self._has_recently_received_update_message = False
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_update)
        )
        self.async_on_remove(self._cancel_unavailability_tracker)

    @callback
    def _handle_update(self, event: str | None, message: dict[str, Any]) -> None:
        """Handle a pushed data update from the dispatcher."""
        self._has_recently_received_update_message = True

        desc = self.entity_description
        if desc.message_key in message:
            raw = message[desc.message_key]
            if desc.conversion_function:
                self._attr_native_value = desc.conversion_function(raw)
            elif desc.key == "device_role":
                # State translation keys must be snake_case.  The wire value
                # "house-net" is normalised to "house_net" so it matches the
                # key in strings.json.  All other role strings are already valid.
                # None means the sensor has no role yet; map to "unknown" so the
                # entity always has a valid translation key rather than a None state.
                if raw is None:
                    self._attr_native_value = "unknown"
                else:
                    self._attr_native_value = raw.replace("-", "_")
            else:
                self._attr_native_value = raw

        self._schedule_unavailable()
        self.async_write_ha_state()


# ---------------------------------------------------------------------------
# Electricity / water sensor entity
# ---------------------------------------------------------------------------


class PowersensorSensorEntity(PowersensorEntity):
    """Entity representing a single measurement from a Powersensor electricity/water sensor."""

    def __init__(
        self,
        entry_id: str,
        mac: str,
        role: str | None,
        description: PowersensorSensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(entry_id, mac, role, description)
        self._current_translation_key: str | None = self._get_translation_key()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor hardware unit."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            manufacturer="Powersensor",
            model="PowersensorSensor",
            translation_key=self._current_translation_key,
            translation_placeholders={"id": self._mac},
        )

    def _get_translation_key(self) -> str | None:
        return {
            ROLE_HOUSENET: "mains_sensor",
            ROLE_SOLAR: "solar_sensor",
            ROLE_WATER: "water_sensor",
            ROLE_APPLIANCE: "appliance_sensor",
            None: "unknown_sensor",
        }.get(self._role, "unknown_sensor")

    @callback
    def _handle_role_update(self, mac: str, role: str | None) -> None:
        """Handle a role update, refreshing the device registry translation key."""
        if self._mac != mac or self._role == role:
            return
        self._role = role
        self._current_translation_key = self._get_translation_key()
        device_registry = dr.async_get(self.hass)
        info = self.device_info
        device_registry.async_get_or_create(
            config_entry_id=self._config_entry_id,
            identifiers={(DOMAIN, self._mac)},
            translation_key=info.get("translation_key"),
            translation_placeholders=info.get("translation_placeholders"),
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to data-update signal and also ROLE_UPDATE_SIGNAL.

        Sensors can change role at runtime (e.g. when first assigned via the
        app), so they need the role-update subscription in addition to the
        common data-update subscription provided by the base class.
        """
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, ROLE_UPDATE_SIGNAL, self._handle_role_update
            )
        )


# ---------------------------------------------------------------------------
# Smart plug entity
# ---------------------------------------------------------------------------


class PowersensorPlugEntity(PowersensorEntity):
    """Entity representing a single measurement from a Powersensor smart plug."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this smart plug."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            manufacturer="Powersensor",
            model="PowersensorPlug",
            translation_key="plug",
            translation_placeholders={"id": self._mac},
        )


# ---------------------------------------------------------------------------
# Virtual Household entity
# ---------------------------------------------------------------------------


class PowersensorHouseholdEntity(SensorEntity):
    """Sensor entity backed by the Powersensor VirtualHousehold calculation engine."""

    # Household entities are always considered available because VirtualHousehold
    # is a pure in-process calculation layer.  If the underlying devices go offline,
    # their own entities become unavailable — marking the VHH unavailable too would
    # cause unnecessary dashboard churn.
    _attr_available = True
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        vhh: VirtualHousehold,
        description: PowersensorVirtualHouseholdSensorEntityDescription,
    ) -> None:
        """Initialize the virtual household entity."""
        self._vhh = vhh
        self.entity_description: PowersensorVirtualHouseholdSensorEntityDescription = (
            description
        )
        self._attr_unique_id = f"{DOMAIN}_vhh_{description.event}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the virtual household device."""
        return DeviceInfo(
            identifiers={(DOMAIN, "vhh")},
            manufacturer="Powersensor",
            model="Virtual",
            translation_key="virtual_household_view",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to VirtualHousehold events."""
        desc = self.entity_description
        self.async_on_remove(lambda: self._vhh.unsubscribe(desc.event, self._on_event))
        self._vhh.subscribe(desc.event, self._on_event)

    async def _on_event(self, _event: str, msg: dict[str, Any]) -> None:
        """Handle a VirtualHousehold update.

        Must be ``async def``: VirtualHousehold.subscribe awaits every registered
        callback, so a synchronous function would silently produce no result.
        """
        desc = self.entity_description
        if (val := msg.get(desc.message_key)) is not None:
            self._attr_native_value = desc.formatter(val)
            self.async_write_ha_state()


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowersensorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all Powersensor sensor entities for a config entry."""
    runtime: PowersensorRuntimeData = entry.runtime_data
    vhh: VirtualHousehold = runtime.vhh
    dispatcher: PowersensorMessageDispatcher = runtime.dispatcher

    # Tracks which VHH entity groups have been added this session.
    # Reset on every reload since this is a closure-local, not RuntimeData.
    vhh_state = PowersensorVirtualHouseholdState()

    # Tracks which role-gated sensor entities have been created, keyed by
    # (mac, description.key).  Used only to prevent handle_role_update from
    # re-adding entities that handle_discovered_sensor already created.
    role_entities_added: set[tuple[str, str]] = set()

    entry_id = entry.entry_id

    # ------------------------------------------------------------------
    # Role update handling
    # ------------------------------------------------------------------

    @callback
    def handle_role_update(mac_address: str, new_role: str | None) -> None:
        """Persist role changes and trigger a VHH refresh when needed."""
        existing_roles: dict[str, str | None] = dict(entry.data.get(CFG_ROLES, {}))
        old_role = existing_roles.get(mac_address)

        if old_role == new_role:
            return

        _LOGGER.debug("Updating role for %s: %s → %s", mac_address, old_role, new_role)
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CFG_ROLES: {**existing_roles, mac_address: new_role}},
        )

        if mac_address in dispatcher.plugs:
            # Plugs always have ROLE_APPLIANCE — no entity creation needed here.
            return

        # Keep the dispatcher's in-memory role cache in sync.  When a role
        # arrives via the reconfigure flow the dispatcher itself never sees a
        # measurement event for it, so its sensors dict still holds the old
        # (possibly None) value.  update_virtual_household_entities reads
        # dispatcher.sensors.values() to decide whether to create VHH entities,
        # so if this isn't updated now those entities won't be created until the
        # next measurement arrives.
        if mac_address in dispatcher.sensors:
            dispatcher.sensors[mac_address] = new_role

        if new_role in (ROLE_SOLAR, ROLE_HOUSENET):
            async_dispatcher_send(hass, UPDATE_VHH_SIGNAL)

        # Create any role-gated entities not present at initial discovery
        # (e.g. power/energy when a sensor is assigned ROLE_HOUSENET/ROLE_SOLAR,
        # or flow/volume when assigned ROLE_WATER).
        new_entities = [
            PowersensorSensorEntity(entry_id, mac_address, new_role, desc)
            for desc in SENSOR_DESCRIPTIONS
            if desc.supported_roles is not None
            and new_role in desc.supported_roles
            and (mac_address, desc.key) not in role_entities_added
        ]
        if new_entities:
            _LOGGER.debug(
                "Adding %d role-specific entities for %s (role=%s)",
                len(new_entities),
                mac_address,
                new_role,
            )
            for e in new_entities:
                role_entities_added.add((mac_address, e.entity_description.key))
            async_add_entities(new_entities, False)

    entry.async_on_unload(
        async_dispatcher_connect(hass, ROLE_UPDATE_SIGNAL, handle_role_update)
    )

    # ------------------------------------------------------------------
    # Sensor discovery
    # ------------------------------------------------------------------

    @callback
    def handle_discovered_sensor(sensor_mac: str, sensor_role: str | None) -> None:
        """Create entities for a newly discovered sensor."""
        new_sensors = [
            PowersensorSensorEntity(entry_id, sensor_mac, sensor_role, desc)
            for desc in SENSOR_DESCRIPTIONS
            if desc.supported_roles is None or sensor_role in desc.supported_roles
        ]

        # Pre-populate role_entities_added so handle_role_update — which fires
        # shortly after via ROLE_UPDATE_SIGNAL — doesn't add duplicates.
        for e in new_sensors:
            if e.entity_description.supported_roles is not None:
                role_entities_added.add((sensor_mac, e.entity_description.key))

        async_add_entities(new_sensors, False)

        if sensor_role in (ROLE_HOUSENET, ROLE_SOLAR):
            async_dispatcher_send(hass, UPDATE_VHH_SIGNAL)

    entry.async_on_unload(
        async_dispatcher_connect(hass, CREATE_SENSOR_SIGNAL, handle_discovered_sensor)
    )

    # ------------------------------------------------------------------
    # Plug discovery
    # ------------------------------------------------------------------

    @callback
    def handle_discovered_plug(plug_mac: str) -> None:
        """Create entities for a newly discovered plug."""
        _LOGGER.debug("Plug discovered: %s", plug_mac)
        async_add_entities(
            [
                PowersensorPlugEntity(entry_id, plug_mac, ROLE_APPLIANCE, desc)
                for desc in PLUG_DESCRIPTIONS
            ],
            False,
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, CREATE_PLUG_SIGNAL, handle_discovered_plug)
    )

    # ------------------------------------------------------------------
    # Virtual Household
    # ------------------------------------------------------------------

    @callback
    def update_virtual_household_entities() -> None:
        """Add VHH sensor entities once the required sensor roles are present.

        Called at startup and whenever a sensor role changes to ROLE_HOUSENET
        or ROLE_SOLAR.

        VirtualHousehold automatically enables solar processing when it first
        receives a solar-role event (see VirtualHousehold.process_average_power_event),
        so no reload is needed when a solar sensor is discovered mid-session.
        """
        has_mains = any(role == ROLE_HOUSENET for role in dispatcher.sensors.values())
        has_solar = any(role == ROLE_SOLAR for role in dispatcher.sensors.values())

        if not has_mains:
            _LOGGER.debug("No house-net sensor yet; VHH not operational")
            return

        if not vhh_state.mains_added:
            _LOGGER.debug("Enabling mains components in virtual household")
            async_add_entities(
                [
                    PowersensorHouseholdEntity(vhh, desc)
                    for desc in CONSUMPTION_DESCRIPTIONS
                ],
                False,
            )
            vhh_state.mains_added = True

        if has_solar and not vhh_state.solar_added:
            _LOGGER.debug("Enabling solar components in virtual household")
            async_add_entities(
                [
                    PowersensorHouseholdEntity(vhh, desc)
                    for desc in PRODUCTION_DESCRIPTIONS
                ],
                False,
            )
            vhh_state.solar_added = True

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, UPDATE_VHH_SIGNAL, update_virtual_household_entities
        )
    )

    update_virtual_household_entities()
