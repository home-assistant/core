"""Sensor platform for the Xbox integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pythonxbox.api.provider.people.models import Person
from pythonxbox.api.provider.smartglass.models import SmartglassConsole, StorageDevice
from pythonxbox.api.provider.titlehub.models import Title

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    EntityCategory,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_NAME, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import XboxConfigEntry, XboxConsolesCoordinator
from .entity import (
    MAP_MODEL,
    XboxBaseEntity,
    XboxBaseEntityDescription,
    check_deprecated_entity,
    to_https,
)

PARALLEL_UPDATES = 0

MAP_JOIN_RESTRICTIONS = {
    "local": "invite_only",
    "followed": "joinable",
}


class XboxSensor(StrEnum):
    """Xbox sensor."""

    STATUS = "status"
    GAMER_SCORE = "gamer_score"
    ACCOUNT_TIER = "account_tier"
    GOLD_TENURE = "gold_tenure"
    LAST_ONLINE = "last_online"
    FOLLOWING = "following"
    FOLLOWER = "follower"
    NOW_PLAYING = "now_playing"
    FRIENDS = "friends"
    IN_PARTY = "in_party"
    JOIN_RESTRICTIONS = "join_restrictions"
    TOTAL_STORAGE = "total_storage"
    FREE_STORAGE = "free_storage"


@dataclass(kw_only=True, frozen=True)
class XboxSensorEntityDescription(XboxBaseEntityDescription, SensorEntityDescription):
    """Xbox sensor description."""

    value_fn: Callable[[Person, Title | None], StateType | datetime]


@dataclass(kw_only=True, frozen=True)
class XboxStorageDeviceSensorEntityDescription(
    XboxBaseEntityDescription, SensorEntityDescription
):
    """Xbox console sensor description."""

    value_fn: Callable[[StorageDevice], StateType]


def now_playing_attributes(_: Person, title: Title | None) -> dict[str, Any]:
    """Attributes of the currently played title."""
    attributes: dict[str, Any] = {
        "short_description": None,
        "genres": None,
        "developer": None,
        "publisher": None,
        "release_date": None,
        "min_age": None,
        "achievements": None,
        "gamerscore": None,
        "progress": None,
    }
    if not title:
        return attributes
    if title.detail is not None:
        attributes.update(
            {
                "short_description": title.detail.short_description,
                "genres": (
                    ", ".join(title.detail.genres) if title.detail.genres else None
                ),
                "developer": title.detail.developer_name,
                "publisher": title.detail.publisher_name,
                "release_date": (
                    title.detail.release_date.replace(tzinfo=UTC).date()
                    if title.detail.release_date
                    else None
                ),
                "min_age": title.detail.min_age,
            }
        )
    if (achievement := title.achievement) is not None:
        attributes.update(
            {
                "achievements": (
                    f"{achievement.current_achievements} / {achievement.total_achievements}"
                ),
                "gamerscore": (
                    f"{achievement.current_gamerscore} / {achievement.total_gamerscore}"
                ),
                "progress": f"{int(achievement.progress_percentage)} %",
            }
        )

    return attributes


def join_restrictions(person: Person, _: Title | None = None) -> str | None:
    """Join restrictions for current party the user is in."""

    return (
        MAP_JOIN_RESTRICTIONS.get(
            person.multiplayer_summary.party_details[0].join_restriction
        )
        if person.multiplayer_summary and person.multiplayer_summary.party_details
        else None
    )


def title_logo(_: Person, title: Title | None) -> str | None:
    """Get the game logo."""

    return (
        next((to_https(i.url) for i in title.images if i.type == "Tile"), None)
        or next((to_https(i.url) for i in title.images if i.type == "Logo"), None)
        if title and title.images
        else None
    )


SENSOR_DESCRIPTIONS: tuple[XboxSensorEntityDescription, ...] = (
    XboxSensorEntityDescription(
        key=XboxSensor.STATUS,
        translation_key=XboxSensor.STATUS,
        value_fn=lambda x, _: x.presence_text,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.GAMER_SCORE,
        translation_key=XboxSensor.GAMER_SCORE,
        value_fn=lambda x, _: x.gamer_score,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.ACCOUNT_TIER,
        value_fn=lambda _, __: None,
        deprecated=True,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.GOLD_TENURE,
        value_fn=lambda _, __: None,
        deprecated=True,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.LAST_ONLINE,
        translation_key=XboxSensor.LAST_ONLINE,
        value_fn=(
            lambda x, _: x.last_seen_date_time_utc.replace(tzinfo=UTC)
            if x.last_seen_date_time_utc
            else None
        ),
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.FOLLOWING,
        translation_key=XboxSensor.FOLLOWING,
        value_fn=lambda x, _: x.detail.following_count if x.detail else None,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.FOLLOWER,
        translation_key=XboxSensor.FOLLOWER,
        value_fn=lambda x, _: x.detail.follower_count if x.detail else None,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.NOW_PLAYING,
        translation_key=XboxSensor.NOW_PLAYING,
        value_fn=lambda _, title: title.name if title else None,
        attributes_fn=now_playing_attributes,
        entity_picture_fn=title_logo,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.FRIENDS,
        translation_key=XboxSensor.FRIENDS,
        value_fn=lambda x, _: x.detail.friend_count if x.detail else None,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.IN_PARTY,
        translation_key=XboxSensor.IN_PARTY,
        value_fn=(
            lambda x, _: x.multiplayer_summary.in_party
            if x.multiplayer_summary
            else None
        ),
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.JOIN_RESTRICTIONS,
        translation_key=XboxSensor.JOIN_RESTRICTIONS,
        value_fn=join_restrictions,
        device_class=SensorDeviceClass.ENUM,
        options=list(MAP_JOIN_RESTRICTIONS.values()),
    ),
)

STORAGE_SENSOR_DESCRIPTIONS: tuple[XboxStorageDeviceSensorEntityDescription, ...] = (
    XboxStorageDeviceSensorEntityDescription(
        key=XboxSensor.TOTAL_STORAGE,
        translation_key=XboxSensor.TOTAL_STORAGE,
        value_fn=lambda x: x.total_space_bytes,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XboxStorageDeviceSensorEntityDescription(
        key=XboxSensor.FREE_STORAGE,
        translation_key=XboxSensor.FREE_STORAGE,
        value_fn=lambda x: x.free_space_bytes,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: XboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Xbox Live friends."""
    coordinator = config_entry.runtime_data.status
    if TYPE_CHECKING:
        assert config_entry.unique_id
    async_add_entities(
        [
            XboxSensorEntity(coordinator, config_entry.unique_id, description)
            for description in SENSOR_DESCRIPTIONS
            if check_deprecated_entity(
                hass, config_entry.unique_id, description, SENSOR_DOMAIN
            )
        ]
    )
    for subentry_id, subentry in config_entry.subentries.items():
        async_add_entities(
            [
                XboxSensorEntity(coordinator, subentry.unique_id, description)
                for description in SENSOR_DESCRIPTIONS
                if subentry.unique_id
                and check_deprecated_entity(
                    hass, subentry.unique_id, description, SENSOR_DOMAIN
                )
                and subentry.unique_id in coordinator.data.presence
                and subentry.subentry_type == "friend"
            ],
            config_subentry_id=subentry_id,
        )

    consoles_coordinator = config_entry.runtime_data.consoles

    async_add_entities(
        [
            XboxStorageDeviceSensorEntity(
                console, storage_device, consoles_coordinator, description
            )
            for description in STORAGE_SENSOR_DESCRIPTIONS
            for console in coordinator.consoles.result
            if console.storage_devices
            for storage_device in console.storage_devices
        ]
    )


class XboxSensorEntity(XboxBaseEntity, SensorEntity):
    """Representation of a Xbox presence state."""

    entity_description: XboxSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the requested attribute."""
        return self.entity_description.value_fn(self.data, self.title_info)


class XboxStorageDeviceSensorEntity(
    CoordinatorEntity[XboxConsolesCoordinator], SensorEntity
):
    """Console storage device entity for the Xbox integration."""

    _attr_has_entity_name = True
    entity_description: XboxStorageDeviceSensorEntityDescription

    def __init__(
        self,
        console: SmartglassConsole,
        storage_device: StorageDevice,
        coordinator: XboxConsolesCoordinator,
        entity_description: XboxStorageDeviceSensorEntityDescription,
    ) -> None:
        """Initialize the Xbox Console entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self.client = coordinator.client
        self._console = console
        self._storage_device = storage_device
        self._attr_unique_id = (
            f"{console.id}_{storage_device.storage_device_id}_{entity_description.key}"
        )
        self._attr_translation_placeholders = {
            CONF_NAME: storage_device.storage_device_name
        }

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, console.id)},
            manufacturer="Microsoft",
            model=MAP_MODEL.get(self._console.console_type, "Unknown"),
            name=console.name,
        )

    @property
    def data(self) -> StorageDevice | None:
        """Storage device data."""
        consoles = self.coordinator.data.result
        console = next((c for c in consoles if c.id == self._console.id), None)
        if not console or not console.storage_devices:
            return None

        return next(
            (
                d
                for d in console.storage_devices
                if d.storage_device_id == self._storage_device.storage_device_id
            ),
            None,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the requested attribute."""

        return self.entity_description.value_fn(self.data) if self.data else None
