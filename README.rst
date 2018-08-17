Home Assistant |Build Status| |Coverage Status| |Chat Status| |Reviewed by Hound|
=================================================================================

Home Assistant is a home automation platform running on Python 3. It is able to track and control all devices at home and offer a platform for automating control.

To get started:

.. code:: bash

    python3 -m pip install homeassistant
    hass --open-ui

Check out `home-assistant.io <https://home-assistant.io>`__ for `a
demo <https://home-assistant.io/demo/>`__, `installation instructions <https://home-assistant.io/getting-started/>`__,
`tutorials <https://home-assistant.io/getting-started/automation-2/>`__ and `documentation <https://home-assistant.io/docs/>`__.

|screenshot-states|

Featured integrations
---------------------

|screenshot-components|

The system is built using a modular approach so support for other devices or actions can be implemented easily. See also the `section on architecture <https://home-assistant.io/developers/architecture/>`__ and the `section on creating your own
components <https://home-assistant.io/developers/creating_components/>`__.

If you run into issues while using Home Assistant or during development
of a component, check the `Home Assistant help section <https://home-assistant.io/help/>`__ of our website for further help and information.

.. |Build Status| image:: https://travis-ci.org/home-assistant/home-assistant.svg?branch=master
   :target: https://travis-ci.org/home-assistant/home-assistant
.. |Coverage Status| image:: https://img.shields.io/coveralls/home-assistant/home-assistant.svg
   :target: https://coveralls.io/r/home-assistant/home-assistant?branch=master
.. |Chat Status| image:: https://img.shields.io/discord/330944238910963714.svg
   :target: https://discord.gg/c5DvZ4e
.. |Reviewed by Hound| image:: https://img.shields.io/badge/Reviewed_by-Hound-8E64B0.svg
   :target: https://houndci.com
.. |screenshot-states| image:: https://raw.github.com/home-assistant/home-assistant/master/docs/screenshots.png
   :target: https://home-assistant.io/demo/
.. |screenshot-components| image:: https://raw.github.com/home-assistant/home-assistant/dev/docs/screenshot-components.png
   :target: https://home-assistant.io/components/
