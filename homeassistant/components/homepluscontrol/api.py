"""API for Legrand Home+ Control bound to Home Assistant OAuth."""
import logging
import time

from homepluscontrol.authentication import HomePlusOAuth2Async
from homepluscontrol.homeplusinteractivemodule import HomePlusInteractiveModule
from homepluscontrol.homeplusplant import HomePlusPlant

from homeassistant import config_entries, core
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .const import CONF_REDIRECT_URI, CONF_SUBSCRIPTION_KEY, DOMAIN, PLANT_URL

# The Legrand Home+ Control API has very limited request quotas - at the time of writing, it is limited
# to 500 calls per day (resets at 00:00) - so we want to keep updates to a minimum.

# Seconds between API checks for plant information updates. This is expected to change very little over time
# because a user's plants (homes) should rarely change.
PLANT_UPDATE_INTERVAL = 7200  # 120 minutes

# Seconds between API checks for plant topology updates. This is expected to change  little over time
# because the modules in the user's plant should be relatively stable.
PLANT_TOPOLOGY_UPDATE_INTERVAL = 3600  # 60 minutes

# Seconds between API checks for module status updates. This can change frequently so we check often
MODULE_STATUS_UPDATE_INTERVAL = 300  # 5 minutes


class HomePlusControlAsyncApi(HomePlusOAuth2Async):
    """Legrand Home+ Control object that interacts with the OAuth2-based API of the provider.

    This API is bound the HomeAssistant Config Entry that corresponds to this component.

    Attributes:.
        hass (HomeAssistant): HomeAssistant core object.
        config_entry (ConfigEntry): ConfigEntry object that configures this API.
        implementation (AbstractOAuth2Implementation): OAuth2 implementation that handles AA and token refresh.
        logger (Logger): Logger of the object.
        switches (dict): Dictionary of HomePlusControl switches indexed by their unique ID.
        switches_to_remove (dict): Dictionaty of the HomePlusControl switches that are to be removed from HomeAssistant, indexed by their unique ID.
    """

    def __init__(
        self,
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
    ):
        """Initialize the HomePlusControlAsyncApi object.

        Initialize the authenticated API for the Legrand Home+ Control component.

        Args:.
            hass (HomeAssistant): HomeAssistant core object.
            config_entry (ConfigEntry): ConfigEntry object that configures this API.
            implementation (AbstractOAuth2Implementation): OAuth2 implementation that handles AA and token refresh.
        """
        self.hass = hass
        self.config_entry = config_entry
        self.implementation = implementation
        self._domain = DOMAIN
        self._plants = {}
        self.switches = {}
        self.switches_to_remove = {}

        self._last_check = {"PLANT": time.monotonic(), "TOPOLOGY": -1, "STATUS": -1}

        # Create the API authenticated client - external library
        super().__init__(
            client_id=self.config_entry.data[CONF_CLIENT_ID],
            client_secret=self.config_entry.data[CONF_CLIENT_SECRET],
            subscription_key=self.config_entry.data[CONF_SUBSCRIPTION_KEY],
            redirect_uri=self.config_entry.data[CONF_REDIRECT_URI],
            token=self.config_entry.data["token"],
            oauth_client=aiohttp_client.async_get_clientsession(self.hass),
        )

    @property
    def logger(self) -> logging.Logger:
        """Logger of authentication API."""
        return logging.getLogger(__name__)

    @property
    def switches(self):
        """Return dictionary of switch entities of this platform."""
        return self._switches

    @switches.setter
    def switches(self, switches):
        """Set the internal switch attribute."""
        self._switches = switches

    @property
    def switches_to_remove(self):
        """Return dictionary of switch entities of this platform that should be removed from HA."""
        return self._switches_to_remove

    @switches_to_remove.setter
    def switches_to_remove(self, switches):
        """Set the internal switches_to_remove attribute."""
        self._switches_to_remove = switches

    async def async_ensure_token_valid(self) -> None:
        """Ensure that the current token is valid.

        Overrides the method of the external library to ensure that we update the
        config entry whenever the token is refreshed.
        """
        if self.valid_token:
            self.logger.debug("Legrand Home+ Control oauth token is still valid.")
            return

        self.logger.debug(
            "Legrand Home+ Control oauth token is no longer valid so refreshing."
        )
        new_token = await self.implementation.async_refresh_token(self.token)
        self.token = new_token

        self.hass.config_entries.async_update_entry(
            self.config_entry, data={**self.config_entry.data, "token": new_token}
        )

    async def fetch_data(self):
        """Get the latest data from the API.

        Returns:
            dict: Dictionary of switch entities in their updated state.
        """
        await self.async_handle_plant_data()
        return await self.async_handle_module_status()

    async def close_connection(self):
        """Clean up the connection."""
        await self.oauth_client.close()

    async def async_handle_plant_data(self):
        """Recover the plant data for this particular user.

        This will populate the "private" array of plants of this object and will return it.
        It is expected that in most cases, there will only be one plant.

        Returns:
            dict: Dictionary of plants for this user - Keyed by the plant ID. Can be empty if no plants are retrieved.
        """
        # Attempt to recover the plant information from the Hass data object.
        # If it is not there, then we request it from the API and add it.
        # We also refresh from the API if the time has expired.
        plant_info = self.hass.data[self._domain].get("plant_info")
        if plant_info is None or self._should_check("PLANT", PLANT_UPDATE_INTERVAL):
            result = await self.get_request(PLANT_URL)  # Call the API
            plant_info = await result.json()

            # If all goes well, we update the last check time
            self._last_check["PLANT"] = time.monotonic()

            self.hass.data[self._domain]["plant_info"] = plant_info
            self.logger.debug("Obtained plant information from API: %s", plant_info)
        else:
            self.logger.debug(
                "Obtained plant information from Hass object: %s", plant_info
            )

        # Populate the dictionary of plants
        current_plant_ids = []
        for p in plant_info["plants"]:
            current_plant_ids.append(p["id"])
            if p["id"] in self._plants:
                self.logger.debug(
                    "Plant with id %s is already cached. Only updating the existing data.",
                    p["id"],
                )
                cur_plant = self._plants.get(p["id"])
                # We will update the plant info just in case and ensure it has an Api object
                cur_plant.name = p["name"]
                cur_plant.country = p["country"]
                if cur_plant.oauth_client is None:
                    cur_plant.oauth_client = self
            else:
                self.logger.debug("New plant with id %s detected.", p["id"])
                self._plants[p["id"]] = HomePlusPlant(
                    p["id"], p["name"], p["country"], self
                )

        # Discard plants that may have disappeared
        # TODO: Remove associated entities to the plant
        plants_to_pop = []
        for existing_id in self._plants:
            if existing_id in current_plant_ids:
                continue
            self.logger.debug(
                "Plant with id %s is no longer present, so remove from cache.",
                existing_id,
            )
            plants_to_pop.append(existing_id)

        for p in plants_to_pop:
            self._plants.pop(p, None)

        return self._plants

    async def async_handle_module_status(self):
        """Recover the topology information for the plants defined in this object.

        By requesting the topology of the plant, the system learns about the modules that exist.
        The topology indicates identifiers, type and other device information, but it contains no information
        about the state of the module.

        This method returns the list of switch entities that will be registered in HomeAssistant. At this time
        the switches that are discovered through this API call are flattened into a single data structure.

        Returns:
            dict: Dictionary of switch entities across all of the plants.
        """
        for plant in self._plants.values():

            if self._should_check("TOPOLOGY", PLANT_TOPOLOGY_UPDATE_INTERVAL):
                self.logger.debug(
                    "API update of plant topology for plant %s.", plant.id
                )
                await plant.update_topology()  # Call the API
                # If all goes well, we update the last check time
                self._last_check["TOPOLOGY"] = time.monotonic()

            if self._should_check("STATUS", MODULE_STATUS_UPDATE_INTERVAL):
                self.logger.debug("API update of module status for plant %s.", plant.id)
                try:
                    await plant.update_module_status()  # Call the API
                except Exception as err:
                    self.logger.error(
                        "Error encountered when updating plant module status for plant %s: %s [%s]",
                        plant.id,
                        err,
                        type(err),
                    )
                else:
                    # If all goes well, we update the last check time
                    self._last_check["STATUS"] = time.monotonic()

        return self._update_entities()

    def _should_check(self, check_type, period):
        """Return True if the current monotonic time is greater than the last check time plus a fixed period.

        Args:
            check_type (str): Type that identifies the timer that has to be used
            period (float): Number of fractional seconds to add to the last check time
        """
        current_time = time.monotonic()
        if current_time > self._last_check[check_type] + period:
            self.logger.debug(
                "Last check time (%.2f) has been exceeded by more than %.2f seconds [current monotonic time is %.2f]",
                self._last_check[check_type],
                period,
                current_time,
            )
            return True
        return False

    def _update_entities(self):
        """Update the switch entities based on the collected information in the plant object.

        Returns:
            dict: Dictionary of switch entities across all of the plants.
        """
        for plant in self._plants.values():
            # Loop through the modules in the plant and we only keep the ones that are "interactive"
            # and can be represented by a switch, i.e. power outlets, micromodules and light switches.
            # All other modules are discarded/ignored.
            current_module_ids = []
            for module in list(plant.modules.values()):
                if isinstance(module, HomePlusInteractiveModule):
                    current_module_ids.append(module.id)
                    if module.id not in self.switches.keys():
                        self.logger.debug(
                            "Registering Home+ Control module in internal map: %s.",
                            str(module),
                        )
                        self.switches[module.id] = module

            # Discard modules that may have disappeared from the topology
            switches_to_pop = []
            for existing_id in self.switches:
                if existing_id in current_module_ids:
                    continue
                self.logger.debug(
                    "Module with id %s is no longer present, so remove from the internal map.",
                    existing_id,
                )
                switches_to_pop.append(existing_id)

            for s in switches_to_pop:
                self.switches_to_remove[s] = self.switches.pop(s, None)

        return self.switches
