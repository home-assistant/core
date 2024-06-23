"""Update coordinator for Knocki integration."""
from knocki import Trigger

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class KnockiCoordinator(DataUpdateCoordinator[dict[str, Trigger]]):
