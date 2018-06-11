"""
Component that will help guide the user taking its first steps.

"""
import asyncio
import logging

import voluptuous as vol

DOMAIN = 'introduction'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({}),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config=None):
    """Set up the introduction component."""
    log = logging.getLogger(__name__)
    log.info("""

    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        Cześć, witamy w AIS dom!

        Mamy nadzieję, że spełnimy wszystkie twoje marzenia.

        Oto kilka informacji, od których możesz zacząć:

         - Konfiguracja urządzeń :
           http://ai-speaker.com

         - Ustawiania audio :
           http://ai-speaker.com

         - Źródła programu:
           https://github.com/sviete

         - Odpowiedzi na najczęściej zadawane pytania:
           https://github.com/sviete


    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """)

    hass.components.persistent_notification.async_create("""

Mamy nadzieję, że spełnimy wszystkie twoje marzenia.

Oto kilka informacji, od których możesz zacząć:

 - [Konfiguracja urządzeń](http://ai-speaker.com)
 - [Ustawiania audio](http://ai-speaker.com)
 - [Źródła programu](https://github.com/sviete)
 - [Odpowiedzi na najczęściej zadawane pytania](https://github.com/sviete)

""", 'AIS dom, Witamy!')  # noqa

    return True
