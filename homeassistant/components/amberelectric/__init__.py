from .const import DOMAIN


def setup(hass, config):
    hass.helpers.discovery.load_platform("sensor", DOMAIN, {}, config)
    return True


async def async_setup_entry(hass, entry):
    hass.data[DOMAIN] = {"entry": entry}
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True
