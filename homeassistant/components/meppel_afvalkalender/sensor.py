"""Support for Meppel Afvalkalender sensors."""
from typing import Any, Dict

from meppel_afvalkalender import (
    WASTE_TYPE_NON_RECYCLABLE,
    WASTE_TYPE_ORGANIC,
    WASTE_TYPE_PAPER,
    WASTE_TYPE_PLASTIC,
    MeppelAfvalkalender,
    MeppelAfvalkalenderConnectionError,
)

from homeassistant.components.meppel_afvalkalender.const import DATA_UPDATE, DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Meppel Afvalkalender sensor based on a config entry."""
    meppel_afvalkalender = hass.data[DOMAIN][entry.data[CONF_ID]]

    try:
        await meppel_afvalkalender.update()
    except MeppelAfvalkalenderConnectionError as exception:
        raise PlatformNotReady from exception

    sensors = [
        MeppelAfvalkalenderSensor(
            meppel_afvalkalender,
            unique_id=entry.data[CONF_ID],
            name=f"{WASTE_TYPE_NON_RECYCLABLE} Waste Pickup",
            waste_type=WASTE_TYPE_NON_RECYCLABLE,
            icon="mdi:delete-empty",
        ),
        MeppelAfvalkalenderSensor(
            meppel_afvalkalender,
            unique_id=entry.data[CONF_ID],
            name=f"{WASTE_TYPE_ORGANIC} Waste Pickup",
            waste_type=WASTE_TYPE_ORGANIC,
            icon="mdi:delete-empty",
        ),
        MeppelAfvalkalenderSensor(
            meppel_afvalkalender,
            unique_id=entry.data[CONF_ID],
            name=f"{WASTE_TYPE_PAPER} Waste Pickup",
            waste_type=WASTE_TYPE_PAPER,
            icon="mdi:delete-empty",
        ),
        MeppelAfvalkalenderSensor(
            meppel_afvalkalender,
            unique_id=entry.data[CONF_ID],
            name=f"{WASTE_TYPE_PLASTIC} Waste Pickup",
            waste_type=WASTE_TYPE_PLASTIC,
            icon="mdi:delete-empty",
        ),
    ]

    async_add_entities(sensors, True)


class MeppelAfvalkalenderSensor(Entity):
    """Defines a Meppel Afvalkalender sensor."""

    def __init__(
        self,
        meppel_afvalkalender: MeppelAfvalkalender,
        unique_id: str,
        name: str,
        waste_type: str,
        icon: str,
    ) -> None:
        """Initialize the Meppel Afvalkalender entity."""
        self._available = True
        self._unique_id = unique_id
        self._icon = icon
        self._name = name
        self._meppel_afvalkalender = meppel_afvalkalender
        self._waste_type = waste_type
        self._unsub_dispatcher = None

        self._state = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{DOMAIN}_{self._unique_id}_{self._waste_type}"

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return False

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, DATA_UPDATE, self._schedule_immediate_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect from update signal."""
        self._unsub_dispatcher()

    @callback
    def _schedule_immediate_update(self, unique_id: str) -> None:
        """Schedule an immediate update of the entity."""
        if unique_id == self._unique_id:
            self.async_schedule_update_ha_state(True)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self) -> None:
        """Update Meppel Afvalkalender entity."""
        next_pickup = await self._meppel_afvalkalender.next_pickup(self._waste_type)
        if next_pickup is not None:
            self._state = next_pickup.date().isoformat()

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about Meppel Afvalkalender."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": "Meppel Afvalkalender",
            "manufacturer": "Meppel Afvalkalender",
        }
