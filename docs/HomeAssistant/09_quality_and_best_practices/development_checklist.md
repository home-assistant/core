---
title: "Development checklist"
sidebar_label: Introduction
---

Before you commit any changes, check your work against these requirements:

- All communication to external devices or services must be wrapped in an external Python library hosted on [pypi](https://pypi.org/).
  - The library must have source distribution packages available; it's not allowed to rely on packages that only have binary distribution packages.
  - Issue trackers must be enabled for external Python libraries that communicate with external devices or services.
  - If the library is mainly used for Home Assistant and you are a code owner of the integration, it is encouraged to use an issue template picker with links to [Home Assistant Core Issues](https://github.com/home-assistant/core/issues). For example: [zwave-js-server-python - New Issue](https://github.com/home-assistant-libs/zwave-js-server-python/issues/new/choose)
- New dependencies are added to `requirements_all.txt` (if applicable), using `python3 -m script.gen_requirements_all`
- New codeowners are added to `CODEOWNERS` (if applicable), using `python3 -m script.hassfest`
- The `.strict-typing` file is updated to include your code if it provides a fully type hinted source.
- The code is formatted using Ruff (`ruff format`).
- Documentation is developed for [home-assistant.io](https://home-assistant.io/)
  - Visit the [website documentation](/documenting.md) for more information about contributing to [home-assistant.io](https://github.com/home-assistant/home-assistant.io).
