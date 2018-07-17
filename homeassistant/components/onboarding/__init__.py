"""Component to help onboard new users."""
from homeassistant.core import callback
from homeassistant.loader import bind_hass

from .const import STEPS, STEP_USER, DOMAIN

DEPENDENCIES = ['http']
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1


@bind_hass
@callback
def async_is_onboarded(hass):
    """Return if Home Assistant has been onboarded."""
    # Temporarily: if auth not active, always set onboarded=True
    if not hass.auth.active:
        return True

    return hass.data.get(DOMAIN, True)


async def async_setup(hass, config):
    """Set up the onboard component."""
    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load()

    if data is None:
        data = {
            'done': []
        }

    if STEP_USER not in data['done']:
        # Users can already have created an owner account via the command line
        # If so, mark the user step as done.
        has_owner = False

        for user in await hass.auth.async_get_users():
            if user.is_owner:
                has_owner = True
                break

        if has_owner:
            data['done'].append(STEP_USER)
            await store.async_save(data)

    if set(data['done']) == set(STEPS):
        return True

    hass.data[DOMAIN] = False

    from . import views

    await views.async_setup(hass, data, store)

    return True
