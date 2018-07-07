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

        Cześć, witamy w systemie Asystent domowy!

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

 - [Pierwsze kroki](https://github.com/sviete/AIS-WWW/wiki/1.-Pierwsze-kroki)
 - [Komendy głosowe](https://github.com/sviete/AIS-WWW/wiki/3.-Komendy-g%C5%82osowe)
 - [Zdalny dostęp](https://github.com/sviete/AIS-WWW/wiki/7.-Zdalny-dost%C4%99p)
 - [Źródła systemu](https://github.com/sviete)
 - [Strona projektu](https://ai-speaker.com)

""", 'Cześć, witamy w systemie Asystent domowy!')  # noqa

    return True
