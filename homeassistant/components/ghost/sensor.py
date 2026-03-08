"""Sensor platform for Ghost."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CURRENCY, DOMAIN, MANUFACTURER, MODEL
from .coordinator import GhostData, GhostDataUpdateCoordinator

if TYPE_CHECKING:
    from . import GhostConfigEntry

# Coordinator handles batching, no limit needed.
PARALLEL_UPDATES = 0


def _get_currency_value(currency_data: dict[str, Any]) -> int | None:
    """Extract the first currency value from a currency dict."""
    if not currency_data:
        return None
    first_value = next(iter(currency_data.values()), None)
    if first_value is None:
        return None
    return int(first_value)


@dataclass(frozen=True, kw_only=True)
class GhostSensorEntityDescription(SensorEntityDescription):
    """Describes a Ghost sensor entity."""

    value_fn: Callable[[GhostData], str | int | None]


SENSORS: tuple[GhostSensorEntityDescription, ...] = (
    # Core member metrics
    GhostSensorEntityDescription(
        key="total_members",
        translation_key="total_members",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.members.get("total", 0),
    ),
    GhostSensorEntityDescription(
        key="paid_members",
        translation_key="paid_members",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.members.get("paid", 0),
    ),
    GhostSensorEntityDescription(
        key="free_members",
        translation_key="free_members",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.members.get("free", 0),
    ),
    GhostSensorEntityDescription(
        key="comped_members",
        translation_key="comped_members",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.members.get("comped", 0),
    ),
    # Post metrics
    GhostSensorEntityDescription(
        key="published_posts",
        translation_key="published_posts",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.posts.get("published", 0),
    ),
    GhostSensorEntityDescription(
        key="draft_posts",
        translation_key="draft_posts",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.posts.get("drafts", 0),
    ),
    GhostSensorEntityDescription(
        key="scheduled_posts",
        translation_key="scheduled_posts",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.posts.get("scheduled", 0),
    ),
    GhostSensorEntityDescription(
        key="latest_post",
        translation_key="latest_post",
        value_fn=lambda data: (
            data.latest_post.get("title") if data.latest_post else None
        ),
    ),
    # Email metrics
    GhostSensorEntityDescription(
        key="latest_email",
        translation_key="latest_email",
        value_fn=lambda data: (
            data.latest_email.get("title") if data.latest_email else None
        ),
    ),
    GhostSensorEntityDescription(
        key="latest_email_sent",
        translation_key="latest_email_sent",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: (
            data.latest_email.get("email_count") if data.latest_email else None
        ),
    ),
    GhostSensorEntityDescription(
        key="latest_email_opened",
        translation_key="latest_email_opened",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: (
            data.latest_email.get("opened_count") if data.latest_email else None
        ),
    ),
    GhostSensorEntityDescription(
        key="latest_email_open_rate",
        translation_key="latest_email_open_rate",
        native_unit_of_measurement="%",
        value_fn=lambda data: (
            data.latest_email.get("open_rate") if data.latest_email else None
        ),
    ),
    GhostSensorEntityDescription(
        key="latest_email_clicked",
        translation_key="latest_email_clicked",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: (
            data.latest_email.get("clicked_count") if data.latest_email else None
        ),
    ),
    GhostSensorEntityDescription(
        key="latest_email_click_rate",
        translation_key="latest_email_click_rate",
        native_unit_of_measurement="%",
        value_fn=lambda data: (
            data.latest_email.get("click_rate") if data.latest_email else None
        ),
    ),
    # Social/ActivityPub metrics
    GhostSensorEntityDescription(
        key="socialweb_followers",
        translation_key="socialweb_followers",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.activitypub.get("followers", 0),
    ),
    GhostSensorEntityDescription(
        key="socialweb_following",
        translation_key="socialweb_following",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.activitypub.get("following", 0),
    ),
    # Engagement metrics
    GhostSensorEntityDescription(
        key="total_comments",
        translation_key="total_comments",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.comments,
    ),
)


REVENUE_SENSORS: tuple[GhostSensorEntityDescription, ...] = (
    GhostSensorEntityDescription(
        key="mrr",
        translation_key="mrr",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=0,
        value_fn=lambda data: _get_currency_value(data.mrr),
    ),
    GhostSensorEntityDescription(
        key="arr",
        translation_key="arr",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=0,
        value_fn=lambda data: _get_currency_value(data.arr),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GhostConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ghost sensors based on a config entry."""
    coordinator = entry.runtime_data.coordinator

    entities: list[GhostSensorEntity | GhostNewsletterSensorEntity] = [
        GhostSensorEntity(coordinator, description, entry) for description in SENSORS
    ]

    # Add revenue sensors only when Stripe is linked.
    if coordinator.data.mrr:
        entities.extend(
            GhostSensorEntity(coordinator, description, entry)
            for description in REVENUE_SENSORS
        )

    async_add_entities(entities)

    newsletter_added: set[str] = set()

    @callback
    def _async_add_newsletter_entities() -> None:
        """Add newsletter entities when new newsletters appear."""
        nonlocal newsletter_added

        new_newsletters = {
            newsletter_id
            for newsletter_id, newsletter in coordinator.data.newsletters.items()
            if newsletter.get("status") == "active"
        } - newsletter_added

        if not new_newsletters:
            return

        async_add_entities(
            GhostNewsletterSensorEntity(
                coordinator,
                entry,
                newsletter_id,
                coordinator.data.newsletters[newsletter_id].get("name", "Newsletter"),
            )
            for newsletter_id in new_newsletters
        )
        newsletter_added |= new_newsletters

    _async_add_newsletter_entities()
    entry.async_on_unload(
        coordinator.async_add_listener(_async_add_newsletter_entities)
    )


class GhostSensorEntity(CoordinatorEntity[GhostDataUpdateCoordinator], SensorEntity):
    """Representation of a Ghost sensor."""

    entity_description: GhostSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GhostDataUpdateCoordinator,
        description: GhostSensorEntityDescription,
        entry: GhostConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=coordinator.api.api_url,
        )

    @property
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class GhostNewsletterSensorEntity(
    CoordinatorEntity[GhostDataUpdateCoordinator], SensorEntity
):
    """Representation of a Ghost newsletter subscriber sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "newsletter_subscribers"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: GhostDataUpdateCoordinator,
        entry: GhostConfigEntry,
        newsletter_id: str,
        newsletter_name: str,
    ) -> None:
        """Initialize the newsletter sensor."""
        super().__init__(coordinator)
        self._newsletter_id = newsletter_id
        self._newsletter_name = newsletter_name
        self._attr_unique_id = f"{entry.unique_id}_newsletter_{newsletter_id}"
        self._attr_translation_placeholders = {"newsletter_name": newsletter_name}
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=coordinator.api.api_url,
        )

    def _get_newsletter_by_id(self) -> dict[str, Any] | None:
        """Get newsletter data by ID."""
        return self.coordinator.data.newsletters.get(self._newsletter_id)

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        if not super().available or self.coordinator.data is None:
            return False
        return self._newsletter_id in self.coordinator.data.newsletters

    @property
    def native_value(self) -> int | None:
        """Return the subscriber count for this newsletter."""
        if newsletter := self._get_newsletter_by_id():
            count: int = newsletter.get("count", {}).get("members", 0)
            return count
        return None
