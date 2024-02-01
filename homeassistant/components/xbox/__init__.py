"""The xbox integration."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
import logging

from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.api.provider.catalog.const import SYSTEM_PFN_ID_MAP
from xbox.webapi.api.provider.catalog.models import AlternateIdType, Product
from xbox.webapi.api.provider.people.models import (
    PeopleResponse,
    Person,
    PresenceDetail,
)
from xbox.webapi.api.provider.smartglass.models import (
    SmartglassConsoleList,
    SmartglassConsoleStatus,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import api
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up xbox from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    auth = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    client = XboxLiveClient(auth)
    consoles: SmartglassConsoleList = await client.smartglass.get_console_list()
    _LOGGER.debug(
        "Found %d consoles: %s",
        len(consoles.result),
        consoles.dict(),
    )

    coordinator = XboxUpdateCoordinator(hass, client, consoles)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": XboxLiveClient(auth),
        "consoles": consoles,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Unsub from coordinator updates
        hass.data[DOMAIN][entry.entry_id]["sensor_unsub"]()
        hass.data[DOMAIN][entry.entry_id]["binary_sensor_unsub"]()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


@dataclass
class ConsoleData:
    """Xbox console status data."""

    status: SmartglassConsoleStatus
    app_details: Product | None


@dataclass
class PresenceData:
    """Xbox user presence data."""

    xuid: str
    gamertag: str
    display_pic: str
    online: bool
    status: str
    in_party: bool
    in_game: bool
    in_multiplayer: bool
    gamer_score: str
    gold_tenure: str | None
    account_tier: str


@dataclass
class XboxData:
    """Xbox dataclass for update coordinator."""

    consoles: dict[str, ConsoleData]
    presence: dict[str, PresenceData]


class XboxUpdateCoordinator(DataUpdateCoordinator[XboxData]):  # pylint: disable=hass-enforce-coordinator-module
    """Store Xbox Console Status."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: XboxLiveClient,
        consoles: SmartglassConsoleList,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=10),
        )
        self.data = XboxData({}, {})
        self.client: XboxLiveClient = client
        self.consoles: SmartglassConsoleList = consoles

    async def _async_update_data(self) -> XboxData:
        """Fetch the latest console status."""
        # Update Console Status
        new_console_data: dict[str, ConsoleData] = {}
        for console in self.consoles.result:
            current_state: ConsoleData | None = self.data.consoles.get(console.id)
            status: SmartglassConsoleStatus = (
                await self.client.smartglass.get_console_status(console.id)
            )

            _LOGGER.debug(
                "%s status: %s",
                console.name,
                status.dict(),
            )

            # Setup focus app
            app_details: Product | None = None
            if current_state is not None:
                app_details = current_state.app_details

            if status.focus_app_aumid:
                if (
                    not current_state
                    or status.focus_app_aumid != current_state.status.focus_app_aumid
                ):
                    app_id = status.focus_app_aumid.split("!")[0]
                    id_type = AlternateIdType.PACKAGE_FAMILY_NAME
                    if app_id in SYSTEM_PFN_ID_MAP:
                        id_type = AlternateIdType.LEGACY_XBOX_PRODUCT_ID
                        app_id = SYSTEM_PFN_ID_MAP[app_id][id_type]
                    catalog_result = (
                        await self.client.catalog.get_product_from_alternate_id(
                            app_id, id_type
                        )
                    )
                    if catalog_result and catalog_result.products:
                        app_details = catalog_result.products[0]
            else:
                app_details = None

            new_console_data[console.id] = ConsoleData(
                status=status, app_details=app_details
            )

        # Update user presence
        presence_data: dict[str, PresenceData] = {}
        batch: PeopleResponse = await self.client.people.get_friends_own_batch(
            [self.client.xuid]
        )
        own_presence: Person = batch.people[0]
        presence_data[own_presence.xuid] = _build_presence_data(own_presence)

        friends: PeopleResponse = await self.client.people.get_friends_own()
        for friend in friends.people:
            if not friend.is_favorite:
                continue

            presence_data[friend.xuid] = _build_presence_data(friend)

        return XboxData(new_console_data, presence_data)


def _build_presence_data(person: Person) -> PresenceData:
    """Build presence data from a person."""
    active_app: PresenceDetail | None = None
    with suppress(StopIteration):
        active_app = next(
            presence for presence in person.presence_details if presence.is_primary
        )

    return PresenceData(
        xuid=person.xuid,
        gamertag=person.gamertag,
        display_pic=person.display_pic_raw,
        online=person.presence_state == "Online",
        status=person.presence_text,
        in_party=person.multiplayer_summary.in_party > 0,
        in_game=active_app is not None and active_app.is_game,
        in_multiplayer=person.multiplayer_summary.in_multiplayer_session,
        gamer_score=person.gamer_score,
        gold_tenure=person.detail.tenure,
        account_tier=person.detail.account_tier,
    )
