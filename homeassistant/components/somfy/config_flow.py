"""Config flow for Somfy."""
from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Optional, Any

from pymfy.api.somfy_api import AbstractSomfyApi
import async_timeout

from homeassistant import config_entries
from homeassistant.core import callback, HomeAssistant
from .const import DOMAIN, DATA_IMPLEMENTATION

_LOGGER = logging.getLogger(__name__)


class AbstractSomfyImplementation(ABC):
    """Base class to abstract authentication for Somfy."""

    @property
    def name(self) -> str:
        """Name of the implementation."""
        raise NotImplementedError

    @property
    def domain(self) -> str:
        """Domain that is providing the implementation."""
        raise NotImplementedError

    @abstractmethod
    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate a url for the user to authorize.

        This step is called when a config flow is initialized. It should redirect the
        user to the Somfy website where they can authorize Home Assistant to be used
        with Somfy.

        The implementation is responsible to get notified when the user is authorized
        and progress the specified config flow. Do as little work as possible once
        notified. You can do the work inside async_resolve_external_data. This will
        give the best UX.

        Pass external data in with:

        ```python
        await hass.config_entries.flow.async_configure(
            flow_id=flow_id, user_input=external_data
        )
        ```
        """

    @abstractmethod
    async def async_resolve_external_data(self, data: Any) -> dict:
        """Resolve external data to tokens.

        Turn the data that the implementation passed to the config flow as external
        step data into Somfy tokens. These tokens will be stored as 'token' in the
        config entry data.
        """

    @abstractmethod
    def async_create_api_auth(
        self, hass: HomeAssistant, config_entry: config_entries.ConfigEntry
    ) -> AbstractSomfyApi:
        """Create a Somfy API Auth object.

        The tokens returned from `async_resolve_external_data` can be found in 'token' key
        in the config entry data.

        It is the responsibility of the implementation to update the config entry when
        a new access token is fetched.

        ```python
        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, "token": new_tokens}
        )
        ```
        """


@callback
def register_flow_implementation(
    hass: HomeAssistant, implementation: AbstractSomfyImplementation
):
    """Register a flow implementation."""
    implementations = hass.data.setdefault(DOMAIN, {}).setdefault(
        DATA_IMPLEMENTATION, {}
    )
    implementations[implementation.domain] = implementation


@config_entries.HANDLERS.register("somfy")
class SomfyFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Instantiate config flow."""
        self.flow_impl: Optional[AbstractSomfyImplementation] = None
        self.external_data = None

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        implementations = self.hass.data.get(DOMAIN, {}).get(DATA_IMPLEMENTATION)

        if not implementations:
            return self.async_abort(reason="missing_configuration")

        # Pick first implementation as we have only one.
        self.flow_impl = list(implementations.values())[0]
        return await self.async_step_auth()

    async def async_step_auth(self, user_input=None):
        """Create an entry for auth."""
        # Flow has been triggered from Somfy website
        if user_input:
            self.external_data = user_input
            return self.async_external_step_done(next_step_id="creation")

        try:
            with async_timeout.timeout(10):
                url = await self.flow_impl.async_generate_authorize_url(self.flow_id)
        except asyncio.TimeoutError:
            return self.async_abort(reason="authorize_url_timeout")

        return self.async_external_step(step_id="auth", url=url)

    async def async_step_creation(self, user_input=None):
        """Create Somfy api and entries."""
        tokens = await self.flow_impl.async_resolve_external_data(self.external_data)

        _LOGGER.info("Successfully authenticated Somfy")

        return self.async_create_entry(
            title="Somfy",
            data={"implementation": self.flow_impl.domain, "token": tokens},
        )

    async_step_import = async_step_user
