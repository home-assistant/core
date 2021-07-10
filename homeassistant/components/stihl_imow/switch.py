"""Platform for sensor integration."""
from datetime import timedelta
import logging

from aiohttp import ClientResponseError
import async_timeout
from imow.common.exceptions import ApiMaintenanceError
from imow.common.mowerstate import MowerState

from homeassistant import config_entries, core
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import extract_properties_by_type
from .const import CONF_MOWER, DOMAIN
from .entity import ImowBaseEntity
from .maps import IMOW_SENSORS_MAP

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Add sensors for passed config_entry in HA."""
    config = hass.data[DOMAIN][config_entry.entry_id]

    mower_id = config[CONF_MOWER]["mower_id"]
    imow = config["api"]

    async def async_update_data():
        """
        Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        switch_entities = {}
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):

                mower_state = await imow.receive_mower_by_id(mower_id)
                del mower_state.__dict__["imow"]

                entities, device = extract_properties_by_type(mower_state, bool)

                for entity in entities:
                    if IMOW_SENSORS_MAP[entity]["switch"]:
                        switch_entities[entity] = entities[entity]

                return device, switch_entities

        except ClientResponseError as err:

            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err
        except ApiMaintenanceError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="imow_switch_entity",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=config["polling_interval"]),
    )

    #
    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    # If you do not want to retry setup on failure, use
    # coordinator.async_refresh() instead
    #
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        ImowSwitchSensorEntity(
            coordinator, coordinator.data[0], idx, mower_state_property
        )
        for idx, mower_state_property in enumerate(coordinator.data[1])
    )


class ImowSwitchSensorEntity(ImowBaseEntity, SwitchEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator, device_info, idx, mower_state_property):
        """Override the BaseEntity with Switch Entity content."""
        super().__init__(coordinator, device_info, idx, mower_state_property)
        self._is_on = self.sensor_data[self.property_name]
        self.api = self.coordinator.hass.data[DOMAIN][
            self.coordinator.config_entry.entry_id
        ]["api"]
        self._state = STATE_ON if self._is_on else STATE_OFF

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def is_on(self) -> bool:
        """State of the entity."""
        return self._is_on

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        new_mower_state: MowerState = await self.api.update_setting(
            self.key_device_infos["id"], self.property_name, True
        )
        self._is_on = new_mower_state.__dict__[self.property_name]
        self._state = STATE_ON if self._is_on else STATE_OFF

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        new_mower_state: MowerState = await self.api.update_setting(
            self.key_device_infos["id"], self.property_name, False
        )

        self._is_on = new_mower_state.__dict__[self.property_name]
        self._state = STATE_ON if self._is_on else STATE_OFF
