# Minecraft Server - LAN Discovery Extension
> Adds local network discovery and user-friendly labels (MOTD) to the Home Assistant `minecraft_server` integration.

This extension helps users find Minecraft servers on their local network and pick the desired one using the server's Message of the Day (MOTD) shown next to the `IP address` in the drop-down menu.

---

## Table of contents
- [Quick demo](#quick-demo)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [How to use](#how-to-use)
- [Technical details](#technical-details)

---
## Quick demo
This is a showcase of a populated list of various servers and their MOTD displayed for the user to choose one of them to add to the Home Assistant Dashboard.

<a href="https://ibb.co/rGFyGWXW"><img src="https://i.ibb.co/6RrsRdqd/image.webp" alt="image" border="0"></a>

---

## Features
*  **Automatic and Asynchronous Discovery**: Automatically scan the local network for available Minecraft servers by asynchronously pinging all potential IP addresses between the 1 and 255 subnet.
*  **Drop-down Menu**: Replace the standard text box where the user inputs the IP address with a drop-down menu that containts the discovered servers.
*  **Manual Intervention**: If a server is not automatically discovered, the selector supports custom value entry which allows you to manually input an IP address.
*  **Servers MOTD**: Each server's MOTD is shown next to its IP address in the drop-down menu to help the user distinguish between the various servers.

---

## Requirements
*  **Home Assistant**: Home assistant is a prerequisite for this integration. [Click here](https://www.home-assistant.io/installation/) to help get you started.
*  **Dependencies**:
*  *  `netifaces`: Used to identify local network interfaces.
   *  Existing dependencies of the core Minecraft server integration (`mcstatus`).

---

## Installation
Since this is an extension of an existing integarition, you can install it as a custom component.

1.  Download this repository.
2.  Copy the `Minecraft_server` folder found in `homeassistant/components/` and replace your current folder and all files within it with the updated version. Alternatively, you can download and replace the entire Home Assistant directory.
3.  Restart and rebuild Home Assistant.

---

## How to use
1.  In Home Assistant, navigate to **Settings** > **Devices & Services**.
2.  Click **+ Add Integration in the bottom right corner**.
3.  Search for **Minecraft Server**.
4.  The configuration flow will automatically trigger the discovery process.
    *  *Please wait a moment while the integration scans your local network.*
5.  Link your **Minecraft Server** and click on the input box to launch the drop-down menu populated with all discovered servers.
6.  Choose the desired server and submit your choice.

---

## Technical details

###  How scanning works
The `ServerLocator` class utilizes `netifaces` to find the host machine's local network interfaces and generates addresses within a range of `.1`–`.254` which is one of the most common subnets (`.0` and `.255` are excluded beacuse the former is the host and the latter is the broadcast).<br>
For each address, the locator checks a set of ports to build a list of entries.
The config flow then performs an asynchronous status request against each discovered IP address to read the server's MOTD.
