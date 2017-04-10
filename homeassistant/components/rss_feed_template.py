"""
Exports sensor values via RSS feed.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/rss_feed_template/
"""

import asyncio
from aiohttp import web
from cgi import escape

import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
import homeassistant.helpers.config_validation as cv

DOMAIN="rss_feed_template"
DEPENDENCIES = ['http']

CONTENT_TYPE_XML = "text/xml"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: cv.ordered_dict(
        vol.Schema({
                vol.Optional('title'): cv.template,
                vol.Required('items'): vol.All(
                    cv.ensure_list,
                    [{
                        vol.Optional('title'): cv.template,
                        vol.Optional('description'): cv.template,
                    }]
                )
            })
        )
    }, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the RSS feeds."""
    
    for (feeduri,feedconfig) in config[DOMAIN].items():
        rss_view = RssView(hass, feedconfig)
        hass.http.app.router.add_route('get', '/api/rss/%s' % feeduri, rss_view.get)

    return True

class RssView(HomeAssistantView):
    
    _title = None
    _items = None
    
    def __init__(self, hass, feedconfig):
        """Initialize the rss view."""
        self._title = feedconfig.get('title')
        if self._title is not None:
            self._title.hass = hass
        
        self._items = feedconfig.get('items')
        for item in self._items:
            if 'title' in item:
                item['title'].hass=hass
            if 'description' in item:
                item['description'].hass=hass
            
    
    @asyncio.coroutine
    def get(self, request, entity_id=None):
        response='<?xml version="1.0" encoding="utf-8"?>\n\n'
        
        response+='<rss>\n'
        if self._title is not None:
            response+='  <title>%s</title>\n' % escape(self._title.async_render())
        
        for item in self._items:
            response+='  <item>\n'
            if 'title' in item:
                response+='    <title>'
                response+=escape(item['title'].async_render())
                response+='</title>\n'
            if 'description' in item:
                response+='    <description>'
                response+=escape(item['description'].async_render())
                response+='</description>\n'
            response+='  </item>\n'

        response+='</rss>\n'

        return web.Response(
            body=response, content_type=CONTENT_TYPE_XML, status=200)
