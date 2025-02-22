"""Support to interact with Remember The Milk."""

from rtmapi import Rtm
import voluptuous as vol

from homeassistant.components import configurator
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER
from .entity import RememberTheMilkEntity
from .storage import RememberTheMilkConfiguration

# httplib2 is a transitive dependency from RtmAPI. If this dependency is not
# set explicitly, the library does not work.

CONF_SHARED_SECRET = "shared_secret"

RTM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_SHARED_SECRET): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [RTM_SCHEMA])}, extra=vol.ALLOW_EXTRA
)

SERVICE_CREATE_TASK = "create_task"
SERVICE_COMPLETE_TASK = "complete_task"

SERVICE_SCHEMA_CREATE_TASK = vol.Schema(
    {vol.Required(CONF_NAME): cv.string, vol.Optional(CONF_ID): cv.string}
)

SERVICE_SCHEMA_COMPLETE_TASK = vol.Schema({vol.Required(CONF_ID): cv.string})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Remember the milk component."""
    component = EntityComponent[RememberTheMilkEntity](LOGGER, DOMAIN, hass)

    stored_rtm_config = RememberTheMilkConfiguration(hass)
    await stored_rtm_config.setup()
    for rtm_config in config[DOMAIN]:
        account_name = rtm_config[CONF_NAME]
        LOGGER.debug("Adding Remember the milk account %s", account_name)
        api_key = rtm_config[CONF_API_KEY]
        shared_secret = rtm_config[CONF_SHARED_SECRET]
        token = stored_rtm_config.get_token(account_name)
        if token:
            LOGGER.debug("found token for account %s", account_name)
            await _create_instance(
                hass,
                account_name,
                api_key,
                shared_secret,
                token,
                stored_rtm_config,
                component,
            )
        else:
            await _register_new_account(
                hass, account_name, api_key, shared_secret, stored_rtm_config, component
            )

    LOGGER.debug("Finished adding all Remember the milk accounts")
    return True


async def _create_instance(
    hass: HomeAssistant,
    account_name: str,
    api_key: str,
    shared_secret: str,
    token: str,
    stored_rtm_config: RememberTheMilkConfiguration,
    component: EntityComponent[RememberTheMilkEntity],
) -> None:
    entity = RememberTheMilkEntity(
        account_name, api_key, shared_secret, token, stored_rtm_config
    )
    LOGGER.debug("Instance created for account %s", entity.name)
    await entity.check_token(hass)
    await component.async_add_entities([entity])
    hass.services.async_register(
        DOMAIN,
        f"{account_name}_create_task",
        entity.create_task,
        schema=SERVICE_SCHEMA_CREATE_TASK,
    )
    hass.services.async_register(
        DOMAIN,
        f"{account_name}_complete_task",
        entity.complete_task,
        schema=SERVICE_SCHEMA_COMPLETE_TASK,
    )


async def _register_new_account(
    hass: HomeAssistant,
    account_name: str,
    api_key: str,
    shared_secret: str,
    stored_rtm_config: RememberTheMilkConfiguration,
    component: EntityComponent[RememberTheMilkEntity],
) -> None:
    """Register a new account."""
    api = Rtm(api_key, shared_secret, "write", None)
    url, frob = await hass.async_add_executor_job(api.authenticate_desktop)
    LOGGER.debug("Sent authentication request to server")

    @callback
    def register_account_callback(fields: list[dict[str, str]]) -> None:
        """Call for register the configurator."""
        hass.async_create_task(handle_token(api, frob))

    async def handle_token(api: Rtm, frob: str) -> None:
        """Handle token."""
        await hass.async_add_executor_job(api.retrieve_token, frob)

        token: str | None = api.token
        if token is None:
            LOGGER.error("Failed to register, please try again")
            configurator.async_notify_errors(
                hass, request_id, "Failed to register, please try again."
            )
            return

        stored_rtm_config.set_token(account_name, token)
        LOGGER.debug("Retrieved new token from server")

        await _create_instance(
            hass,
            account_name,
            api_key,
            shared_secret,
            token,
            stored_rtm_config,
            component,
        )

        configurator.async_request_done(hass, request_id)

    request_id = configurator.async_request_config(
        hass,
        f"{DOMAIN} - {account_name}",
        callback=register_account_callback,
        description=(
            "You need to log in to Remember The Milk to"
            "connect your account. \n\n"
            "Step 1: Click on the link 'Remember The Milk login'\n\n"
            "Step 2: Click on 'login completed'"
        ),
        link_name="Remember The Milk login",
        link_url=url,
        submit_caption="login completed",
    )
