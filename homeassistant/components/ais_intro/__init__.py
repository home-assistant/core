"""
Component that will help guide the user taking its first steps.

"""
import asyncio
import logging

DOMAIN = "ais_intro"


@asyncio.coroutine
def async_setup(hass, config=None):
    """Set up the introduction component."""
    log = logging.getLogger(__name__)
    log.info(
        """

    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        Cześć, witamy w systemie Asystent domowy!

        Mamy nadzieję, że spełnimy wszystkie twoje marzenia.

        Oto kilka informacji, od których możesz zacząć:

         - Dokumentacja :
           https://sviete.github.io/AIS-docs

         - Źródła programu:
           https://github.com/sviete

         - Strona projektu:
           https://www.ai-speaker.com


    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """
    )

    hass.components.persistent_notification.async_create(
        """

Mamy nadzieję, że spełnimy wszystkie twoje marzenia.

Oto kilka informacji, od których możesz zacząć:

 - [Dokumentacja](https://sviete.github.io/AIS-docs)
 - [Źródła systemu](https://github.com/sviete)
 - [Strona projektu](https://www.ai-speaker.com)

""",
        "Cześć, witamy w systemie Asystent domowy!",
    )  # noqa

    return True
