"""Binary sensor platform."""

from datetime import timedelta
import logging

from kat_bulgaria.obligations import KatApi, KatApiResponse

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import generate_entity_name
from .const import CONF_DRIVING_LICENSE, CONF_PERSON_EGN, CONF_PERSON_NAME, DOMAIN

SCAN_INTERVAL = timedelta(minutes=20)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform from config_entry."""

    person_name: str = str(entry.data.get(CONF_PERSON_NAME))
    person_egn: str = str(entry.data.get(CONF_PERSON_EGN))
    license_number: str = str(entry.data.get(CONF_DRIVING_LICENSE))

    api: KatApi = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [KatObligationsSensor(api, person_name, person_egn, license_number)], True
    )


class KatObligationsSensor(BinarySensorEntity):
    """A simple sensor."""

    _attr_has_entity_name = True

    @property
    def name(self) -> str | None:
        """Name of the entity."""
        return generate_entity_name(self.user_name)

    def __init__(self, api: KatApi, name: str, egn: str, license_number: str) -> None:
        """Initialize the sensor."""

        self.api = api

        self.user_egn = egn
        self.user_license_number = license_number
        self.user_name = name

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""

        resp: KatApiResponse[bool] = await self.api.async_check_obligations(
            self.user_egn, self.user_license_number
        )

        if resp.success:
            self._attr_is_on = resp.data
        else:
            _LOGGER.info(resp.error_message)
