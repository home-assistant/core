"""TFA.me station integration: coordinator.py."""

import logging
import socket

from tfa_me_ha_local.client import (
    TFAmeClient,
    TFAmeConnectionError,
    TFAmeException,
    TFAmeHTTPError,
    TFAmeJSONError,
    TFAmeTimeoutError,
)
from tfa_me_ha_local.data import TFAmeDataForHA

from homeassistant.components.sensor import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type TFAmeConfigEntry = ConfigEntry[TFAmeDataCoordinator]


class TFAmeDataCoordinator(DataUpdateCoordinator):
    """Class for managing data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        host: str,
        interval: timedelta,
        name_with_station_id: bool,
    ) -> None:
        """Initialize data update coordinator."""
        self.host = host  # from config_entry.data[CONF_IP_ADDRESS]
        self.first_init = 0
        self.ha = hass
        self.config_entry = config_entry
        self.sensor_entity_list: list[str] = []  # [Entity ID strings]
        self.name_with_station_id = (
            name_with_station_id  # from config_entry.data[CONF_NAME_WITH_STATION_ID]
        )
        self.gateway_id = ""
        self.poll_interval = interval  # former from config_entry.data[CONF_INTERVAL]
        self.entities_added = 0

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=self.poll_interval,
            config_entry=self.config_entry,
        )

    async def _async_update_data(self):
        """Request and update data."""
        parsed_data = {}  # dict

        # Try to get an IP for a mDNS host name:
        # - when IP can be solved it returns the IP
        # - when it is an IP it just returns the IP
        if "-" in self.host:
            # station ID, contains "-"
            mdns_name = f"tfa-me-{self.host:}.local"
            resolved_host = await self.resolve_mdns(mdns_name)
        else:
            resolved_host = self.host

        # Try to update data from station URL: e.g. "http://192.168.1.38/sensors"
        try:
            # New TFA.me client
            tfa_me_client = TFAmeClient(resolved_host, "sensors", log_level=1)

            # Fetch all available sensors as JSON from TFA.me station
            json_data = await tfa_me_client.async_get_sensors()

            # New TFA.me data structure
            tfa_me_data = TFAmeDataForHA(multiple_entities=True)

            # Convert JSON to TFA.me data for HA
            parsed_data = tfa_me_data.json_to_entities(json_data=json_data)
            self.gateway_id = tfa_me_data.get_gateway_id()

        # Specific error mapping
        except (TFAmeTimeoutError, TFAmeConnectionError) as err:
            # Device not reachable → after first start "NotReady", then "UpdateFailed"
            msg: str = "Timeout general connection error: " + str(err.__doc__)
            _LOGGER.error(msg)
            if self.first_init == 0:
                raise ConfigEntryNotReady(
                    f"Cannot reach {resolved_host}: {err}"
                ) from err
            raise UpdateFailed(f"Connection problem: {err}") from err

        except (TFAmeHTTPError, TFAmeJSONError) as err:
            # Device responding but data invalid
            msg: str = "HTTP or invalid response error: " + str(err.__doc__)
            _LOGGER.error(msg)
            raise UpdateFailed(f"Invalid response: {err}") from err

        except TFAmeException as err:
            # All other client errors
            msg: str = "All other client errors: " + str(err.__doc__)
            _LOGGER.error(msg)
            if self.first_init == 0:
                raise ConfigEntryNotReady(f"TFA.me client error: {err}") from err
            raise UpdateFailed(f"TFA.me client error: {err}") from err

        except Exception as err:
            # Fallback for unexpected errors
            msg: str = "Fallback for unexpected errors: " + str(err.__doc__)
            _LOGGER.error(msg)
            if self.first_init == 0:
                raise ConfigEntryNotReady(f"Unexpected error: {err}") from err
            raise UpdateFailed(f"Unexpected error: {err}") from err

        else:
            if self.first_init < 2:
                self.first_init += 1

            # values are available with self.coordinator.data[self.entity_id]["keyword"]
            return parsed_data

    async def resolve_mdns(self, host_str: str) -> str:
        """Try to resolve host name and to get IP."""
        try:
            return socket.gethostbyname(host_str)  # Resolve: name to IP
        except socket.gaierror:
            return host_str  # Error, just return original string
