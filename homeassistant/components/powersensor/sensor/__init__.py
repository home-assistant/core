"""Sensor platform for the integration."""

from __future__ import annotations

import asyncio
import copy
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from ..const import (
    # Used config entry fields
    CFG_ROLES,
    # Used signals
    CREATE_PLUG_SIGNAL,
    CREATE_SENSOR_SIGNAL,
    PLUG_ADDED_TO_HA_SIGNAL,
    # Used roles
    ROLE_APPLIANCE,
    ROLE_HOUSENET,
    ROLE_SOLAR,
    ROLE_UPDATE_SIGNAL,
    # Used runtime_data entries
    RT_DISPATCHER,
    RT_VHH,
    RT_VHH_LOCK,
    RT_VHH_MAINS_ADDED,
    RT_VHH_SOLAR_ADDED,
    SENSOR_ADDED_TO_HA_SIGNAL,
    UPDATE_VHH_SIGNAL,
)
from ..PowersensorMessageDispatcher import PowersensorMessageDispatcher
from .PlugMeasurements import PlugMeasurements
from .PowersensorHouseholdEntity import (
    ConsumptionMeasurements,
    PowersensorHouseholdEntity,
    ProductionMeasurements,
)
from .PowersensorPlugEntity import PowersensorPlugEntity
from .PowersensorSensorEntity import PowersensorSensorEntity
from .SensorMeasurements import SensorMeasurements

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Powersensor sensors."""
    vhh = entry.runtime_data[RT_VHH]
    dispatcher: PowersensorMessageDispatcher = entry.runtime_data[RT_DISPATCHER]

    entry.runtime_data[RT_VHH_LOCK] = asyncio.Lock()
    entry.runtime_data[RT_VHH_MAINS_ADDED] = False
    entry.runtime_data[RT_VHH_SOLAR_ADDED] = False

    plug_role = ROLE_APPLIANCE

    def with_solar():
        """Checks whether any known sensor has the solar role."""
        return ROLE_SOLAR in entry.data.get(CFG_ROLES, {}).values()

    def with_mains():
        """Checks whether any known sensor has the house-net role."""
        return ROLE_HOUSENET in entry.data.get(CFG_ROLES, {}).values()

    #
    # Role update support
    #
    async def handle_role_update(mac_address: str, new_role: str):
        """Persists role updates and signals for VHH update if needed."""
        # We only persist actual roles. If a device forgets its role, we want
        # to keep what we've previously learned.
        if new_role is not None:
            new_data = copy.deepcopy({**entry.data})
            if CFG_ROLES not in new_data:
                new_data[CFG_ROLES] = {}
            roles = new_data[CFG_ROLES]
            old_role = roles.get(mac_address, None)
            if old_role is None or old_role != new_role:
                _LOGGER.debug(
                    "Updating role for %s from %s to %s",
                    mac_address,
                    old_role,
                    new_role,
                )
                roles[mac_address] = new_role
                hass.config_entries.async_update_entry(entry, data=new_data)

        # Note: for house-net/solar/appliance <-> water we'd need to change the entities too

        # Note: we don't currently support dynamically removing/disabling VHH
        # entities if a solar/house-net sensor disappears.
        if new_role in [ROLE_SOLAR, ROLE_HOUSENET]:
            async_dispatcher_send(hass, UPDATE_VHH_SIGNAL)

    entry.async_on_unload(
        async_dispatcher_connect(hass, ROLE_UPDATE_SIGNAL, handle_role_update)
    )

    #
    # Automatic sensor discovery
    #
    async def handle_discovered_sensor(sensor_mac: str, sensor_role: str):
        """Registers sensor entities, signals sensor added plus VHH update if needed."""
        new_sensors = [
            PowersensorSensorEntity(
                hass, sensor_mac, sensor_role, SensorMeasurements.Battery
            ),
            PowersensorSensorEntity(
                hass, sensor_mac, sensor_role, SensorMeasurements.WATTS
            ),
            PowersensorSensorEntity(
                hass, sensor_mac, sensor_role, SensorMeasurements.SUMMATION_ENERGY
            ),
            PowersensorSensorEntity(
                hass, sensor_mac, sensor_role, SensorMeasurements.ROLE
            ),
            PowersensorSensorEntity(
                hass, sensor_mac, sensor_role, SensorMeasurements.RSSI
            ),
        ]
        async_add_entities(new_sensors, True)
        async_dispatcher_send(hass, SENSOR_ADDED_TO_HA_SIGNAL, sensor_mac, sensor_role)

        if (sensor_role == ROLE_SOLAR and with_mains()) or sensor_role == ROLE_HOUSENET:
            async_dispatcher_send(hass, UPDATE_VHH_SIGNAL)

    entry.async_on_unload(
        async_dispatcher_connect(hass, CREATE_SENSOR_SIGNAL, handle_discovered_sensor)
    )

    #
    # Plug handling
    #
    async def create_plug(plug_mac_address: str, role: str):
        """Registers sensor entities."""
        this_plug_sensors = [
            PowersensorPlugEntity(hass, plug_mac_address, role, PlugMeasurements.WATTS),
            PowersensorPlugEntity(
                hass, plug_mac_address, role, PlugMeasurements.VOLTAGE
            ),
            PowersensorPlugEntity(
                hass, plug_mac_address, role, PlugMeasurements.APPARENT_CURRENT
            ),
            PowersensorPlugEntity(
                hass, plug_mac_address, role, PlugMeasurements.ACTIVE_CURRENT
            ),
            PowersensorPlugEntity(
                hass, plug_mac_address, role, PlugMeasurements.REACTIVE_CURRENT
            ),
            PowersensorPlugEntity(
                hass, plug_mac_address, role, PlugMeasurements.SUMMATION_ENERGY
            ),
            PowersensorPlugEntity(hass, plug_mac_address, role, PlugMeasurements.ROLE),
        ]

        async_add_entities(this_plug_sensors, True)

    for plug_mac in dispatcher.plugs:
        await create_plug(plug_mac, plug_role)

    #
    # Automatic plug discovery
    #
    async def handle_discovered_plug(
        plug_mac_address: str, host: str, port: int, name: str
    ):
        """Registers sensor entities, signals plug added."""
        await create_plug(plug_mac_address, plug_role)
        async_dispatcher_send(
            hass, PLUG_ADDED_TO_HA_SIGNAL, plug_mac_address, host, port, name
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, CREATE_PLUG_SIGNAL, handle_discovered_plug)
    )
    await dispatcher.process_plug_queue()

    # Possibly unnecessary but will add sensors where the messages came in early
    # Hopefully keeps wait time less than 30s
    for mac, role in dispatcher.on_start_sensor_queue.items():
        await handle_discovered_sensor(mac, role)

    #
    # Virtual household support
    #
    async def update_virtual_household_entities():
        """Enables VHH entities based on solar/house-net availability."""
        async with entry.runtime_data[RT_VHH_LOCK]:
            if not with_mains():
                _LOGGER.debug("No house-net, VHH not yet operational")
                return  # No VHH until we have at least house-net

            mains_added = entry.runtime_data[RT_VHH_MAINS_ADDED]
            solar_added = entry.runtime_data[RT_VHH_SOLAR_ADDED]

            household_entities = []

            if with_mains() and not mains_added:
                _LOGGER.debug("Enabling mains components in virtual household")
                household_entities.extend(
                    [
                        PowersensorHouseholdEntity(vhh, measurement_type)
                        for measurement_type in ConsumptionMeasurements
                    ]
                )

                entry.runtime_data[RT_VHH_MAINS_ADDED] = True

            if with_solar() and not solar_added:
                _LOGGER.debug("Enabling solar components in virtual household")
                household_entities.extend(
                    [
                        PowersensorHouseholdEntity(vhh, solar_measurement_type)
                        for solar_measurement_type in ProductionMeasurements
                    ]
                )
                entry.runtime_data[RT_VHH_SOLAR_ADDED] = True

            if len(household_entities) > 0:
                async_add_entities(household_entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, UPDATE_VHH_SIGNAL, update_virtual_household_entities
        )
    )

    await update_virtual_household_entities()
