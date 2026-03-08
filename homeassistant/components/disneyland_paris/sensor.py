"""Sensor platform for Disneyland Paris Integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from dlpwait import Park, Parks

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DisneylandParisConfigEntry
from .entity import DisneyAdventureWorldEntity, DisneylandEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DisneylandParisSensorEntityDescription(SensorEntityDescription):
    """Describes Disneyland Paris sensor entity."""

    value_fn: Callable[[Park], int | datetime | None]


DISNEYLAND_PARK_SENSORS: tuple[DisneylandParisSensorEntityDescription, ...] = (
    DisneylandParisSensorEntityDescription(
        key="opening_time",
        translation_key="opening_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda park: park.opening_time,
    ),
    DisneylandParisSensorEntityDescription(
        key="closing_time",
        translation_key="closing_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda park: park.closing_time,
    ),
)

DISNEYLAND_ATTRACTION_SENSORS: tuple[DisneylandParisSensorEntityDescription, ...] = (
    DisneylandParisSensorEntityDescription(
        key="P1NA07",
        translation_key="its_a_small_world_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1NA07"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1AA00",
        translation_key="adventure_isle_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1AA00"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1NA00",
        translation_key="alices_curious_labyrinth_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1NA00"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1DA03",
        translation_key="autopia_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1DA03"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1RA00",
        translation_key="big_thunder_mountain_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1RA00"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1NA01",
        translation_key="blanche_neige_et_les_sept_nains_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1NA01"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1DA04",
        translation_key="buzz_lightyear_laser_blast_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1DA04"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1NA03",
        translation_key="casey_jr_le_petit_train_du_cirque_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1NA03"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1DA10",
        translation_key="disneyland_railroad_discoveryland_station_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1DA10"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1NA16",
        translation_key="disneyland_railroad_fantasyland_station_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1NA16"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1RA10",
        translation_key="disneyland_railroad_frontierland_depot_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1RA10"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1MA05",
        translation_key="disneyland_railroad_main_street_station_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1MA05"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1NA05",
        translation_key="dumbo_the_flying_elephant_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1NA05"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1RA07",
        translation_key="frontierland_playground_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1RA07"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1AA02",
        translation_key="indiana_jones_and_the_temple_of_peril_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1AA02"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1AA01",
        translation_key="la_cabane_des_robinson_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1AA01"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1NA06",
        translation_key="la_galerie_de_la_belle_au_bois_dormant_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1NA06"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1NA12",
        translation_key="la_taniere_du_dragon_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1NA12"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1NA02",
        translation_key="le_carrousel_de_lancelot_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1NA02"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1AA03",
        translation_key="le_passage_enchante_daladdin_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1AA03"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1NA09",
        translation_key="le_pays_des_contes_de_fees_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1NA09"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1DA06",
        translation_key="les_mysteres_du_nautilus_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1DA06"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1NA13",
        translation_key="les_voyages_de_pinocchio_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1NA13"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1NA08",
        translation_key="mad_hatters_tea_cups_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1NA08"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1MA04",
        translation_key="main_street_vehicles_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1MA04"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1DA07",
        translation_key="orbitron_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1DA07"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1NA10",
        translation_key="peter_pans_flight_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1NA10"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1RA03",
        translation_key="phantom_manor_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1RA03"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1AA08",
        translation_key="pirate_galleon_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1AA08"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1AA04",
        translation_key="pirates_of_the_caribbean_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1AA04"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1AA05",
        translation_key="pirates_beach_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1AA05"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1RA05",
        translation_key="rustler_roundup_shootin_gallery_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1RA05"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1DA09",
        translation_key="star_tours_the_adventures_continue_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1DA09"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1DA08",
        translation_key="star_wars_hyperspace_mountain_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1DA08"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P1RA06",
        translation_key="thunder_mesa_riverboat_landing_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P1RA06"),
    ),
)

DISNEY_ADVENTURE_WORLD_PARK_SENSORS: tuple[
    DisneylandParisSensorEntityDescription, ...
] = (
    DisneylandParisSensorEntityDescription(
        key="opening_time",
        translation_key="opening_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda park: park.opening_time,
    ),
    DisneylandParisSensorEntityDescription(
        key="closing_time",
        translation_key="closing_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda park: park.closing_time,
    ),
)

DISNEY_ADVENTURE_WORLD_ATTRACTION_SENSORS: tuple[
    DisneylandParisSensorEntityDescription, ...
] = (
    DisneylandParisSensorEntityDescription(
        key="P2AC01",
        translation_key="avengers_assemble_flight_force_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P2AC01"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P2XA02",
        translation_key="cars_quatre_roues_rallye_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P2XA02"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P2XA00",
        translation_key="cars_road_trip_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P2XA00"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P2XA03",
        translation_key="crushs_coaster_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P2XA03"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P2EA00",
        translation_key="frozen_ever_after_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P2EA00"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P2XA05",
        translation_key="les_tapis_volants_flying_carpets_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P2XA05"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P2DA00",
        translation_key="raiponce_tangled_spin_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P2DA00"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P2XA09",
        translation_key="ratatouille_remy_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P2XA09"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P2XA06",
        translation_key="rc_racer_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P2XA06"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P2XA08",
        translation_key="slinky_dog_zigzag_spin_standby_wait_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P2XA08"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P2AC02",
        translation_key="spider_man_web_adventure_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P2AC02"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P2ZA02",
        translation_key="tower_of_terror_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P2ZA02"),
    ),
    DisneylandParisSensorEntityDescription(
        key="P2XA07",
        translation_key="toy_soldiers_parachute_drop_standby_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda park: park.standby_wait_times.get("P2XA07"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DisneylandParisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        [
            *(
                DisneylandSensor(coordinator, description)
                for description in DISNEYLAND_PARK_SENSORS
            ),
            *(
                DisneylandSensor(coordinator, description)
                for description in DISNEYLAND_ATTRACTION_SENSORS
                if description.key
                in coordinator.client.parks[Parks.DISNEYLAND].standby_wait_times
            ),
            *(
                DisneyAdventureWorldSensor(coordinator, description)
                for description in DISNEY_ADVENTURE_WORLD_PARK_SENSORS
            ),
            *(
                DisneyAdventureWorldSensor(coordinator, description)
                for description in DISNEY_ADVENTURE_WORLD_ATTRACTION_SENSORS
                if description.key
                in coordinator.client.parks[
                    Parks.WALT_DISNEY_STUDIOS
                ].standby_wait_times
            ),
        ]
    )


class DisneylandSensor(DisneylandEntity, SensorEntity):
    """Base Disneyland Sensor Class."""

    entity_description: DisneylandParisSensorEntityDescription

    @property
    def native_value(self) -> int | datetime | None:
        """Return the native value of the sensor."""

        return self.entity_description.value_fn(
            self.coordinator.client.parks[Parks.DISNEYLAND]
        )


class DisneyAdventureWorldSensor(DisneyAdventureWorldEntity, SensorEntity):
    """Base Disney Adventure World Sensor Class."""

    entity_description: DisneylandParisSensorEntityDescription

    @property
    def native_value(self) -> int | datetime | None:
        """Return the native value of the sensor."""

        return self.entity_description.value_fn(
            self.coordinator.client.parks[Parks.WALT_DISNEY_STUDIOS]
        )
