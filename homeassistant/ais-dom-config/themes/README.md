# Home Assistant Community Themes
> All community themes in one repository

## Themes

| Theme           | Credits                                                                                                                                                              | Variable            |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| Christmas       | [moose517](https://community.home-assistant.io/u/moose517) posted [Christmas Theme](https://community.home-assistant.io/t/christmas-theme/34036)                     | christmas           |
| Dark Cyan       | [broesie](https://community.home-assistant.io/u/broesie) posted [Dark Cyan Theme](https://community.home-assistant.io/t/dark-cyan-theme/28594)                       | dark_cyan           |
| Dark Orange     | [Bram_Kragten](https://community.home-assistant.io/u/Bram_Kragten) posted [Orange Theme](https://community.home-assistant.io/t/orange-theme/28601)                   | dark_orange         |
| Dark Red        | [broesie](https://community.home-assistant.io/u/broesie) posted [Dark Red Theme](https://community.home-assistant.io/t/dark-red-theme/28592)                         | dark_red            |
| Another Dark    | [lambtho](https://community.home-assistant.io/u/lambtho) posted [Another Dark Theme](https://community.home-assistant.io/t/another-dark-theme/28595)                 | dark                |
| Halloween       | [skalavala](https://community.home-assistant.io/u/skalavala) posted [Halloween Theme](https://community.home-assistant.io/t/halloween-theme/30872)                   | halloween           |
| Material Dark   | [matust](https://community.home-assistant.io/u/matust) posted [Material dark theme](https://community.home-assistant.io/t/material-dark-theme/30796)                 | material_dark_green |
| Midnight        | [marcelhoffs](https://community.home-assistant.io/u/marcelhoffs) posted [Midnight Theme](https://community.home-assistant.io/t/midnight-theme/28598)                 | midnight            |
| Grey Night      | [ksya](https://community.home-assistant.io/u/ksya) posted [Grey Night theme](https://community.home-assistant.io/t/grey-night-theme/30848)                           | night               |
| Solarized Light | [snwtoy](https://community.home-assistant.io/u/snwtoy) posted [Solarized Light theme](https://community.home-assistant.io/t/solarized-light-theme/42713)             | solarized_light     |
| Sublimination   | [MikaelSchultz](https://community.home-assistant.io/u/MikaelSchultz) posted [Sublimination Theme](https://community.home-assistant.io/t/sublimination-theme/67312)   | sublimination       |
| Black and Green | [GreenTurtwig](https://community.home-assistant.io/u/GreenTurtwig) posted [Black and Green Theme](https://community.home-assistant.io/t/black-and-green-theme/28602) | teal                |
| Vintage         | [surendran.anup](https://community.home-assistant.io/u/surendran.anup) posted [Vintage Theme](https://community.home-assistant.io/t/vintage-theme/42806)             | vintage             |

> Do you enjoy one of the community themes? Show the creator some love by pressing the :heart: under the body of the post.

Your theme not listed? Create a pull request or an issue.

##  Installation

Clone this repository in your existing (or create it) `themes/` folder.

```bash
cd themes/
git clone https://github.com/maartenpaauw/home-assistant-community-themes.git
```

Or using submodules:

```bash
cd themes/
git submodule add https://github.com/maartenpaauw/home-assistant-community-themes.git
```

Add the following code to your `configuration.yaml` file.

```yaml
frontend:
  ... # your configuration.
  themes: !include_dir_merge_named themes
  ... # your configuration.
```
