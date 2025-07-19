"""The quantum_gateway component."""

from requests import RequestException
import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.const import CONF_HOST, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DATA_COODINATOR, DOMAIN, LOGGER, PLATFORM_SCHEMA
from .coordinator import QuantumGatewayCoordinator

CONFIG_SCHEMA = vol.Schema(
    {DEVICE_TRACKER_DOMAIN: [PLATFORM_SCHEMA]},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Quantum Gateway component."""

    options = next(
        (
            conf
            for conf in config.get(DEVICE_TRACKER_DOMAIN, [])
            if conf.get(CONF_PLATFORM) == DOMAIN
        ),
        None,
    )
    if not options:
        return True

    hass.data.setdefault(DOMAIN, {})
    if options[CONF_HOST] not in hass.data[DOMAIN]:
        hass.data[DOMAIN][options[CONF_HOST]] = {}

    coordinator = QuantumGatewayCoordinator(hass, options)

    try:
        await coordinator._async_setup()  # noqa: SLF001
        success_init = (
            coordinator.scanner.success_init if coordinator.scanner else False
        )
    except RequestException:
        success_init = False
        LOGGER.error("Unable to connect to gateway. Check host")

    if not success_init:
        LOGGER.error("Unable to login to gateway. Check password and host")

    hass.data[DOMAIN][options[CONF_HOST]][DATA_COODINATOR] = (
        coordinator if success_init else None
    )

    return success_init
