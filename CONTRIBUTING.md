# Adding support for a new device

For help on building your component, please see the See the [developer documentation on home-assistant.io](https://home-assistant.io/developers/).

After you finish adding support for your device:

 - update the supported devices in README.md.
 - add any new dependencies to requirements.txt.
 - Make sure all your code passes Pylint, flake8 (PEP8 and some more) validation. To generate reports, run `pylint homeassistant > pylint.txt` and `flake8 homeassistant --exclude bower_components,external > flake8.txt`.

If you've added a component:

 - update the file [`domain-icon.html`](https://github.com/balloob/home-assistant/blob/master/homeassistant/components/http/www_static/polymer/domain-icon.html) with an icon for your domain ([pick from this list](https://www.polymer-project.org/components/core-icons/demo.html))
 - update the demo component with two states that it provides
 - Add your component to home-assistant.conf.example

Since you've updated domain-icon.html, you've made changes to the frontend:

 - run `build_frontend`. This will build a new version of the frontend. Make sure you add the changed files `frontend.py` and `frontend.html` to the commit.

## Setting states

It is the responsibility of the component to maintain the states of the devices in your domain. Each device should be a single state and, if possible, a group should be provided that tracks the combined state of the devices.

A state can have several attributes that will help the frontend in displaying your state:

 - `friendly_name`: this name will be used as the name of the device
 - `entity_picture`: this picture will be shown instead of the domain icon
 - `unit_of_measurement`: this will be appended to the state in the interface

These attributes are defined in [homeassistant.components](https://github.com/balloob/home-assistant/blob/master/homeassistant/components/__init__.py#L25).

## Working on the frontend

The frontend is composed of Polymer web-components and compiled into the file `frontend.html`. During development you do not want to work with the compiled version but with the seperate files. To have Home Assistant serve the seperate files, set `development=1` for the http-component in your config.

When you are done with development and ready to commit your changes, run `build_frontend`, set `development=0` in your config and validate that everything still works.

## Notes on PyLint and PEP8 validation

In case a PyLint warning cannot be avoided, add a comment to disable the PyLint check for that line. This can be done using the format `# pylint: disable=YOUR-ERROR-NAME`. Example of an unavoidable PyLint warning is if you do not use the passed in datetime if you're listening for time change.
