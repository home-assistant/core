"""Support for SleepIQ from SleepNumber."""
import dataclasses
from datetime import timedelta
import logging
from typing import Dict

from sleepyq import Bed, SideStatus, Sleepyq
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    CONFIG_ENTRY_UPDATE_SIGNAL_TEMPLATE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ICON_EMPTY,
    ICON_OCCUPIED,
    IS_IN_BED,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
        }
    },
    extra=vol.ALLOW_EXTRA,
)

DATA_SLEEPIQ = "data_sleepiq"

DEFAULT_COMPONENT_NAME = "SleepIQ {}"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


class SleepIQDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Bed]]):
    """SleepIQ data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        client: Sleepyq,
        update_interval: timedelta,
        username: str,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass, _LOGGER, name=f"{username}@SleepIQ", update_interval=update_interval
        )
        self.client = client

    async def async_update_config(self, config_entry: ConfigEntry) -> None:
        """Handle config update."""
        self.update_interval = timedelta(
            seconds=config_entry.options[CONF_SCAN_INTERVAL]
        )

    async def _async_update_data(self) -> Dict[str, Bed]:
        return {
            bed.bed_id: bed
            for bed in await self.hass.async_add_executor_job(
                self.client.beds_with_sleeper_status
            )
        }


@dataclasses.dataclass
class SleepIQHassData:
    """Home Assistant SleepIQ runtime data."""

    coordinators: Dict[str, SleepIQDataUpdateCoordinator] = dataclasses.field(
        default_factory=dict
    )


def _config_entry_update_signal_name(config_entry: ConfigEntry) -> str:
    """Get signal name for updates to a config entry."""
    return CONFIG_ENTRY_UPDATE_SIGNAL_TEMPLATE.format(config_entry.unique_id)


async def _async_signal_options_update(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Signal config entry options update."""
    async_dispatcher_send(
        hass, _config_entry_update_signal_name(config_entry), config_entry
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SleepIQ component."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={"username": conf[CONF_USERNAME], "password": conf[CONF_PASSWORD]},
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the SleepIQ config entry."""
    client = Sleepyq(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])

    try:
        await hass.async_add_executor_job(client.login)
    except ValueError:
        _LOGGER.error("SleepIQ login failed, double check your username and password")
        return False

    if CONF_SCAN_INTERVAL in entry.data:
        update_interval = timedelta(seconds=entry.data[CONF_SCAN_INTERVAL])
    else:
        update_interval = DEFAULT_SCAN_INTERVAL

    coordinator = SleepIQDataUpdateCoordinator(
        hass,
        client=client,
        update_interval=update_interval,
        username=entry.data[CONF_USERNAME],
    )

    # Call the SleepIQ API to refresh data
    await coordinator.async_config_entry_first_refresh()

    # Listen to config entry updates
    entry.async_on_unload(entry.add_update_listener(_async_signal_options_update))
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            _config_entry_update_signal_name(entry),
            coordinator.async_update_config,
        )
    )

    hass.data[DATA_SLEEPIQ] = SleepIQHassData()
    hass.data[DATA_SLEEPIQ].coordinators[entry.data[CONF_USERNAME]] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    hass.data[DATA_SLEEPIQ].coordinators.pop(config_entry.data[CONF_USERNAME])

    return unload_ok


class SleepIQBedSideEntity(CoordinatorEntity):
    """Entity class for a side of a SleepIQ bed."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Dict[str, Bed]],
        bed_id: str,
        side: str,
    ) -> None:
        """Initialize the SleepIQ side entity."""
        super().__init__(coordinator)
        self.bed_id = bed_id
        self.side = side

        # Added by subclass.
        self._name = ""

    @property
    def _bed(self) -> Bed:
        return self.coordinator.data[self.bed_id]

    @property
    def _side(self) -> SideStatus:
        return getattr(self._bed, self.side)

    @property
    def unique_id(self) -> str:
        """Return unique ID for the entity."""
        return f"{self.bed_id}_{self._side.sleeper.first_name}_{self._name}"

    @property
    def name(self) -> str:
        """Return name for the entity."""
        return f"SleepNumber {self._bed.name} {self._side.sleeper.first_name} {SENSOR_TYPES[self._name]}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON_OCCUPIED if self.is_on else ICON_EMPTY

    @property
    def is_on(self) -> bool:
        """Return true if the side is occupied."""
        return getattr(self._side, IS_IN_BED)
