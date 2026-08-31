"""Show the amount of records in a user's Discogs collection."""

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

SENSOR_COLLECTION_TYPE = "collection"
SENSOR_WANTLIST_TYPE = "wantlist"
SENSOR_RANDOM_RECORD_TYPE = "random_record"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_COLLECTION_TYPE,
        translation_key="collection",
        icon=ICON_RECORD,
        native_unit_of_measurement=UNIT_RECORDS,
    ),
    SensorEntityDescription(
        key=SENSOR_WANTLIST_TYPE,
        translation_key="wantlist",
        icon=ICON_RECORD,
        native_unit_of_measurement=UNIT_RECORDS,
    ),
    SensorEntityDescription(
        key=SENSOR_RANDOM_RECORD_TYPE,
        translation_key="random_record",
        icon=ICON_PLAYER,
    ),
)
SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("monitored_conditions"): vol.All(cv.ensure_list, [cv.string]),
    }
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
    """Create a new Discogs sensor for a specific type."""

    _attr_attribution = "Data provided by Discogs"
    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        client: discogs_client.Client,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Discogs sensor."""
        self.entity_description = description
        self._client = client
        self._discogs_data: dict[str, Any] = {}
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
        """Return the device state attributes of the sensor."""
        if self._attr_native_value is None or self._attrs is None:
            return None

        if (
            self.entity_description.key == SENSOR_RANDOM_RECORD_TYPE
            and self._attr_native_value is not None
        ):
            return {
                "cat_no": self._attrs["labels"][0]["catno"],
                "cover_image": self._attrs["cover_image"],
                "format": (
                    f"{self._attrs['formats'][0]['name']}"
                    f" ({self._attrs['formats'][0]['descriptions'][0]})"
                ),
                "label": self._attrs["labels"][0]["name"],
                "released": self._attrs["year"],
                ATTR_IDENTITY: self._discogs_data["user"],
            }

        return {
            ATTR_IDENTITY: self._discogs_data["user"],
        }

    def get_random_record(self) -> str | None:
        """Get a random record suggestion from the user's collection."""
        # Index 0 in the folders is the 'All' folder
        collection = self._discogs_data["folders"][0]
        if collection.count > 0:
            random_index = random.randrange(collection.count)
            random_record = collection.releases[random_index].release

            self._attrs = random_record.data
            return (
                f"{random_record.data['artists'][0]['name']} -"
                f" {random_record.data['title']}"
            )

        return None

    def update(self) -> None:
        """Set state to the amount of records in user's collection."""
        identity = self._client.identity()
        self._discogs_data = {
            "user": identity.name,
            "folders": identity.collection_folders,
            "collection_count": identity.num_collection,
            "wantlist_count": identity.num_wantlist,
        }

        if self.entity_description.key == SENSOR_COLLECTION_TYPE:
            self._attr_native_value = self._discogs_data["collection_count"]
        elif self.entity_description.key == SENSOR_WANTLIST_TYPE:
            self._attr_native_value = self._discogs_data["wantlist_count"]
        else:
            self._attr_native_value = self.get_random_record()
