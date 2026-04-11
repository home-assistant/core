"""Alexa Devices constants."""

import logging

_LOGGER = logging.getLogger(__package__)

DOMAIN = "alexa_devices"
CONF_LOGIN_DATA = "login_data"
CONF_SITE = "site"

DEFAULT_DOMAIN = "com"
COUNTRY_DOMAINS = {
    "ar": DEFAULT_DOMAIN,
    "at": DEFAULT_DOMAIN,
    "au": "com.au",
    "be": "com.be",
    "br": DEFAULT_DOMAIN,
    "gb": "co.uk",
    "il": DEFAULT_DOMAIN,
    "jp": "co.jp",
    "mx": "com.mx",
    "no": DEFAULT_DOMAIN,
    "nz": "com.au",
    "pl": DEFAULT_DOMAIN,
    "tr": "com.tr",
    "us": DEFAULT_DOMAIN,
    "za": "co.za",
}

CATEGORY_SENSORS = "sensors"
CATEGORY_NOTIFICATIONS = "notifications"

# Map service translation keys to Alexa API
INFO_SKILLS_MAPPING = {
    "calendar_today": "Alexa.Calendar.PlayToday",
    "calendar_tomorrow": "Alexa.Calendar.PlayTomorrow",
    "calendar_next": "Alexa.Calendar.PlayNext",
    "date": "Alexa.Date.Play",
    "time": "Alexa.Time.Play",
    "national_news": "Alexa.News.NationalNews",
    "flash_briefing": "Alexa.FlashBriefing.Play",
    "traffic": "Alexa.Traffic.Play",
    "weather": "Alexa.Weather.Play",
    "cleanup": "Alexa.CleanUp.Play",
    "good_morning": "Alexa.GoodMorning.Play",
    "sing_song": "Alexa.SingASong.Play",
    "fun_fact": "Alexa.FunFact.Play",
    "tell_joke": "Alexa.Joke.Play",
    "tell_story": "Alexa.TellStory.Play",
    "im_home": "Alexa.ImHome.Play",
    "goodnight": "Alexa.GoodNight.Play",
}
