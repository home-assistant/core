"""Sensor platform for the Powersensor integration.

Each physical Powersensor device (magnetic sensor, water sensor, smart plug) pushes
data to the integration over UDP via a Powersensor plug.  A single logical
"Virtual Household" device aggregates readings from mains and solar magnetic sensor
into whole-home power/energy figures.

Entity descriptions are declared as module-level tuples so the entity classes
themselves stay thin — each class simply reads ``entity_description`` fields
rather than containing dispatch logic.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from typing import Any, override

from powersensor_local import VirtualHousehold

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
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
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CREATE_PLUG_SIGNAL,
    CREATE_SENSOR_SIGNAL,
    DATA_UPDATE_SIGNAL_PREFIX,
    DEVICE_REMOVED_SIGNAL,
    DOMAIN,
    ROLE_APPLIANCE,
    ROLE_HOUSENET,
    ROLE_SOLAR,
    ROLE_UPDATE_SIGNAL,
    ROLE_WATER,
    UPDATE_VHH_SIGNAL,
    VHH_DEVICE_ID,
)
from .entity import PLUG_UPDATE_TIMEOUT, SENSOR_UPDATE_TIMEOUT, PowersensorEntity
from .models import PowersensorConfigEntry, PowersensorRuntimeData
from .powersensor_message_dispatcher import PowersensorMessageDispatcher

_LOGGER = logging.getLogger(__name__)


def _volts_to_battery_pct(volts: float) -> float:
    """Convert a battery voltage reading to a percentage (3.3 V = 0 %, 4.15 V = 100 %).

    A linear approximation is deliberate.  powersensor-local reports the raw
    voltage and documents that any percentage mapping is inaccurate, because
    battery curves vary between individual cells and with conditions.  For a
    simple percentage display it recommends exactly this linear extrapolation
    across the middle of the curve, 3.3 V to 4.15 V: "not entirely accurate,
    but it's also not useless" (see the "volts" field in its xlatemsg module).
    """
    return max(min(100.0 * (volts - 3.3) / 0.85, 100.0), 0.0)


def _joules_to_kwh(joules: float) -> float:
    """Convert watt-seconds (joules) to kilowatt-hours."""
    return joules / 3_600_000.0


# States of the device_role ENUM entities.  Wire roles are snake_cased to match.
_DEVICE_ROLE_OPTIONS = ["appliance", "house_net", "solar", "unknown", "water"]

_SENSOR_DEVICE_TRANSLATION_KEYS: dict[str | None, str] = {
    ROLE_HOUSENET: "mains_sensor",
    ROLE_SOLAR: "solar_sensor",
    ROLE_WATER: "water_sensor",
    ROLE_APPLIANCE: "appliance_sensor",
}


def _sensor_device_translation_key(role: str | None) -> str:
    """Return the device-registry translation key naming a sensor by its role."""
    return _SENSOR_DEVICE_TRANSLATION_KEYS.get(role, "unknown_sensor")


@dataclass(frozen=True, kw_only=True)
class PowersensorSensorEntityDescription(SensorEntityDescription):
    """Describes a single measurement entity for an electricity/water sensor or plug.

    Attributes:
        conversion_function: Optional transform applied to the raw message value.
        event:               Required dispatcher event name this entity subscribes to.
        message_key:         Required key inside the event payload that carries the value.
        last_reset_key:      Optional key inside the event payload that carries when the
                             value last reset to zero, in seconds since the Unix epoch.
                             Set for TOTAL sensors, so that statistics start a new
                             cycle at a reset instead of counting the drop.
        supported_roles:     When set, this entity is only created for sensors whose
                             role is in this set.  None means all roles.
    """

    event: str
    message_key: str
    conversion_function: Callable[[float], float] | None = None
    last_reset_key: str | None = None
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


SENSOR_DESCRIPTIONS: tuple[PowersensorSensorEntityDescription, ...] = (
    PowersensorSensorEntityDescription(
        key="battery_level",
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
        device_class=SensorDeviceClass.ENERGY,
        # TOTAL (not TOTAL_INCREASING) is intentional: magnetic sensors do net
        # metering, so the cumulative joule value can decrease (e.g. a solar
        # sensor exporting more than it imports).
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        event="summation_energy",
        message_key="summation_joules",
        conversion_function=_joules_to_kwh,
        last_reset_key="summation_resettime_utc",
        supported_roles=frozenset({ROLE_HOUSENET, ROLE_SOLAR, ROLE_APPLIANCE}),
    ),
    PowersensorSensorEntityDescription(
        key="device_role",
        translation_key="device_role",
        device_class=SensorDeviceClass.ENUM,
        options=_DEVICE_ROLE_OPTIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        event="role",
        message_key="role",
    ),
    PowersensorSensorEntityDescription(
        key="rssi_ble",
        translation_key="rssi_ble",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        event="radio_signal_quality",
        message_key="average_rssi",
    ),
    PowersensorSensorEntityDescription(
        key="water_flow_rate",
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
        device_class=SensorDeviceClass.WATER,
        # TOTAL_INCREASING: water sensors can't detect backflow, so the total
        # only increases until the device resets it to zero, which this state
        # class treats as the start of a new meter cycle.
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
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        event="average_power",
        message_key="watts",
    ),
    PowersensorSensorEntityDescription(
        key="volts",
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
        device_class=SensorDeviceClass.ENERGY,
        # TOTAL (not TOTAL_INCREASING) is intentional, even though plugs
        # measure load-side consumption only and can't measure reverse flow.
        # Readings aren't clipped at zero, so with no load, measurement noise
        # makes the counter dip briefly, and can take it below zero just after
        # a reset; the dips and rises cancel out over time.  HA requires that a
        # TOTAL_INCREASING value cannot decrease because of measurement noise:
        # it would log a warning for every dip, treat a dip of more than 10% as
        # a meter reset, and reject negative values.
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        event="summation_energy",
        message_key="summation_joules",
        conversion_function=_joules_to_kwh,
        last_reset_key="summation_resettime_utc",
    ),
    PowersensorSensorEntityDescription(
        # Plugs report ROLE_APPLIANCE.  A message without a role falls back to
        # the saved one (the dispatcher saves plug roles too), so once a plug
        # has reported its role this shows "appliance" rather than "unknown".
        key="device_role",
        translation_key="device_role",
        device_class=SensorDeviceClass.ENUM,
        options=_DEVICE_ROLE_OPTIONS,
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
        # TOTAL_INCREASING: VirtualHousehold's totals only increase, and restart
        # from zero when it is created (each HA start or integration reload) or
        # a contributing sensor's counter resets.  This state class treats a
        # drop as the start of a new meter cycle.
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
        # TOTAL_INCREASING: VirtualHousehold's totals only increase, and restart
        # from zero when it is created (each HA start or integration reload) or
        # a contributing sensor's counter resets.  This state class treats a
        # drop as the start of a new meter cycle.
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
        # TOTAL_INCREASING: VirtualHousehold's totals only increase, and restart
        # from zero when it is created (each HA start or integration reload) or
        # a contributing sensor's counter resets.  This state class treats a
        # drop as the start of a new meter cycle.
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
        # TOTAL_INCREASING: VirtualHousehold's totals only increase, and restart
        # from zero when it is created (each HA start or integration reload) or
        # a contributing sensor's counter resets.  This state class treats a
        # drop as the start of a new meter cycle.
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        formatter=_joules_to_kwh,
        event="solar_generation_summation",
        message_key="summation_joules",
    ),
)


@dataclass
class PowersensorVirtualHouseholdState:
    """Tracks which Virtual Household entity groups have been added to HA.

    Both flags are one-way within a session: a group is never removed once
    added.  Household figures are only correct while every contributing sensor
    is reporting, so a solar sensor that stops reporting must still count as
    part of the household — its entities stay and withhold data rather than
    disappearing and taking their recorded energy history with them.  A
    household that has genuinely lost its solar array needs the integration
    set up again.

    Owned by async_setup_entry's closure and reset on every reload so that a
    fresh load always starts clean.
    """

    mains_added: bool = False
    solar_added: bool = False


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
    # Entries are never removed on a role change, matching the fact that the
    # entities themselves are kept (see handle_role_update).  They are removed
    # only when the user deletes the device, which takes its entities with it.
    role_entities_added: set[tuple[str, str]] = set()

    entry_id = entry.entry_id

    @callback
    def handle_role_update(mac_address: str, new_role: str | None) -> None:
        """Add whatever entities a sensor's new role enables, and rename its device.

        The dispatcher has already saved the role: it sends this signal only
        for a role that changed, and saves it first so that saving does not
        depend on this platform having loaded.

        Entities belonging to the previous role are deliberately left in place.
        Role changes are usually transient: a sensor that has forgotten its
        role reports the real one again as soon as it recovers, and the role
        set through the reconfigure flow is overridden the moment that happens.
        Removing entities in between would discard the energy history they have
        recorded.  A sensor that has genuinely been re-purposed therefore needs
        its stale entities deleted by hand.
        """
        if mac_address in dispatcher.plugs:
            # A plug's role is always ROLE_APPLIANCE, so there are no role-gated
            # entities to add and no device to rename.
            return

        # The device is named after its role, but core only reads device_info
        # when an entity is added, so the rename has to go to the registry
        # directly.  Done here rather than per entity to keep it to one write.
        dr.async_get(hass).async_get_or_create(
            config_entry_id=entry_id,
            identifiers={(DOMAIN, mac_address)},
            translation_key=_sensor_device_translation_key(new_role),
            translation_placeholders={"id": mac_address},
        )

        if new_role in (ROLE_SOLAR, ROLE_HOUSENET):
            async_dispatcher_send(hass, UPDATE_VHH_SIGNAL)

        # Create any role-gated entities not present at initial discovery
        # (e.g. power/energy when a sensor is assigned ROLE_HOUSENET/ROLE_SOLAR,
        # or flow/volume when assigned ROLE_WATER).
        new_entities = [
            PowersensorSensorEntity(dispatcher, mac_address, desc)
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
            async_add_entities(new_entities)

    entry.async_on_unload(
        async_dispatcher_connect(hass, ROLE_UPDATE_SIGNAL, handle_role_update)
    )

    @callback
    def handle_device_removed(mac_address: str) -> None:
        """Forget a deleted device's entities, so they are added again if it returns."""
        role_entities_added.difference_update(
            {added for added in role_entities_added if added[0] == mac_address}
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, DEVICE_REMOVED_SIGNAL, handle_device_removed)
    )

    @callback
    def handle_discovered_sensor(sensor_mac: str, sensor_role: str | None) -> None:
        """Create entities for a newly discovered sensor."""
        new_sensors = [
            PowersensorSensorEntity(dispatcher, sensor_mac, desc)
            for desc in SENSOR_DESCRIPTIONS
            if desc.supported_roles is None or sensor_role in desc.supported_roles
        ]

        # Pre-populate role_entities_added so handle_role_update — which fires
        # shortly after via ROLE_UPDATE_SIGNAL — doesn't add duplicates.
        for e in new_sensors:
            if e.entity_description.supported_roles is not None:
                role_entities_added.add((sensor_mac, e.entity_description.key))

        async_add_entities(new_sensors)

        if sensor_role in (ROLE_HOUSENET, ROLE_SOLAR):
            async_dispatcher_send(hass, UPDATE_VHH_SIGNAL)

    entry.async_on_unload(
        async_dispatcher_connect(hass, CREATE_SENSOR_SIGNAL, handle_discovered_sensor)
    )

    @callback
    def handle_discovered_plug(plug_mac: str) -> None:
        """Create entities for a newly discovered plug."""
        _LOGGER.debug("Plug discovered: %s", plug_mac)
        async_add_entities(
            [PowersensorPlugEntity(plug_mac, desc) for desc in PLUG_DESCRIPTIONS],
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, CREATE_PLUG_SIGNAL, handle_discovered_plug)
    )

    @callback
    def update_virtual_household_entities() -> None:
        """Add VHH sensor entities once the required sensor roles are present.

        Called at startup and whenever a sensor role changes to ROLE_HOUSENET
        or ROLE_SOLAR.

        VirtualHousehold automatically enables solar processing when it first
        receives a solar-role event (see VirtualHousehold.process_average_power_event),
        so no reload is needed when a solar sensor is discovered mid-session.

        Groups are only ever added, never removed — see
        PowersensorVirtualHouseholdState.
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
            )
            vhh_state.mains_added = True

        if has_solar and not vhh_state.solar_added:
            _LOGGER.debug("Enabling solar components in virtual household")
            async_add_entities(
                [
                    PowersensorHouseholdEntity(vhh, desc)
                    for desc in PRODUCTION_DESCRIPTIONS
                ],
            )
            vhh_state.solar_added = True

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, UPDATE_VHH_SIGNAL, update_virtual_household_entities
        )
    )

    # Discovery starts before this platform is forwarded, so devices found in
    # between are only recorded in the dispatcher — their CREATE signals had no
    # listener.  Seed them now.  There is no await between connecting the
    # listeners above and this loop, so a device is seen by exactly one path.
    for plug_mac in dispatcher.plugs:
        handle_discovered_plug(plug_mac)
    for sensor_mac, sensor_role in dispatcher.sensors.items():
        handle_discovered_sensor(sensor_mac, sensor_role)

    update_virtual_household_entities()


class PowersensorMeasurementEntity(PowersensorEntity, SensorEntity):
    """Sensor entity reporting one measurement from a Powersensor plug or sensor."""

    def __init__(
        self,
        mac: str,
        description: PowersensorSensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            mac,
            f"{DATA_UPDATE_SIGNAL_PREFIX}{mac}_{description.event}",
        )
        self._unrecognised_role: str | None = None
        self._attr_native_value = None
        self.entity_description: PowersensorSensorEntityDescription = description
        self._attr_unique_id = f"{mac}_{description.key}"

    @override
    def _update_from_message(self, message: dict[str, Any]) -> bool:
        """Set the native value from the description's key in the message.

        Measurements are written on every update, even when the value repeats,
        as HA's integral and derivative helpers count the repeated reports.
        device_role arrives with every measurement only to keep it available
        (see the dispatcher), so it is written only when the role changes.
        """
        desc = self.entity_description
        if desc.message_key in message:
            raw = message[desc.message_key]
            if desc.last_reset_key is not None:
                self._attr_last_reset = dt_util.utc_from_timestamp(
                    message[desc.last_reset_key]
                )
            if desc.conversion_function:
                self._attr_native_value = desc.conversion_function(raw)
            elif desc.key == "device_role":
                # State translation keys must be snake_case.  The wire value
                # "house-net" is normalized to "house_net" so it matches the
                # key in strings.json.  All other known roles are already valid.
                # None means the sensor has no role yet; map to "unknown" so the
                # entity always has a valid translation key rather than a None state.
                role = "unknown" if raw is None else raw.replace("-", "_")
                # Firmware may report roles this integration doesn't know yet.
                # Core rejects an ENUM state outside its options on every write,
                # so show those as unknown.  Only the display is clamped: the
                # real role is still persisted and passed to VirtualHousehold,
                # which ignores it.  Clamped any earlier, it would read as a
                # missing role and fall back to the sensor's saved role.
                if role not in _DEVICE_ROLE_OPTIONS:
                    if role != self._unrecognised_role:
                        _LOGGER.debug(
                            "Unrecognised role %r reported by %s; showing as unknown",
                            raw,
                            self._mac,
                        )
                        self._unrecognised_role = role
                    role = "unknown"
                changed = role != self._attr_native_value
                self._attr_native_value = role
                return changed
            else:
                self._attr_native_value = raw
        return True


class PowersensorSensorEntity(PowersensorMeasurementEntity):
    """Entity representing a single measurement from a Powersensor electricity/water sensor."""

    _update_timeout = SENSOR_UPDATE_TIMEOUT

    def __init__(
        self,
        dispatcher: PowersensorMessageDispatcher,
        mac: str,
        description: PowersensorSensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(mac, description)
        self._dispatcher = dispatcher

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor hardware unit.

        Only read when the entity is added; a later role change renames the
        device from the platform's handle_role_update.  The name follows the
        sensor's current role, not the one it had when the entity was created,
        so an entity added after a rename cannot undo it.
        """
        # Deliberately no via_device_id.  A sensor is not tied to a plug: any
        # plug in range can relay it, and it moves to another after repeated
        # communication failures, so a parent plug would often be stale or
        # point at a plug that has been removed.
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            manufacturer="Powersensor",
            model="PowersensorSensor",
            translation_key=_sensor_device_translation_key(
                self._dispatcher.sensors[self._mac]
            ),
            translation_placeholders={"id": self._mac},
        )


class PowersensorPlugEntity(PowersensorMeasurementEntity):
    """Entity representing a single measurement from a Powersensor smart plug."""

    _update_timeout = PLUG_UPDATE_TIMEOUT

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device info for this smart plug."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            manufacturer="Powersensor",
            model="PowersensorPlug",
            translation_key="plug",
            translation_placeholders={"id": self._mac},
        )


class PowersensorHouseholdEntity(SensorEntity):
    """Sensor entity backed by the Powersensor VirtualHousehold calculation engine.

    Always available, unlike the device entities: VirtualHousehold is an
    in-process calculation, and the device entities it derives from already
    show when their data stops.  Marking these unavailable as well would only
    add dashboard churn.
    """

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
    @override
    def device_info(self) -> DeviceInfo:
        """Return device info for the virtual household device."""
        return DeviceInfo(
            identifiers={(DOMAIN, VHH_DEVICE_ID)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Powersensor",
            model="Virtual",
            translation_key="virtual_household_view",
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to VirtualHousehold events."""
        await super().async_added_to_hass()
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
