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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CURRENCY, DOMAIN, MANUFACTURER, MODEL
from .coordinator import GhostDataUpdateCoordinator

if TYPE_CHECKING:
    from . import GhostConfigEntry

# Coordinator handles batching, no limit needed.
PARALLEL_UPDATES = 0


def _nested_get(data: dict[str, Any], *keys: str, default: Any = 0) -> Any:
    """Get nested dict value safely."""
    result: Any = data
    for key in keys:
        if not isinstance(result, dict):
            return default
        result = result.get(key, {})
    return result if result != {} else default


def _get_device_info(
    coordinator: GhostDataUpdateCoordinator, entry: GhostConfigEntry
) -> DeviceInfo:
    """Get device info for Ghost sensors."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=coordinator.site_title,
        manufacturer=MANUFACTURER,
        model=MODEL,
        configuration_url=coordinator.api.api_url,
    )


def _get_mrr_value(data: dict[str, Any]) -> int | None:
    """Extract MRR value, converting cents to whole dollars."""
    mrr_data = data.get("mrr", {})
    if not mrr_data:
        return None
    first_value = next(iter(mrr_data.values()), None)
    if first_value is None:
        return None
    return int(round(first_value / 100))


@dataclass(frozen=True, kw_only=True)
class GhostSensorEntityDescription(SensorEntityDescription):
    """Describes a Ghost sensor entity."""

    value_fn: Callable[[dict[str, Any]], str | int | None]
    extra_attrs_fn: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None


SENSORS: tuple[GhostSensorEntityDescription, ...] = (
    # Core member metrics
    GhostSensorEntityDescription(
        key="total_members",
        translation_key="total_members",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: _nested_get(data, "members", "total"),
    ),
    GhostSensorEntityDescription(
        key="paid_members",
        translation_key="paid_members",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: _nested_get(data, "members", "paid"),
    ),
    GhostSensorEntityDescription(
        key="free_members",
        translation_key="free_members",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: _nested_get(data, "members", "free"),
    ),
    GhostSensorEntityDescription(
        key="comped_members",
        translation_key="comped_members",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: _nested_get(data, "members", "comped"),
    ),
    # Revenue metrics
    GhostSensorEntityDescription(
        key="mrr",
        translation_key="mrr",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=0,
        value_fn=_get_mrr_value,
    ),
    GhostSensorEntityDescription(
        key="arr",
        translation_key="arr",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=0,
        value_fn=lambda data: (mrr := _get_mrr_value(data)) and mrr * 12,
    ),
    # Post metrics
    GhostSensorEntityDescription(
        key="published_posts",
        translation_key="published_posts",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: _nested_get(data, "posts", "published"),
    ),
    GhostSensorEntityDescription(
        key="draft_posts",
        translation_key="draft_posts",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: _nested_get(data, "posts", "drafts"),
    ),
    GhostSensorEntityDescription(
        key="scheduled_posts",
        translation_key="scheduled_posts",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: _nested_get(data, "posts", "scheduled"),
    ),
    GhostSensorEntityDescription(
        key="latest_post",
        translation_key="latest_post",
        value_fn=lambda data: (
            data.get("latest_post", {}).get("title")
            if data.get("latest_post")
            else None
        ),
        extra_attrs_fn=lambda data: (
            {
                "url": post.get("url"),
                "published_at": post.get("published_at"),
                "slug": post.get("slug"),
            }
            if (post := data.get("latest_post"))
            else None
        ),
    ),
    # Email metrics
    GhostSensorEntityDescription(
        key="latest_email",
        translation_key="latest_email",
        value_fn=lambda data: (
            data.get("latest_email", {}).get("title")
            if data.get("latest_email")
            else None
        ),
        extra_attrs_fn=lambda data: (
            {
                "subject": email.get("subject"),
                "sent_at": email.get("submitted_at"),
                "sent_to": email.get("email_count"),
                "delivered": email.get("delivered_count"),
                "opened": email.get("opened_count"),
                "clicked": email.get("clicked_count"),
                "failed": email.get("failed_count"),
                "open_rate": email.get("open_rate"),
                "click_rate": email.get("click_rate"),
            }
            if (email := data.get("latest_email"))
            else None
        ),
    ),
    GhostSensorEntityDescription(
        key="latest_email_sent",
        translation_key="latest_email_sent",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: (
            data.get("latest_email", {}).get("email_count")
            if data.get("latest_email")
            else None
        ),
    ),
    GhostSensorEntityDescription(
        key="latest_email_opened",
        translation_key="latest_email_opened",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: (
            data.get("latest_email", {}).get("opened_count")
            if data.get("latest_email")
            else None
        ),
    ),
    GhostSensorEntityDescription(
        key="latest_email_open_rate",
        translation_key="latest_email_open_rate",
        native_unit_of_measurement="%",
        value_fn=lambda data: (
            data.get("latest_email", {}).get("open_rate")
            if data.get("latest_email")
            else None
        ),
    ),
    GhostSensorEntityDescription(
        key="latest_email_clicked",
        translation_key="latest_email_clicked",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: (
            data.get("latest_email", {}).get("clicked_count")
            if data.get("latest_email")
            else None
        ),
    ),
    GhostSensorEntityDescription(
        key="latest_email_click_rate",
        translation_key="latest_email_click_rate",
        native_unit_of_measurement="%",
        value_fn=lambda data: (
            data.get("latest_email", {}).get("click_rate")
            if data.get("latest_email")
            else None
        ),
    ),
    # Social/ActivityPub metrics
    GhostSensorEntityDescription(
        key="socialweb_followers",
        translation_key="socialweb_followers",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: _nested_get(data, "activitypub", "followers"),
    ),
    GhostSensorEntityDescription(
        key="socialweb_following",
        translation_key="socialweb_following",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: _nested_get(data, "activitypub", "following"),
    ),
    # Engagement metrics
    GhostSensorEntityDescription(
        key="total_comments",
        translation_key="total_comments",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("comments", 0),
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

    # Add dynamic newsletter sensors (active only).
    for newsletter in coordinator.data.get("newsletters", []):
        newsletter_id = newsletter.get("id")
        newsletter_name = newsletter.get("name", "Newsletter")
        newsletter_status = newsletter.get("status")
        if newsletter_id and newsletter_status == "active":
            entities.append(
                GhostNewsletterSensorEntity(
                    coordinator, entry, newsletter_id, newsletter_name
                )
            )

    async_add_entities(entities)


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
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = _get_device_info(coordinator, entry)

    @property
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.entity_description.extra_attrs_fn is not None:
            return self.entity_description.extra_attrs_fn(self.coordinator.data)
        return None


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
        self._attr_unique_id = f"{entry.entry_id}_newsletter_{newsletter_id}"
        self._attr_translation_placeholders = {"newsletter_name": newsletter_name}
        self._attr_device_info = _get_device_info(coordinator, entry)

    def _get_newsletter_by_id(self) -> dict[str, Any] | None:
        """Get newsletter data by ID."""
        newsletters = self.coordinator.data.get("newsletters", [])
        return next(
            (n for n in newsletters if n.get("id") == self._newsletter_id), None
        )

    @property
    def native_value(self) -> int | None:
        """Return the subscriber count for this newsletter."""
        if newsletter := self._get_newsletter_by_id():
            count: int = newsletter.get("count", {}).get("members", 0)
            return count
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if newsletter := self._get_newsletter_by_id():
            return {
                "newsletter_id": self._newsletter_id,
                "status": newsletter.get("status"),
            }
        return None
