# EffortlessHome

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Discord][discord-shield]][discord]
[![Community Forum][forum-shield]][forum]

EffortlessHome is a simplified Home Assistant integration focused on service-based actions and setup helpers.

## Features

- Config flow with account sign-in and system selection.
- Service endpoints for creating alerts/events and maintaining entity metadata.
- Optional deployment helper to copy packaged web resources/config assets.
- Device-class group synchronization at startup.

## Installation

### HACS Installation (Recommended)

1. Open HACS in your Home Assistant instance
2. Add this Github Repo as a custom source
3. Search for "EffortlessHome"
4. Click Install
5. Restart Home Assistant

### Manual Installation

1. Copy the `effortlesshome` directory to your `custom_components` folder
2. Restart Home Assistant
3. Add the integration via Configuration > Integrations > Add Integration > EffortlessHome

## Configuration

### Initial Setup

1. After installation, go to Configuration > Integrations
2. Click the "+" button and search for "EffortlessHome"
3. Enter your EffortlessHome account credentials
4. Select the system you want to configure (if you have multiple systems)

### Required Information

- **Email**: Your EffortlessHome account email
- **Password**: Your EffortlessHome account password

### Optional Configuration

After initial setup, you can configure additional options:

- **Debug Mode**: Enable debug logging for troubleshooting

## Services

The integration provides several services:

| Service | Description |
|---------|-------------|
| `effortlesshome.clean_motion_files` | Clean old motion snapshot files |
| `effortlesshome.create_alert` | Create an alert record |
| `effortlesshome.create_event` | Create an event for active alarm |
| `effortlesshome.deploy_latest_config` | Deploy latest configuration files |
| `effortlesshome.add_label_to_entity` | Add a label to an entity |
| `effortlesshome.update_entity` | Update entity area assignment |

## Entities

This simplified integration does not register dedicated entity platforms.

## Requirements

### Dependencies

This integration requires the following Python packages (automatically installed):

- `oasira>=0.2.12`
- `gcal-sync>=6.2.0`
- `google-auth>=2.28.0`
- `google-api-python-client>=2.126.0`
- `gTTS>=2.5.0`
- `google-genai==1.29.0`
- `influxdb-client>=1.48.0`

### Home Assistant Dependencies

The integration requires the following Home Assistant components:

- `http`
- `recorder`
- `conversation`

## Labels

The integration uses the following labels for entity organization:

- `Favorite`: Mark favorite entities
- `NotForSecurityMonitoring`: Exclude entities from security monitoring

## Support

- **GitHub Issues**: [Report bugs and feature requests](https://github.com/EffortlessHome/EffortlessHome/issues)
- **Discord Community**: [Join our Discord server](https://discord.gg/effortlesshome)
- **Forum**: [Community Forum](https://community.home-assistant.io/t/effortlesshome/)

## Contributing

We welcome contributions! Please see our [contributing guidelines](CONTRIBUTING.md) for more information.

## Run Home Assistant Core PR Checks Locally

From this `effortlesshome` folder, you can run the same core checks used in Home Assistant CI:

1. First-time setup (create `.venv` in core and install dev/test dependencies):

	```powershell
	.\run_core_pr_checks.ps1 -Setup -Checks all
	```

2. Run all requested checks:

	```powershell
	.\run_core_pr_checks.ps1 -Checks all
	```

3. Run individual checks:

	```powershell
	.\run_core_pr_checks.ps1 -Checks prek
	.\run_core_pr_checks.ps1 -Checks hassfest
	.\run_core_pr_checks.ps1 -Checks pylint
	.\run_core_pr_checks.ps1 -Checks mypy
	```

This script targets `homeassistant/components/effortlesshome` for pylint/mypy and uses the same `PREK_SKIP` split as the CI workflow so that `prek` does not duplicate `hassfest`, `pylint`, and `mypy`.

VS Code tasks are also included in `.vscode/tasks.json` for one-click runs.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Home Assistant community
- All contributors and testers
- EffortlessHome users

---

**Note**: This integration requires an EffortlessHome account. Sign up at [https://my.effortlesshome.co](https://my.effortlesshome.co)

[buymecoffee]: https://www.buymecoffee.com/effortlesshome
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[discord]: https://discord.gg/effortlesshome
[discord-shield]: https://img.shields.io/discord/1234567890?color=7289da&label=Discord&logo=discord&logoColor=white&style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge&logo=home-assistant
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/EffortlessHome/EffortlessHome.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/maintenance/yes/2024.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/EffortlessHome/EffortlessHome.svg?style=for-the-badge
[releases]: https://github.com/EffortlessHome/EffortlessHome/releases