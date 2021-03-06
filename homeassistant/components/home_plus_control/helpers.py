"""Helper classes and functions for the Legrand Home+ Control integration."""
import logging

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import CONF_SUBSCRIPTION_KEY, DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from .switch import HomeControlSwitchEntity

_LOGGER = logging.getLogger(__name__)


async def async_add_entities(new_unique_ids, coordinator, add_entities):
    """Add the entities to the platform.

    Args:
        new_unique_ids (str[]): Unique identifiers of entities to be added to Home Assistant.
        coordinator (DataUpdateCoordinator): Data coordinator of this platform.
        add_entities (function): Method called to add entities to Home Assistant.
    """
    new_entities = []
    for uid in new_unique_ids:
        new_ent = HomeControlSwitchEntity(coordinator, uid)
        new_entities.append(new_ent)
    add_entities(new_entities)


async def async_remove_entities(remove_uids, entity_uid_map, device_reg):
    """Remove the entities from the platform.

    Args:
        remove_uids (str[]): Unique identifiers of entities to be removed to Home Assistant.
        entity_uid_map (dict): Lookup dictionary of unique_ids (key) and entity_ids (value).
        device_reg(DeviceRegistry): Home Assistant Device Registry.
    """
    for uid in remove_uids:
        entity_uid_map.pop(uid)
        device = device_reg.async_get_device({(DOMAIN, uid)})
        device_reg.async_remove_device(device.id)


class HomePlusControlOAuth2Implementation(
    config_entry_oauth2_flow.LocalOAuth2Implementation
):
    """OAuth2 implementation that extends the HomeAssistant local implementation.

    It provides the name of the integration and adds support for the subscription key.

    Attributes:
        hass (HomeAssistant): HomeAssistant core object.
        client_id (str): Client identifier assigned by the API provider when registering an app.
        client_secret (str): Client secret assigned by the API provider when registering an app.
        subscription_key (str): Subscription key obtained from the API provider.
        token (dict): oauth2 token used by this authentication implementation instance.
        name (str): Name of the implementation (appears in the HomeAssitant GUI).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_data: dict,
    ):
        """HomePlusControlOAuth2Implementation Constructor.

            Initialize the authentication implementation for the Legrand Home+ Control API.

        Args:
            hass (HomeAssistant): HomeAssistant core object.
            config_data (dict): Configuration data that complies with the config Schema
                                of this component.
        """
        self.hass = hass
        self._domain = DOMAIN
        self.client_id = config_data[CONF_CLIENT_ID]
        self.client_secret = config_data[CONF_CLIENT_SECRET]
        self.authorize_url = OAUTH2_AUTHORIZE
        self.token_url = OAUTH2_TOKEN
        self.subscription_key = config_data[CONF_SUBSCRIPTION_KEY]

        super().__init__(
            hass=self.hass,
            domain=self._domain,
            client_id=self.client_id,
            client_secret=self.client_secret,
            authorize_url=self.authorize_url,
            token_url=self.token_url,
        )

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Home+ Control"
