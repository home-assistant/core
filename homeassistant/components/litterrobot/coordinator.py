"""The Litter-Robot coordinator."""

from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
import logging

from pylitterbot import Account, FeederRobot, LitterRobot
from pylitterbot.exceptions import LitterRobotException, LitterRobotLoginException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=5)

type LitterRobotConfigEntry = ConfigEntry[LitterRobotDataUpdateCoordinator]


class LitterRobotDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """The Litter-Robot data update coordinator."""

    config_entry: LitterRobotConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: LitterRobotConfigEntry
    ) -> None:
        """Initialize the Litter-Robot data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

        self.account = Account(websession=async_get_clientsession(hass))
        self.previous_members: set[str] = set()

    async def _async_update_data(self) -> None:
        """Update all device states from the Litter-Robot API."""
        try:
            await self.account.load_robots(subscribe_for_updates=True)
            await self.account.load_pets()
            for pet in self.account.pets:
                # Need to fetch weight history for `get_visits_since`
                await pet.fetch_weight_history()
        except LitterRobotLoginException as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_credentials"
            ) from ex
        except LitterRobotException as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(ex)},
            ) from ex

        current_members = {robot.serial for robot in self.account.robots} | {
            pet.id for pet in self.account.pets
        }
        if stale_members := self.previous_members - current_members:
            device_registry = dr.async_get(self.hass)
            for device_id in stale_members:
                device = device_registry.async_get_device(
                    identifiers={(DOMAIN, device_id)}
                )
                if device:
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )
        self.previous_members = current_members

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            await self.account.connect(
                username=self.config_entry.data[CONF_USERNAME],
                password=self.config_entry.data[CONF_PASSWORD],
                load_robots=True,
                subscribe_for_updates=True,
                load_pets=True,
            )
        except LitterRobotLoginException as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_credentials"
            ) from ex
        except LitterRobotException as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(ex)},
            ) from ex

    def litter_robots(self) -> Generator[LitterRobot]:
        """Get Litter-Robots from the account."""
        return (
            robot for robot in self.account.robots if isinstance(robot, LitterRobot)
        )

    def feeder_robots(self) -> Generator[FeederRobot]:
        """Get Feeder-Robots from the account."""
        return (
            robot for robot in self.account.robots if isinstance(robot, FeederRobot)
        )
