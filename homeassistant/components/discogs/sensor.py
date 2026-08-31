"""Sensor platform for Discogs."""

from datetime import timedelta
import random
from typing import Any, override

import discogs_client
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_NAME, DOMAIN

ATTR_IDENTITY = "identity"

ICON_RECORD = "mdi:album"
ICON_PLAYER = "mdi:record-player"
UNIT_RECORDS = "records"

SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("monitored_conditions"): vol.All(cv.ensure_list, [cv.string]),
    }
)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="collection",
        translation_key="collection",
        icon=ICON_RECORD,
        native_unit_of_measurement=UNIT_RECORDS,
    ),
    SensorEntityDescription(
        key="wantlist",
        translation_key="wantlist",
        icon=ICON_RECORD,
        native_unit_of_measurement=UNIT_RECORDS,
    ),
    SensorEntityDescription(
        key="random_record",
        translation_key="random_record",
        icon=ICON_PLAYER,
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import YAML configuration and forward to config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "import"},
        data={
            CONF_TOKEN: config[CONF_TOKEN],
            "name": config.get("name", DEFAULT_NAME),
        },
    )

    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_import_issue_cannot_connect",
            breaks_in_ha_version="2027.2.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue_cannot_connect",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Discogs",
            },
        )
        return

    if result.get("type") is FlowResultType.CREATE_ENTRY:
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2027.2.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Discogs",
            },
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Discogs sensor from a config entry."""
    client = await hass.async_add_executor_job(
        discogs_client.Client, SERVER_SOFTWARE, None, entry.data[CONF_TOKEN]
    )
    async_add_entities(
        (DiscogsSensor(entry, client, description) for description in SENSOR_TYPES),
        True,
    )


class DiscogsSensor(SensorEntity):
    """Representation of a Discogs sensor."""

    _attr_attribution = "Data provided by Discogs"
    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        client: discogs_client.Client,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._client = client
        self._attrs: dict[str, Any] = {}
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.discogs.com",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=entry.title,
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the extra state attributes."""
        if self.entity_description.key == "random_record" and self._attrs:
            return {
                ATTR_IDENTITY: self._attrs.get("username"),
                "cat_no": self._attrs.get("cat_no"),
                "cover_image": self._attrs.get("cover_image"),
                "format": self._attrs.get("format"),
                "label": self._attrs.get("label"),
                "released": self._attrs.get("released"),
            }
        return {ATTR_IDENTITY: self._attrs.get("username")}

    def update(self) -> None:
        """Fetch data from Discogs."""
        identity = self._client.identity()
        self._attrs["username"] = identity.name

        if self.entity_description.key == "collection":
            self._attr_native_value = identity.num_collection
        elif self.entity_description.key == "wantlist":
            self._attr_native_value = identity.num_wantlist
        else:
            self._attr_native_value = self._get_random_record(identity)

    def _get_random_record(self, identity: Any) -> str | None:
        """Get a random record from the user's collection."""
        folders = identity.collection_folders
        if folders and folders[0].count > 0:
            collection = folders[0]
            random_index = random.randrange(collection.count)
            release = collection.releases[random_index].release
            data = release.data
            artists = data.get("artists", [])
            artist_name = artists[0]["name"] if artists else "Unknown"
            labels = data.get("labels", [])
            formats = data.get("formats", [])
            fmt_entry = formats[0] if formats else {}
            fmt_descriptions = fmt_entry.get("descriptions", [])
            self._attrs.update(
                {
                    "cat_no": labels[0]["catno"] if labels else None,
                    "cover_image": data.get("cover_image"),
                    "format": (
                        f"{fmt_entry.get('name', '')} ({fmt_descriptions[0]})"
                        if fmt_descriptions
                        else fmt_entry.get("name")
                    ),
                    "label": labels[0]["name"] if labels else None,
                    "released": data.get("year"),
                }
            )
            return f"{artist_name} - {data.get('title', 'Unknown')}"
        return None
