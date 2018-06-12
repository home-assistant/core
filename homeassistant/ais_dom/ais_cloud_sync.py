"""
AIS dom Cloud conection
"""
import asyncio
import logging
import homeassistant.core as ha
from homeassistant.components import ais_cloud
from homeassistant.helpers.discovery import async_load_platform
aisCloud = ais_cloud.AisCloudWS()
DOMAIN = 'ais_cloud_sync'
_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the demo environment."""
    configurator = hass.components.configurator
    config.setdefault(ha.DOMAIN, {})
    config.setdefault(DOMAIN, {})
    configurator_ids = []

    def ais_configuration_callback(data):
        """callback, mark config as done."""
        import re
        _LOGGER.info("Create token")
        if ("login" not in data):
            _LOGGER.error("No login")
            configurator.notify_errors(
                configurator_ids[0],
                "Podaj adres email.")
            return
        login = data.get('login')
        match_patern = "^[_a-z0-9-]+(\.[_a-z0-9-]+)"
        match_patern += "*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$"
        if (len(login) < 7 or re.match(match_patern, login) is None):
            configurator.notify_errors(
                configurator_ids[0],
                "Podaj poprawny adres email.")
            return
        if ("password" not in data):
            _LOGGER.error("No password")
            configurator.notify_errors(
                configurator_ids[0],
                "Podaj hasło.")
            return
        password = data.get('password')
        if (len(password) == 0):
            _LOGGER.error("No password")
            configurator.notify_errors(
                configurator_ids[0],
                "Podaj hasło.")
            return
        token = aisCloud.getCloudToken(login, password)
        _LOGGER.error('token: ' + str(token))
        if (token is not None):
            hass.states.async_set(
                'weblink.cloud', ais_cloud.CLOUD_APP_URL + token, {
                    'icon': 'mdi:open-in-new',
                    'friendly_name': 'Przejdz do konfiguracji usług online'
                })
            hass.services.call(
                'group', 'set_visibility', {
                    'entity_id': 'group.dom_cloud',
                    'visible': True
                })
            # dynamically add the cloud services
            # here we should take the info about users services to anable them
            try:
                hass.async_run_job(
                    async_load_platform(hass, 'ais_gm_service', {}, {}))
            except Exception as e:
                _LOGGER.error('async_load_platform ais_gm_service ' + str(e))
            # hass.block_till_done()
            configurator.request_done(configurator_ids[0])
        else:
            configurator.notify_errors(
                configurator_ids[0],
                "Brak dostępu, spróbuj ponownie.")

    def setup_configurator():
        """Set up a configurator."""
        request_id = configurator.request_config(
            "AIS dom, Twoje usługi", ais_configuration_callback,
            description=("Dostęp do usług online umożliwia łatwą "
                         "aktualizację, konfigurację i personalizację "
                         " Twojego systemu AIS dom.\n"
                         "Aby dołączyć podaj hasło oraz adres email"
                         " na który otrzymałeś dane o dostępie."),
            fields=[{'id': 'login', 'name': 'Adres email'},
                    {'id': 'password', 'name': 'Hasło', 'type': 'password'}],
            submit_caption="OK, połącz konto online!"
        )
        configurator_ids.append(request_id)
    token = aisCloud.getCurrentToken()
    if (token is None):
        hass.async_add_job(setup_configurator)
    else:
        # the token is valid (no need to configure access)
        try:
            hass.async_run_job(
                async_load_platform(hass, 'ais_gm_service', {}, {}))
        except Exception as e:
            _LOGGER.error('async_load_platform ais_gm_service ' + str(e))
        _LOGGER.debug("the token is valid (no need to configure access)")
        return True

    return True
