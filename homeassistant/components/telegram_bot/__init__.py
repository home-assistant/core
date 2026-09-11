"""Support to send and receive Telegram messages."""

import logging
from typing import Protocol, cast

import telegram
from telegram import Bot
from telegram.error import InvalidToken, TelegramError

from homeassistant.const import CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.typing import ConfigType

from . import broadcast, polling, webhooks
from .bot import (
    BaseTelegramBot,
    TelegramBotConfigEntry,
    TelegramNotificationService,
    initialize_bot,
)

# The ATTR_* below are unused here, but re-exported for the telegram integration.
from .const import (
    ATTR_CHAT_ID,  # noqa: F401
    ATTR_DISABLE_NOTIF,  # noqa: F401
    ATTR_DISABLE_WEB_PREV,  # noqa: F401
    ATTR_MESSAGE_TAG,  # noqa: F401
    ATTR_MESSAGE_THREAD_ID,  # noqa: F401
    ATTR_PARSER,
    CONF_API_ENDPOINT,
    CONF_CHAT_ID,
    DEFAULT_API_ENDPOINT,
    DOMAIN,
    PLATFORM_BROADCAST,
    PLATFORM_POLLING,
    PLATFORM_WEBHOOKS,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class BotPlatformModule(Protocol):
    """Define the module protocol for telegram bot modules."""

    async def async_setup_bot_platform(
        self, hass: HomeAssistant, bot: Bot, config: TelegramBotConfigEntry
    ) -> BaseTelegramBot | None:
        """Set up the Telegram bot platform."""


MODULES = {
    PLATFORM_BROADCAST: broadcast,
    PLATFORM_POLLING: polling,
    PLATFORM_WEBHOOKS: webhooks,
}

PLATFORMS: list[Platform] = [Platform.EVENT, Platform.NOTIFY]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Telegram bot component."""
    async_setup_services(hass)

    return True


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: TelegramBotConfigEntry
) -> bool:
    """Migrate Telegram Bot config entry."""

    version = config_entry.version
    minor_version = config_entry.minor_version
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        version,
        minor_version,
    )

    # version 1.1: to add default API endpoint
    if version == 1 and minor_version == 1:
        new_data = {**config_entry.data}
        new_data[CONF_API_ENDPOINT] = DEFAULT_API_ENDPOINT
        updated = hass.config_entries.async_update_entry(
            config_entry, data=new_data, minor_version=2
        )
        _LOGGER.debug(
            "Migrated Telegram Bot config entry to %s.%s, entry updated: %s",
            config_entry.version,
            config_entry.minor_version,
            updated,
        )

    # version 1.2 -> 1.3: give each chat its own device, linked to the shared bot device,
    # and make sure the bot device is tied to (entry, None).
    if version == 1 and config_entry.minor_version < 3:
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        devices = dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        )
        if devices:
            bot_device = devices[0]
            bot_id = next(
                identifier
                for domain, identifier in bot_device.identifiers
                if domain == DOMAIN
            )
            notify_entities = {
                entity.config_subentry_id: entity
                for entity in er.async_entries_for_config_entry(
                    entity_registry, config_entry.entry_id
                )
                # The event entity (no subentry) stays on the shared bot device
                if entity.config_subentry_id is not None
            }
            for subentry_id, subentry in config_entry.subentries.items():
                per_chat_device = device_registry.async_get_or_create(
                    config_entry_id=config_entry.entry_id,
                    config_subentry_id=subentry_id,
                    identifiers={(DOMAIN, f"{bot_id}_{subentry.data[CONF_CHAT_ID]}")},
                    via_device_id=bot_device.id,
                )
                if entity := notify_entities.get(subentry_id):
                    entity_registry.async_update_entity(
                        entity.entity_id, device_id=per_chat_device.id
                    )
            # Hand the bot device back to (entry, None), keeping the event entity
            device_registry.async_update_device(
                bot_device.id, new_config_subentry_id=None
            )
        hass.config_entries.async_update_entry(config_entry, minor_version=3)

    return True


def bot_device_info(config_entry: TelegramBotConfigEntry, bot_id: int) -> dr.DeviceInfo:
    """Return device info for the shared bot device."""
    return dr.DeviceInfo(
        name=config_entry.title,
        entry_type=dr.DeviceEntryType.SERVICE,
        manufacturer="Telegram",
        model=config_entry.data[CONF_PLATFORM].capitalize(),
        sw_version=telegram.__version__,
        identifiers={(DOMAIN, f"{bot_id}")},
    )


async def async_setup_entry(hass: HomeAssistant, entry: TelegramBotConfigEntry) -> bool:
    """Create the Telegram bot from config entry."""
    bot: Bot = await hass.async_add_executor_job(initialize_bot, hass, entry.data)
    try:
        await bot.get_me()
    except InvalidToken as err:
        # pylint: disable-next=home-assistant-exception-not-translated
        raise ConfigEntryAuthFailed("Invalid API token for Telegram Bot.") from err
    except TelegramError as err:
        raise ConfigEntryNotReady from err

    p_type: str = entry.data[CONF_PLATFORM]

    _LOGGER.debug("Setting up %s.%s", DOMAIN, p_type)
    module = cast(BotPlatformModule, MODULES[p_type])
    try:
        receiver_service = await module.async_setup_bot_platform(hass, bot, entry)
    except Exception:
        _LOGGER.exception("Error setting up Telegram bot %s", p_type)
        await bot.shutdown()
        return False

    notify_service = TelegramNotificationService(
        hass, receiver_service, bot, entry, entry.options[ATTR_PARSER]
    )
    entry.runtime_data = notify_service

    # Create the bot device before the platforms are set up, so the per-chat devices can
    # resolve it as their via_device no matter which platform is set up first
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **bot_device_info(entry, bot.id)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: TelegramBotConfigEntry) -> None:
    """Handle config changes."""
    entry.runtime_data.parse_mode = entry.options[ATTR_PARSER]
    if entry.runtime_data.old_config_data != entry.data:
        # Reload if config data has changed
        hass.config_entries.async_schedule_reload(entry.entry_id)
        return

    # reload entities
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: TelegramBotConfigEntry
) -> bool:
    """Unload Telegram app."""
    # broadcast platform has no app
    if entry.runtime_data.app:
        await entry.runtime_data.app.shutdown()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
