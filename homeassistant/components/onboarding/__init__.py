"""Component to help onboard new users."""
from homeassistant.core import callback
from homeassistant.loader import bind_hass

from .const import STEPS, DOMAIN

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

    if data and set(data['done']) == set(STEPS):
        return True

    if data is None:
        data = {
            'done': []
        }

    hass.data[DOMAIN] = False

    from . import views

    await views.async_setup(hass, data, store)

    return True
