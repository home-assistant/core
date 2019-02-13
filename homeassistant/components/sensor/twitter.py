"""
Support for Twitter.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.twitter/
"""
from datetime import timedelta
import json
import logging
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_NAME, CONF_ACCESS_TOKEN, CONF_USERNAME, CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['TwitterAPI==2.5.9']

_LOGGER = logging.getLogger(__name__)

ATTR_USERNAME = 'username'
ATTR_LATEST_TWEET_DATE = 'latest_tweet_date'
ATTR_LATEST_TWEET_TEXT = 'latest_tweet_text'
ATTR_LATEST_TWEET_RETWEETS = 'latest_tweet_retweets'
ATTR_LATEST_TWEET_LIKES = 'latest_tweet_likes'
ATTR_LATEST_TWEET_HASHTAGS = 'latest_tweet_hashtags'
ATTR_LATEST_TWEET_MENTIONS = 'latest_tweet_mentions'

CONF_CONSUMER_KEY = 'consumer_key'
CONF_CONSUMER_SECRET = 'consumer_secret'
CONF_ACCESS_TOKEN_SECRET = 'access_token_secret'
CONF_USERS = 'users'

DEFAULT_NAME = 'Twitter'

SCAN_INTERVAL = timedelta(seconds=300)

USERS_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_NAME): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Required(CONF_ACCESS_TOKEN_SECRET): cv.string,
    vol.Required(CONF_CONSUMER_KEY): cv.string,
    vol.Required(CONF_CONSUMER_SECRET): cv.string,
    vol.Required(CONF_USERS):
        vol.All(cv.ensure_list, [USERS_SCHEMA])
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Twitter sensor platform."""
    sensors = []
    for user in config.get(USERS_SCHEMA):
        data = TwitterData(
            name=config.get(user, CONF_NAME),
            username=config.get(user, CONF_USERNAME),
            consumer_key=config.get(CONF_CONSUMER_KEY),
            consumer_secret=config.get(CONF_CONSUMER_SECRET),
            access_token_key=config.get(CONF_ACCESS_TOKEN),
            access_token_secret=config.get(CONF_ACCESS_TOKEN_SECRET)
        )
        sensors.append(TwitterSensor(data))
    add_entities(sensors, True)


class TwitterSensor(Entity):
    """Representation of a Twitter sensor."""

    def __init__(self, twitter_data):
        """Initialize the Twitter sensor."""
        self._unique_id = twitter_data.username
        self._name = None
        self._state = None
        self._available = False
        self._twitter_data = twitter_data
        self._latest_tweet_date = None
        self._latest_tweet_text = None
        self._latest_tweet_retweets = None
        self._latest_tweet_likes = None
        self._latest_tweet_hashtags = None
        self._latest_tweet_mentions = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID for the sensor."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_NAME: self._name,
            ATTR_USERNAME: self._username,
            ATTR_LATEST_TWEET_DATE: self._latest_tweet_date,
            ATTR_LATEST_TWEET_TEXT: self._latest_tweet_text,
            ATTR_LATEST_TWEET_RETWEETS: self._latest_tweet_retweets,
            ATTR_LATEST_TWEET_LIKES: self._latest_tweet_likes,
            ATTR_LATEST_TWEET_HASHTAGS: self._latest_tweet_hashtags,
            ATTR_LATEST_TWEET_MENTIONS: self._latest_tweet_mentions
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return 'mdi:twitter-circle'

    def update(self):
        """Collect updated data from Twitter API."""
        self._twitter_data.update()

        self._name = self._twitter_data.name
        self._username = self._twitter_data.username
        self._state = self._twitter_data.latest_tweet_date
        self._available = self._twitter_data.available
        self._latest_tweet_date = self._twitter_data.latest_tweet_date
        self._latest_tweet_text = self._twitter_data.latest_tweet_text
        self._latest_tweet_retweets = self._twitter_data.latest_tweet_retweets
        self._latest_tweet_likes = self._twitter_data.latest_tweet_likes
        self._latest_tweet_hashtags = self._twitter_data.latest_tweet_hashtags
        self._latest_tweet_mentions = self._twitter_data.latest_tweet_mentions


class TwitterData():
    """Twitter Data object."""

    def __init__(self, name, username, consumer_key, consumer_secret,
                 access_token_key, access_token_secret):
        """Set up Twitter."""
        from TwitterAPI import TwitterAPI

        self._api = TwitterAPI(consumer_key, consumer_secret,
                               access_token_key, access_token_secret)

        self.name = name
        self.username = username

        self.available = False
        self.latest_tweet_date = None
        self.latest_tweet_text = None
        self.latest_tweet_retweets = None
        self.latest_tweet_likes = None
        self.latest_tweet_hashtags = None
        self.latest_tweet_mentions = None

    def update(self):
        """Update Twitter Sensor."""
        from TwitterAPI import TwitterPager

        pager = TwitterPager(self._api,
                             'statuses/user_timeline',
                             {'screen_name': self.username, 'count': 1})

        tweet = pager.get_iterator(wait=3.5)[0]

        self.latest_tweet_date = tweet['created_at']
        self.latest_tweet_text = tweet['text']
        self.latest_tweet_retweets = tweet['retweet_count']
        self.latest_tweet_likes = tweet['favorite_count']
        self.latest_tweet_hashtags = json.dumps(tweet['entities']['hashtags'])
        mentions = []
        for user in tweet['entities']['user_mentions']:
            mentions.append(user['screen_name'])
        self.latest_tweet_mentions = json.dumps(mentions)

        self.available = True
