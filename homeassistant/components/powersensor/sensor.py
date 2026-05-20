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
    PLUG_ADDED_TO_HA_SIGNAL,
    ROLE_APPLIANCE,
    ROLE_HOUSENET,
    ROLE_SOLAR,
    ROLE_UPDATE_SIGNAL,
    ROLE_WATER,
    SENSOR_ADDED_TO_HA_SIGNAL,
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
        entity_category=EntityCategory.DIAGNOSTIC,
        event="role",
        message_key="role",
    ),
)

HOUSEHOLD_DESCRIPTIONS: tuple[
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

CONSUMPTION_DESCRIPTIONS: tuple[
    PowersensorVirtualHouseholdSensorEntityDescription, ...
] = tuple(
    d
    for d in HOUSEHOLD_DESCRIPTIONS
    if d.key
    in {"power_home_use", "power_from_grid", "energy_home_use", "energy_from_grid"}
)

PRODUCTION_DESCRIPTIONS: tuple[
    PowersensorVirtualHouseholdSensorEntityDescription, ...
] = tuple(
    d
    for d in HOUSEHOLD_DESCRIPTIONS
    if d.key
    in {
        "power_to_grid",
        "power_solar_generation",
        "energy_to_grid",
        "energy_solar_generation",
    }
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
        """(Re-)schedule the unavailability timer using async_call_later."""
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
        """Subscribe to dispatcher signals when added to HA."""
        self._has_recently_received_update_message = False
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_update)
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, ROLE_UPDATE_SIGNAL, self._handle_role_update
            )
        )
        self.async_on_remove(self._cancel_unavailability_tracker)

    def _rename_based_on_role(self) -> bool:
        """Return True if a role change requires refreshing device translation data.

        This is a subclass hook used by ``_handle_role_update`` to decide whether
        the device registry should be updated with a new ``translation_key`` and
        related placeholders after the role changes.
        """
        return False

    @callback
    def _handle_role_update(self, mac: str, role: str | None) -> None:
        """Handle a role update signal for this device."""
        if self._mac != mac or self._role == role:
            return

        self._role = role
        if not self._rename_based_on_role():
            return

        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(identifiers={(DOMAIN, self._mac)})
        info = self.device_info
        if device is not None:
            device_registry.async_get_or_create(
                config_entry_id=self._config_entry_id,
                identifiers=device.identifiers,
                translation_key=info.get("translation_key"),
                translation_placeholders=info.get("translation_placeholders"),
            )

        self.async_write_ha_state()

    @callback
    def _handle_update(self, event: str, message: dict[str, Any]) -> None:
        """Handle a pushed data update from the dispatcher."""
        self._has_recently_received_update_message = True

        desc = self.entity_description
        if desc.message_key in message:
            raw = message[desc.message_key]
            if desc.conversion_function:
                self._attr_native_value = desc.conversion_function(raw)
            elif desc.key == "device_role" and isinstance(raw, str):
                # State translation keys must be snake_case.  The wire value
                # "house-net" is normalised to "house_net" so it matches the
                # key in strings.json.  All other role strings are already
                # valid (no hyphens).
                self._attr_native_value = raw.replace("-", "_")
            else:
                self._attr_native_value = raw

        self._schedule_unavailable()
        self.async_write_ha_state()


# ---------------------------------------------------------------------------
# electricity / water sensor entity
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

    def _rename_based_on_role(self) -> bool:
        expected = self._get_translation_key()
        if self._current_translation_key != expected:
            self._current_translation_key = expected
            return True
        return False


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

    # Household entities are always considered available because the
    # VirtualHousehold is a pure in-process calculation layer with no network
    # dependency of its own.  If the underlying plug or sensor devices go
    # offline their own entities will become unavailable, which is the correct
    # signal to the user.  The VHH continues to hold its last-known values and
    # will resume updating as soon as data arrives again — marking it
    # unavailable in the interim would only cause unnecessary dashboard churn.
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
        self._attr_unique_id = f"vhh_{description.event}"

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

        Must be ``async def``: VirtualHousehold.subscribe awaits every
        registered callback, so a plain synchronous function would be awaited
        as a coroutine and silently produce no result.
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

    # Sensor-platform bookkeeping — local to this closure so that a reload
    # always starts clean without touching RuntimeData.
    vhh_state = PowersensorVirtualHouseholdState()
    role_specific_entities_added: set[tuple[str, str]] = set()

    entry_id = entry.entry_id

    def _with_solar() -> bool:
        """Return True when any known sensor carries the solar role."""
        return ROLE_SOLAR in entry.data.get(CFG_ROLES, {}).values()

    def _with_mains() -> bool:
        """Return True when any known sensor carries the house-net role."""
        return ROLE_HOUSENET in entry.data.get(CFG_ROLES, {}).values()

    # ------------------------------------------------------------------
    # Role update handling
    # ------------------------------------------------------------------

    @callback
    def handle_role_update(mac_address: str, new_role: str | None) -> None:
        """Persist role changes and trigger a VHH refresh when needed."""
        # Plugs report None or ROLE_APPLIANCE and have all their entities
        # created unconditionally at discovery time — nothing to do here.

        # Build a fresh copy of entry.data with an updated roles dict.
        # entry.data is immutable by convention — async_update_entry replaces it
        # atomically — so we construct a new top-level dict and a new roles dict
        # rather than mutating any nested object in place.
        existing_roles: dict[str, str | None] = dict(entry.data.get(CFG_ROLES, {}))
        old_role = existing_roles.get(mac_address)
        new_data = {
            **entry.data,
            CFG_ROLES: {**existing_roles, mac_address: new_role},
        }

        if mac_address in dispatcher.plugs:
            # Plugs only get ROLE_APPLIANCE (or None) — they don't roam between
            # roles the way sensors do, so we only persist when the role is
            # ROLE_APPLIANCE and has actually changed.  All plug entities are
            # created unconditionally at discovery time, so no entity creation
            # is needed here regardless of the new role.
            if new_role == ROLE_APPLIANCE and old_role != new_role:
                _LOGGER.debug(
                    "Updating role for %s from %s to %s",
                    mac_address,
                    old_role,
                    new_role,
                )
                hass.config_entries.async_update_entry(entry, data=new_data)
            return

        if old_role != new_role:
            _LOGGER.debug(
                "Updating role for %s from %s to %s", mac_address, old_role, new_role
            )
            hass.config_entries.async_update_entry(entry, data=new_data)

            if new_role in (ROLE_SOLAR, ROLE_HOUSENET):
                async_dispatcher_send(hass, UPDATE_VHH_SIGNAL)

            # Add any role-specific entities that weren't created at discovery
            # time (e.g. water_flow_rate / total_water_consumption when a sensor
            # is reassigned to ROLE_WATER, or power / total_energy when it moves
            # to ROLE_HOUSENET / ROLE_SOLAR).
            # Only touch descriptions that are role-gated (supported_roles is
            # not None) to avoid re-creating universal entities (battery, rssi,
            # device_role) which already exist and would trigger
            # duplicate-unique-ID warnings.
            new_role_entities = [
                PowersensorSensorEntity(entry_id, mac_address, new_role, desc)
                for desc in SENSOR_DESCRIPTIONS
                if desc.supported_roles is not None
                and new_role in desc.supported_roles
                and (mac_address, desc.key) not in role_specific_entities_added
            ]
            if new_role_entities:
                _LOGGER.debug(
                    "Adding %d role-specific entities for %s (role=%s)",
                    len(new_role_entities),
                    mac_address,
                    new_role,
                )
                for e in new_role_entities:
                    role_specific_entities_added.add(
                        (mac_address, e.entity_description.key)
                    )
                async_add_entities(new_role_entities, True)

    entry.async_on_unload(
        async_dispatcher_connect(hass, ROLE_UPDATE_SIGNAL, handle_role_update)
    )

    # ------------------------------------------------------------------
    # Sensor discovery
    # ------------------------------------------------------------------

    @callback
    def handle_discovered_sensor(sensor_mac: str, sensor_role: str | None) -> None:
        """Create entities for a newly discovered sensor and signal HA."""
        new_sensors = [
            PowersensorSensorEntity(entry_id, sensor_mac, sensor_role, desc)
            for desc in SENSOR_DESCRIPTIONS
            if desc.supported_roles is None or sensor_role in desc.supported_roles
        ]

        # Record role-gated entities now so that handle_role_update — which fires
        # shortly after via SENSOR_ADDED_TO_HA_SIGNAL → ROLE_UPDATE_SIGNAL — sees
        # them as already created and doesn't add duplicates.
        for e in new_sensors:
            if e.entity_description.supported_roles is not None:
                role_specific_entities_added.add((sensor_mac, e.entity_description.key))

        async_add_entities(new_sensors, True)
        async_dispatcher_send(hass, SENSOR_ADDED_TO_HA_SIGNAL, sensor_mac, sensor_role)

        if (
            sensor_role == ROLE_SOLAR and _with_mains()
        ) or sensor_role == ROLE_HOUSENET:
            async_dispatcher_send(hass, UPDATE_VHH_SIGNAL)

    entry.async_on_unload(
        async_dispatcher_connect(hass, CREATE_SENSOR_SIGNAL, handle_discovered_sensor)
    )

    # ------------------------------------------------------------------
    # Plug handling
    # ------------------------------------------------------------------

    def _create_plug_entities(plug_mac: str, role: str) -> list[PowersensorPlugEntity]:
        """Return plug sensor entities for a given MAC address."""
        return [
            PowersensorPlugEntity(entry_id, plug_mac, role, desc)
            for desc in PLUG_DESCRIPTIONS
        ]

    for plug_mac in dispatcher.plugs:
        async_add_entities(_create_plug_entities(plug_mac, ROLE_APPLIANCE), True)

    @callback
    def handle_discovered_plug(plug_mac: str, host: str, port: int, name: str) -> None:
        """Create entities for a newly discovered plug and signal HA."""
        async_add_entities(_create_plug_entities(plug_mac, ROLE_APPLIANCE), True)
        async_dispatcher_send(hass, PLUG_ADDED_TO_HA_SIGNAL, plug_mac, host, port, name)

    entry.async_on_unload(
        async_dispatcher_connect(hass, CREATE_PLUG_SIGNAL, handle_discovered_plug)
    )

    # Catch sensors whose messages arrived before the platform was ready.
    # Clear the queue afterwards so a reload does not re-process them.
    for mac, role in dispatcher.drain_on_start_sensor_queue():
        handle_discovered_sensor(mac, role)

    # ------------------------------------------------------------------
    # Virtual Household
    # ------------------------------------------------------------------

    @callback
    def update_virtual_household_entities() -> None:
        """Add VHH sensor entities once the required sensor roles are available.

        Called at startup and whenever a sensor role changes.  The first time a
        solar sensor is seen we must reconstruct the VirtualHousehold with
        ``with_solar=True`` — the library does not support enabling solar on an
        existing instance.  We transfer the dispatcher's reference and re-wire any
        existing entity subscriptions via a brief unsubscribe / re-subscribe cycle
        so that entities already added to HA continue to receive events.

        This is a synchronous @callback because it only calls async_add_entities
        (which is itself synchronous) and accesses in-memory state.  The lock is
        not needed here since HA callbacks are serialised on the event loop.
        """
        if not _with_mains():
            _LOGGER.debug("No house-net sensor yet; VHH not operational")
            return

        household_entities: list[PowersensorHouseholdEntity] = []

        if not vhh_state.mains_added:
            _LOGGER.debug("Enabling mains components in virtual household")
            household_entities.extend(
                PowersensorHouseholdEntity(vhh, desc)
                for desc in CONSUMPTION_DESCRIPTIONS
            )
            vhh_state.mains_added = True

        if _with_solar() and not vhh_state.solar_added:
            _LOGGER.debug("Enabling solar components in virtual household")

            # Guard: the VirtualHousehold must be constructed with
            # with_solar=True to emit solar events.  If a solar sensor is
            # discovered mid-session (i.e. after __init__.py already built the
            # VHH with False), schedule a config-entry reload so that
            # async_setup_entry re-reads entry.data — which by this point
            # already has the solar role persisted — and rebuilds the VHH
            # correctly.  Return early so we don't add solar entities that
            # would be subscribed to an incapable VHH instance.
            if not runtime.with_solar:
                _LOGGER.debug(
                    "VirtualHousehold lacks solar support; scheduling reload "
                    "to rebuild with with_solar=True"
                )
                hass.config_entries.async_schedule_reload(entry.entry_id)
                return

            household_entities.extend(
                PowersensorHouseholdEntity(vhh, desc)
                for desc in PRODUCTION_DESCRIPTIONS
            )
            vhh_state.solar_added = True

        if household_entities:
            async_add_entities(household_entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, UPDATE_VHH_SIGNAL, update_virtual_household_entities
        )
    )

    update_virtual_household_entities()
