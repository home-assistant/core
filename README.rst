Repository for the Home Asssisant Core of GM4

Home Assistant SMHI Integration Project - Group Milestone 4
=======================================

Overview
--------

This project integrates Swedish Meteorological and Hydrological Institute (SMHI) weather data into Home Assistant, providing users with comprehensive weather information across Sweden.

Group Memembers
--------
| faeazehmhmdi - Faezeh Mohammadi
| FN890 - Filip Nordquist
| RasmusOtterlind - Rasumus Otterlind
| sam-salek - Sam Salek
| Xerxz - Simon Andersson
| pillezu - Viktor Berggren

Features
--------

* Interactive Weather Map: Displays real-time weather data across Sweden.
* Weather Alerts and Warnings: Provides updates on weather-related warnings.
* Lightning Impact Visualization: Shows areas affected by lightning strikes.
* Fire Risk Indicators: Highlights regions with high fire risk levels.
* Radar Movement on Dashboard: Visualizes weather radar movements.

Getting Started
---------------

Prerequisites
~~~~~~~~~~~~~

* Docker installed on your machine.
* Visual Studio Code.

Installation
~~~~~~~~~~~~

1. **Install Docker**: Follow the instructions on the `Docker website <https://www.docker.com/get-started>`_ to download and install Docker for your operating system.

2. **Clone the Repository**:

   * Open Visual Studio Code.
   * Run the command to clone the repository into a Docker container:

   .. code-block:: none

       vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https%3A%2F%2Fgithub.com%2Fpillezu%2FcoreGM4

3. **Run Home Assistant**:

   * For Mac: Press ``Shift+Command+P``
   * For Windows/Linux: Press ``Ctrl+Shift+P``
   * Select ``Tasks: Run Task``.
   * Choose ``Run Home Assistant``.

Usage
-----

Accessing SMHI Integration Features
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **Edit Dashboard**:

   * Navigate to your Home Assistant dashboard.
   * Click on ``Edit Dashboard``.

2. **Add Entities Card**:

   * Choose ``Add Card`` and select the ``Entities Card``.
   * Add the following entities:

     * ``Display Fire Risk``
     * ``Display Lightning``
     * ``Display Warnings``
     * ``Display Weather``

   These entities control what information is displayed on the map.

3. **Add Picture Card for Radar Map**:

   * Add a ``Picture Card`` to your dashboard.
   * Include the ``SMHI Radar Map`` entity.
   * This displays the radar movement.

Acknowledgments
---------------

* Swedish Meteorological and Hydrological Institute (SMHI) for providing the weather data.

