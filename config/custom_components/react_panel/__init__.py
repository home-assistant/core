"""
Custom panel example showing TodoMVC using React.

Will add a panel to control lights and switches using React. Allows configuring
the title via configuration.yaml:

react_panel:
  title: 'home'

"""
import os

from homeassistant.components.frontend import register_panel

DOMAIN = 'react_panel'
DEPENDENCIES = ['frontend']

PANEL_PATH = os.path.join(os.path.dirname(__file__), 'panel.html')


def setup(hass, config):
    """Initialize custom panel."""
    title = config.get(DOMAIN, {}).get('title')

    config = None if title is None else {'title': title}

    register_panel(hass, 'react', PANEL_PATH,
                   title='TodoMVC', icon='mdi:checkbox-marked-outline',
                   config=config)
    return True
