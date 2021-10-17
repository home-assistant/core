"""Show the amount of records in a user's Discogs collection."""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
import logging
from random import randrange
from typing import Callable

from dateutil.tz import tzutc
import discogs_client
from discogs_client.models import Listing, Release
from feedparser import parse as parse_feed
import voluptuous as vol
from voluptuous.validators import Boolean

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE
import homeassistant.helpers.config_validation as cv
from homeassistant.util.yaml.objects import NodeListClass

_LOGGER = logging.getLogger(__name__)

ATTR_IDENTITY = "identity"

ATTRIBUTION = "Data provided by Discogs"

DEFAULT_NAME = "Discogs"

ICON_RECORD = "mdi:album"
ICON_PLAYER = "mdi:record-player"
ICON_MARKETPLACE = "mdi:shop"
UNIT_RECORDS = "records"

SCAN_INTERVAL = timedelta(minutes=10)

SENSOR_COLLECTION_TYPE = "collection"
SENSOR_WANTLIST_TYPE = "wantlist"
SENSOR_RANDOM_RECORD_TYPE = "random_record"
SENSOR_MARKETPLACE_ITEMS = "marketplace"

USER_SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_COLLECTION_TYPE,
        name="Collection",
        icon=ICON_RECORD,
        native_unit_of_measurement=UNIT_RECORDS,
    ),
    SensorEntityDescription(
        key=SENSOR_WANTLIST_TYPE,
        name="Wantlist",
        icon=ICON_RECORD,
        native_unit_of_measurement=UNIT_RECORDS,
    ),
    SensorEntityDescription(
        key=SENSOR_RANDOM_RECORD_TYPE,
        name="Random Record",
        icon=ICON_PLAYER,
    ),
)
SENSOR_KEYS: list[str] = [desc.key for desc in USER_SENSOR_TYPES] + [
    SENSOR_MARKETPLACE_ITEMS
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional("marketplace", default={}): NodeListClass,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: dict,
    add_entities: Callable[
        [list[DiscogsSensor] | list[DiscogMarketplaceSensor], Boolean], None
    ],
    discovery_info=None,
):
    """Set up the Discogs sensor."""
    token = config[CONF_TOKEN]
    name = config[CONF_NAME]

    try:
        _discogs_client = discogs_client.Client(SERVER_SOFTWARE, user_token=token)

        identity = _discogs_client.identity()

        discogs_data = {
            "user": identity.name,
            "folders": identity.collection_folders,
            "collection_count": identity.num_collection,
            "wantlist_count": identity.num_wantlist,
        }

        if marketplace_items := config.get("marketplace"):
            _build_marketplace_sensors(
                hass, _discogs_client, add_entities, marketplace_items
            )

    except discogs_client.exceptions.HTTPError:
        _LOGGER.error("API token is not valid")
        return

    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    entities = [
        DiscogsSensor(discogs_data, name, description)
        for description in USER_SENSOR_TYPES
        if description.key in monitored_conditions
    ]

    add_entities(entities, True)


def _build_marketplace_sensors(
    hass: HomeAssistant,
    _discogs_client: discogs_client,
    add_entities: Callable[[list[DiscogMarketplaceSensor], Boolean], None],
    marketplace_items: list,
):
    """Build Marketplace sensors and add them to the list."""
    marketplace_sensors: list[DiscogMarketplaceSensor] = []
    for release in marketplace_items:
        release_obj = Release(_discogs_client, {"id": release["id"]})
        release_obj.refresh()

        if release_obj.marketplace_stats.blocked_from_sale:
            _LOGGER.warning(
                f"Release {release_obj.id} - {release_obj.name} is Blocked from Sale on Discogs. Sensor will not be created."
            )
            continue

        if sensor_type := release.get("sort_by"):
            try:
                sensor_type = MarketplaceSensorType[sensor_type]
            except KeyError:
                _LOGGER.error(
                    f"{sensor_type} is not a valid Marketplace Sensor Type (valid: 'price', 'price_asc', 'quality', 'newest')"
                )
        else:
            sensor_type = MarketplaceSensorType[release["sort_by"]]

        key = f"discogs.{release_obj.title}_{release_obj.artists[0].name}_{release_obj.id}"

        hass.add_job(
            add_entities,
            [
                DiscogMarketplaceSensor(
                    name=f"{release_obj.title} ({release_obj.id})",
                    description=SensorEntityDescription(
                        key=key,
                        device_class="monetary"
                        if sensor_type
                        in [
                            MarketplaceSensorType.price_desc,
                            MarketplaceSensorType.price_asc,
                        ]
                        else None,
                        native_unit_of_measurement="listings",
                    ),
                    release=release_obj,
                    sensor_type=sensor_type,
                    client=_discogs_client,
                    limit=release.get("limit", 25),
                )
            ],
            True,
        )

    add_entities(marketplace_sensors, True)


class MarketplaceSensorType(Enum):
    """Defines what type of Marketplace Sensor it is, and what value it should use."""

    price_asc = "lowest_price"
    price_desc = "highest_price"
    quality = "highest_quality"
    newest = "newest_listing"

    def __str__(self) -> str:
        """Return the value of the enum."""
        return self.value


def quality_to_int(quality: str):
    """Convert the Quality String into a int value."""

    cond = {
        "Mint (M)": 8,
        "Near Mint (NM or M-)": 7,
        "Very Good Plus (VG+)": 6,
        "Very Good (VG)": 5,
        "Good Plus (G+)": 4,
        "Good (G)": 3,
        "Fair (F)": 2,
        "Poor (P)": 1,
    }

    return cond[quality]


class DiscogMarketplaceSensor(SensorEntity):
    """Monitor Discogs' Marketplace for new marketplace listings for releases based on a specific criteria."""

    def __init__(
        self,
        name,
        description: SensorEntityDescription,
        release: Release,
        sensor_type: MarketplaceSensorType,
        client: discogs_client.Client,
        limit: int,
    ):
        """Initialize the Discog Marketplace sensor."""
        self.client = client
        self.entity_description = description
        self.release = release
        self.sensor_type = sensor_type
        self.limit = limit
        self.listings: list = []
        self._attr_name = name

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._attr_unit_of_measurement

    @property
    def _attr_unit_of_measurement(self):
        """Determine the unit of measurement based on the sensor type."""
        if self.sensor_type in (
            MarketplaceSensorType.price_desc,
            MarketplaceSensorType.price_asc,
        ):
            return self.extra_state_attributes["currency"]
        elif self.sensor_type == MarketplaceSensorType.quality:
            return "(Media Quality + Sleeve Quality) ⁒ 2"
        elif self.sensor_type == MarketplaceSensorType.newest:
            return "Listings"

    @property
    def listing(self) -> None:
        """Get the listing based on the sensor type."""
        if not self.listings:
            return None

        if self.sensor_type == MarketplaceSensorType.price_asc:
            return self.cheapest_listing.__dict__["data"]
        elif self.sensor_type == MarketplaceSensorType.price_desc:
            return self.most_expensive_listing.__dict__["data"]
        elif self.sensor_type == MarketplaceSensorType.quality:
            return self.highest_quality_listing.__dict__["data"]
        elif self.sensor_type == MarketplaceSensorType.newest:
            return self.newest_listing.__dict__["data"]

    @property
    def _attr_state_class(self):
        """Determine state class based on the sensor type."""
        if not self.listing:
            return "total"

        if self.sensor_type in (
            MarketplaceSensorType.price_desc,
            MarketplaceSensorType.price_asc,
        ):
            return "measurement"
        elif self.sensor_type in (
            MarketplaceSensorType.quality,
            MarketplaceSensorType.newest,
        ):
            return "total"

    @property
    def native_value(self) -> int:
        """Determine the value of the sensor based on the sensor type."""
        if not self.listing:
            return 0

        if self.sensor_type == MarketplaceSensorType.price_asc:
            self._attr_name += " - Lowest Price"
            return self.extra_state_attributes["lowest_price"]
        elif self.sensor_type == MarketplaceSensorType.price_desc:
            self._attr_name += " - Highest Price"
            return self.extra_state_attributes["highest_price"]
        elif self.sensor_type == MarketplaceSensorType.quality:
            self._attr_name += " - Best Condition (Average)"
            return self.cond_avg()
        elif self.sensor_type == MarketplaceSensorType.newest:
            self._attr_name += " - Listings Available"
            return len(self.listings)

    def cond_avg(self):
        """Determine the Condition Average based on the Media + Sleeve Condition."""
        return (
            quality_to_int(self.extra_state_attributes["media_condition"])
            + quality_to_int(self.extra_state_attributes["sleeve_condition"])
        ) / 2

    @property
    def extra_state_attributes(self) -> dict:
        """Return the device state attributes of the sensor."""
        if self.listing is None or self.listings == [None]:
            return {
                "sensor_type": self.sensor_type.value,
                ATTR_ATTRIBUTION: ATTRIBUTION,
            }

        return {
            "sensor_type": self.sensor_type.value,
            "price": round(self.listing["price"]["value"], 2),
            "lowest_price": round(self.cheapest_listing.price.value, 2),
            "highest_price": round(self.most_expensive_listing.price.value, 2),
            "posted": self.listing["posted"],
            "currency": self.listing["price"]["currency"],
            "seller_name": self.listing["seller"]["username"],
            "link": self.listing["uri"],
            "allows_offers": self.listing["allow_offers"],
            "ships_from": self.listing["ships_from"],
            "media_condition": self.listing["condition"],
            "sleeve_condition": self.listing["sleeve_condition"],
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    @property
    def most_expensive_listing(self) -> dict | None:
        """Get the most expensive listing."""
        if not self.listings:
            return None
        return sorted(self.listings, key=lambda x: x.price.value, reverse=True)[0]

    @property
    def cheapest_listing(self) -> dict | None:
        """Get the cheapest listing."""
        if not self.listings:
            return None
        return sorted(self.listings, key=lambda x: x.price.value)[0]

    @property
    def newest_listing(self) -> dict | None:
        """Get the newest listing."""
        if not self.listings:
            return None
        return self.listings[0]

    @property
    def highest_quality_listing(self) -> dict | None:
        """Get the highest quality listing based on the average."""
        if not self.listings:
            return None
        return sorted(
            self.listings, key=lambda x: quality_to_int(x.condition), reverse=True
        )[0]

    def get_marketplace_listings(self, last_checked=None) -> None:
        """Check the Marketplace for new listings for a specific release."""
        _LOGGER.info(f"Getting Listings - {self.release.title}")
        page = 1
        entries = self.get_entries(page)
        while entries:
            # Get the the entries for the marketplace
            if last_checked and page == 1:
                t = entries[0].updated_parsed
                last_listed = datetime(*t[:5] + (min(t[5], 59)))
                last_listed = last_listed.replace(tzinfo=tzutc())

                # No new updates
                if last_listed <= last_checked:
                    _LOGGER.info(
                        f"No New Updates, updated at: {last_listed}, last checked at {last_checked}"
                    )
                    break
                else:
                    self.listings = []

            for entry in entries:
                # Get the info
                entry_url = entry.id
                listing_id = entry_url.replace("https://www.discogs.com/sell/item/", "")

                # Grab the Discog Listing from the RSS Feed
                listing = Listing(self.client, dict_={"id": listing_id})
                listing.refresh()
                self.listings.append(listing)

                if len(self.listings) == self.limit:
                    return None

            page += 1

    def get_entries(self, page):
        """Grab the most recent entries."""
        url = f"https://www.discogs.com/sell/mplistrss?output=rss&release_id={self.release.id}&page={page}"
        feed = parse_feed(url)
        entries = feed.entries

        # Reverse the entries so they're in order of newest -> oldest
        entries.reverse()
        return entries

    def update(self):
        """Update the Marketplace Listings."""
        if self.listings:
            last_newest = self.newest_listing.__dict__["data"]["posted"]
            self.get_marketplace_listings(last_checked=last_newest)
        else:
            self.get_marketplace_listings()


class DiscogsSensor(SensorEntity):
    """Create a new Discogs sensor for a specific type."""

    def __init__(self, discogs_data, name, description: SensorEntityDescription):
        """Initialize the Discogs sensor."""
        self.entity_description = description
        self._discogs_data = discogs_data
        self._attrs: dict = {}

        self._attr_name = f"{name} {description.name}"

    @property
    def extra_state_attributes(self):
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
                "format": f"{self._attrs['formats'][0]['name']} ({self._attrs['formats'][0]['descriptions'][0]})",
                "label": self._attrs["labels"][0]["name"],
                "released": self._attrs["year"],
                ATTR_ATTRIBUTION: ATTRIBUTION,
                ATTR_IDENTITY: self._discogs_data["user"],
            }

        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_IDENTITY: self._discogs_data["user"],
        }

    def get_random_record(self):
        """Get a random record suggestion from the user's collection."""
        # Index 0 in the folders is the 'All' folder
        collection = self._discogs_data["folders"][0]
        if collection.count > 0:
            random_index = randrange(collection.count)
            random_record = collection.releases[random_index].release

            self._attrs = random_record.data
            return f"{random_record.data['artists'][0]['name']} - {random_record.data['title']}"

        return None

    def update(self):
        """Set state to the amount of records in user's collection."""
        if self.entity_description.key == SENSOR_COLLECTION_TYPE:
            self._attr_native_value = self._discogs_data["collection_count"]
        elif self.entity_description.key == SENSOR_WANTLIST_TYPE:
            self._attr_native_value = self._discogs_data["wantlist_count"]
        else:
            self._attr_native_value = self.get_random_record()
