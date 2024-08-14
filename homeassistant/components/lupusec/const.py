"""Constants for the Lupusec component."""

from lupupy.constants import (
    TYPE_CONTACT_XT,
    TYPE_DOOR,
    TYPE_INDOOR_SIREN_XT,
    TYPE_KEYPAD_V2,
    TYPE_OUTDOOR_SIREN_XT,
    TYPE_POWER_SWITCH,
    TYPE_POWER_SWITCH_1_XT,
    TYPE_POWER_SWITCH_2_XT,
    TYPE_SMOKE,
    TYPE_SMOKE_XT,
    TYPE_WATER,
    TYPE_WATER_XT,
    TYPE_WINDOW,
)

DOMAIN = "lupusec"

TYPE_TRANSLATION = {
    TYPE_WINDOW: "Fensterkontakt",
    TYPE_DOOR: "Türkontakt",
    TYPE_SMOKE: "Rauchmelder",
    TYPE_WATER: "Wassermelder",
    TYPE_POWER_SWITCH: "Steckdose",
    TYPE_CONTACT_XT: "Fenster- / Türkontakt V2",
    TYPE_WATER_XT: "Wassermelder V2",
    TYPE_SMOKE_XT: "Rauchmelder V2",
    TYPE_POWER_SWITCH_1_XT: "Funksteckdose",
    TYPE_POWER_SWITCH_2_XT: "Funksteckdose V2",
    TYPE_KEYPAD_V2: "Keypad V2",
    TYPE_INDOOR_SIREN_XT: "Innensirene",
    TYPE_OUTDOOR_SIREN_XT: "Außensirene V2",
}
