"""Support for withings sensors."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from homeassistant.util import slugify
from . import const, WITHINGS_ATTRIBUTES, _LOGGER, \
    WithingsDataManager, WithingsHealthSensor


async def async_setup_entry(
        hass: HomeAssistantType,
        entry: ConfigEntry,
        async_add_entities
):
    """Set up the sensor config entry."""
    import nokia

    profile = entry.data[const.PROFILE]
    profile_slug = slugify(profile)
    credentials = entry.data[const.CREDENTIALS]

    def credentials_saver(credentials_param):
        _LOGGER.debug('Saving updated credentials.')
        entry.data[const.CREDENTIALS] = credentials_param
        hass.config_entries.async_update_entry(entry, data={**entry.data})

    _LOGGER.debug(
        'Creating nokia api instance with credentials %s.',
        credentials
    )
    api = nokia.NokiaApi(
        credentials,
        refresh_cb=(lambda token: credentials_saver(
            api.credentials
        ))
    )

    _LOGGER.debug(
        'Creating withings data manager for slug: %s',
        profile_slug
    )
    data_manager = WithingsDataManager(
        profile_slug,
        api
    )

    _LOGGER.debug('Attempting to refresh token.')
    await data_manager.async_refresh_token()

    try:
        _LOGGER.debug('Confirming we\'re authenticated.')
        api.get_user()
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.debug('Not authenticated %s.', ex)
        return False

    _LOGGER.debug('Creating entities.')
    entities = []

    for attribute in WITHINGS_ATTRIBUTES:
        _LOGGER.debug('Creating entity for %s', attribute.friendly_name)

        entity = WithingsHealthSensor(data_manager, attribute)

        entities.append(entity)

    _LOGGER.debug('Adding entities.')
    async_add_entities(entities, True)

    return True
