"""Device name translations for the OMIE - Spain and Portugal electricity prices integration."""

from typing import Generic, NamedTuple, TypeVar

T = TypeVar("T")


class Translated(Generic[T]):
    """TODO: remove me."""

    en: T
    es: T
    pt: T

    def __init__(self, en: T, es: T, pt: T) -> None:
        """TODO: remove me."""
        super().__init__()
        self.en = en
        self.es = es
        self.pt = pt

    @staticmethod
    def lang(locale: str) -> str:
        """Return the best language for the provided locale string (e.g. `en-GB`)."""
        lang = locale.split("-")[0]
        return lang if lang in ["en", "es", "pt"] else "en"

    def get_all(self, locale: str) -> T:
        """Return the translations for the given lang or the default language if lang is unknown."""
        return getattr(self, Translated.lang(locale))


class DeviceNames(NamedTuple):
    """Translations used by the Device."""

    device_manufacturer: str
    device_name: str
    device_model: str


DEVICE_NAMES: Translated[DeviceNames] = Translated(
    en=DeviceNames(
        device_manufacturer="OMI Group",
        device_name="OMIE",
        device_model="MIBEL market results",
    ),
    es=DeviceNames(
        device_manufacturer="Grupo OMI",
        device_name="OMIE",
        device_model="Resultados del MIBEL",
    ),
    pt=DeviceNames(
        device_manufacturer="Grupo OMI",
        device_name="OMIE",
        device_model="Resultados do MIBEL",
    ),
)
