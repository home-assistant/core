# Adding support for a new device

You've probably came here beacuse you noticed that your favorite device is not supported and want to add it.

First step is to decide under which component the device has to reside. Each component is responsible for a specific domain within Home Assistant. An example is the switch component, which is responsible for interaction with different types of switches. The switch component consists of the following files:

**homeassistant/components/switch/\_\_init\_\_.py**<br />
Contains the Switch component code.

**homeassistant/components/switch/wemo.py**<br />
Contains the code to interact with WeMo switches. Called if type=wemo in switch config. 

**homeassistant/components/switch/tellstick.py**
Contains the code to interact with Tellstick switches. Called if type=tellstick in switch config.

If a component exists, your job is easy. Have a look at how the component works with other platforms and create a similar file for the platform that you would like to add.If you cannot find a suitable component, you'll have to add it yourself. When writing a component try to structure it after the Switch component to maximize reusability.

Communication between Home Assistant and devices should happen via third-party libraries that implement the device API. This will make sure the platform support code stays as small as possible.

After you finish adding support for your device:

 - update the supported devices in README.md.
 - add any new dependencies to requirements.txt.
 - Make sure all your code passes Pylint and PEP8 validation. To generate reports, run `pylint homeassistant > pylint.txt` and `pep8 homeassistant --exclude bower_components,external > pep8.txt`.

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
