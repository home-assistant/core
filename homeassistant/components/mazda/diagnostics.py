





<!DOCTYPE html>
<html lang="en" data-color-mode="auto" data-light-theme="light" data-dark-theme="dark"  data-a11y-animated-images="system" data-a11y-link-underlines="false">

    <style>
  /* for each iteration, uncomment the CSS variable */

  /* light themes */
  [data-color-mode="light"][data-light-theme*="light"],
  [data-color-mode="auto"][data-light-theme*="light"] {
    /* iteration 1 */
    --border-color-iteration-1: #C8CCD0;
    /* iteration 2 */
    --border-color-iteration-2: #BABFC5;
    /* iteration 3 */
    --border-color-iteration-3: #A6ADB4;
    /* iteration final */
    /* --border-color-iteration-4: #868F99; */

    /* the first value is the final step, which falls back to previous iterations */
    --control-borderColor-rest: var(--border-color-iteration-4, var(--border-color-iteration-3, var(--border-color-iteration-2, var(--border-color-iteration-1)))) !important;
  }

  /* dark themes */
  [data-color-mode="dark"][data-dark-theme*="dark"],
  [data-color-mode="auto"][data-light-theme*="dark"] {
    /* iteration 1 */
    --border-color-iteration-1: #363940;
    /* iteration 2 */
    --border-color-iteration-2: #3F434B;
    /* iteration 3 */
    --border-color-iteration-3: #4B5159;
    /* iteration final */
    /* --border-color-iteration-4: #666E79; */

    /* the first value is the final step, which falls back to previous iterations */
    --control-borderColor-rest: var(--border-color-iteration-4, var(--border-color-iteration-3, var(--border-color-iteration-2, var(--border-color-iteration-1)))) !important;
  }

  [data-color-mode="dark"][data-dark-theme="dark_dimmed"],
  [data-color-mode="dark"][data-dark-theme="light_high_contrast"],
  [data-color-mode="dark"][data-dark-theme="dark_high_contrast"],
  [data-color-mode="light"][data-light-theme="dark_dimmed"],
  [data-color-mode="light"][data-light-theme="light_high_contrast"],
  [data-color-mode="light"][data-light-theme="dark_high_contrast"] {
    /* skip these themes, use the fallback */
    --control-borderColor-rest: initial !important;
  }

  @media (prefers-color-scheme: dark) {
    /* dark colors in dark mode */
    [data-color-mode="auto"][data-dark-theme*="dark"] {
      /* iteration 1 */
      --border-color-iteration-1: #363940;
      /* iteration 2 */
      --border-color-iteration-2: #3F434B;
      /* iteration 3 */
      --border-color-iteration-3: #4B5159;
      /* iteration final */
      /* --border-color-iteration-4: #666E79; */

      /* the first value is the final step, which falls back to previous iterations */
      --control-borderColor-rest: var(--border-color-iteration-4, var(--border-color-iteration-3, var(--border-color-iteration-2, var(--border-color-iteration-1)))) !important;
    }

    /* light colors in dark mode */
    [data-color-mode="auto"][data-dark-theme*="light"] {
      /* iteration 1 */
      --border-color-iteration-1: #C8CCD0;
      /* iteration 2 */
      --border-color-iteration-2: #BABFC5;
      /* iteration 3 */
      --border-color-iteration-3: #A6ADB4;
      /* iteration final */
      /* --border-color-iteration-4: #868F99; */

      /* the first value is the final step, which falls back to previous iterations */
      --control-borderColor-rest: var(--border-color-iteration-4, var(--border-color-iteration-3, var(--border-color-iteration-2, var(--border-color-iteration-1)))) !important;
      }

    [data-color-mode="auto"][data-dark-theme="dark_dimmed"],
    [data-color-mode="auto"][data-dark-theme="light_high_contrast"],
    [data-color-mode="auto"][data-dark-theme="dark_high_contrast"] {
      /* skip these themes, use the fallback */
      --control-borderColor-rest: initial !important;
    }
  }

  @media (prefers-color-scheme: light) {
    /* dark colors in light mode */
    [data-color-mode="auto"][data-light-theme*="dark"] {
      /* iteration 1 */
      --border-color-iteration-1: #363940;
      /* iteration 2 */
      --border-color-iteration-2: #3F434B;
      /* iteration 3 */
      --border-color-iteration-3: #4B5159;
      /* iteration final */
      /* --border-color-iteration-4: #666E79; */

      /* the first value is the final step, which falls back to previous iterations */
      --control-borderColor-rest: var(--border-color-iteration-4, var(--border-color-iteration-3, var(--border-color-iteration-2, var(--border-color-iteration-1)))) !important;
    }

    /* light colors in light mode */
    [data-color-mode="auto"][data-light-theme*="light"] {
      /* iteration 1 */
      --border-color-iteration-1: #C8CCD0;
      /* iteration 2 */
      --border-color-iteration-2: #BABFC5;
      /* iteration 3 */
      --border-color-iteration-3: #A6ADB4;
      /* iteration final */
      /* --border-color-iteration-4: #868F99; */

      /* the first value is the final step, which falls back to previous iterations */
      --control-borderColor-rest: var(--border-color-iteration-4, var(--border-color-iteration-3, var(--border-color-iteration-2, var(--border-color-iteration-1)))) !important;
    }

    [data-color-mode="auto"][data-light-theme="dark_dimmed"],
    [data-color-mode="auto"][data-light-theme="light_high_contrast"],
    [data-color-mode="auto"][data-light-theme="dark_high_contrast"] {
      /* skip these themes, use the fallback */
      --control-borderColor-rest: initial !important;
    }
  }
</style>


  <head>
    <meta charset="utf-8">
  <link rel="dns-prefetch" href="https://github.githubassets.com">
  <link rel="dns-prefetch" href="https://avatars.githubusercontent.com">
  <link rel="dns-prefetch" href="https://github-cloud.s3.amazonaws.com">
  <link rel="dns-prefetch" href="https://user-images.githubusercontent.com/">
  <link rel="preconnect" href="https://github.githubassets.com" crossorigin>
  <link rel="preconnect" href="https://avatars.githubusercontent.com">

  


  <link crossorigin="anonymous" media="all" rel="stylesheet" href="https://github.githubassets.com/assets/light-b92e9647318f.css" /><link crossorigin="anonymous" media="all" rel="stylesheet" href="https://github.githubassets.com/assets/dark-5d486a4ede8e.css" /><link data-color-theme="dark_dimmed" crossorigin="anonymous" media="all" rel="stylesheet" data-href="https://github.githubassets.com/assets/dark_dimmed-27c8d635e4e5.css" /><link data-color-theme="dark_high_contrast" crossorigin="anonymous" media="all" rel="stylesheet" data-href="https://github.githubassets.com/assets/dark_high_contrast-8438e75afd36.css" /><link data-color-theme="dark_colorblind" crossorigin="anonymous" media="all" rel="stylesheet" data-href="https://github.githubassets.com/assets/dark_colorblind-bf5665b96628.css" /><link data-color-theme="light_colorblind" crossorigin="anonymous" media="all" rel="stylesheet" data-href="https://github.githubassets.com/assets/light_colorblind-c414b5ba1dce.css" /><link data-color-theme="light_high_contrast" crossorigin="anonymous" media="all" rel="stylesheet" data-href="https://github.githubassets.com/assets/light_high_contrast-e5868b7374db.css" /><link data-color-theme="light_tritanopia" crossorigin="anonymous" media="all" rel="stylesheet" data-href="https://github.githubassets.com/assets/light_tritanopia-299ac9c64ec0.css" /><link data-color-theme="dark_tritanopia" crossorigin="anonymous" media="all" rel="stylesheet" data-href="https://github.githubassets.com/assets/dark_tritanopia-3a26e78ad0ff.css" />
  
    <link crossorigin="anonymous" media="all" rel="stylesheet" href="https://github.githubassets.com/assets/primer-primitives-6143c8f97ed1.css" />
    <link crossorigin="anonymous" media="all" rel="stylesheet" href="https://github.githubassets.com/assets/primer-d6dcdf72e61d.css" />
    <link crossorigin="anonymous" media="all" rel="stylesheet" href="https://github.githubassets.com/assets/global-e1566d734d5b.css" />
    <link crossorigin="anonymous" media="all" rel="stylesheet" href="https://github.githubassets.com/assets/github-933ef5369a60.css" />
  <link crossorigin="anonymous" media="all" rel="stylesheet" href="https://github.githubassets.com/assets/code-71ecd5638fbf.css" />

  

  <script type="application/json" id="client-env">{"locale":"en","featureFlags":["failbot_handle_non_errors","geojson_azure_maps","hovercard_show_on_focus","image_metric_tracking","repository_suggester_elastic_search","turbo_experiment_risky","sample_network_conn_type","star_button_focus"]}</script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/wp-runtime-f04178066551.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_dompurify_dist_purify_js-64d590970fa6.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_stacktrace-parser_dist_stack-trace-parser_esm_js-node_modules_github_bro-a4c183-18bf85b8e9f4.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/ui_packages_soft-nav_soft-nav_ts-56133143b228.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/environment-fc6543d75794.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_github_selector-observer_dist_index_esm_js-2646a2c533e3.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_behaviors_dist_esm_focus-zone_js-d55308df5023.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_github_relative-time-element_dist_index_js-99e288659d4f.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_fzy_js_index_js-node_modules_github_combobox-nav_dist_index_js-node_modu-344bff-91b70bb50d68.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_delegated-events_dist_index_js-node_modules_github_details-dialog-elemen-29dc30-2a5b7c1aa525.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_github_filter-input-element_dist_index_js-node_modules_github_remote-inp-59c459-39506636d610.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_github_file-attachment-element_dist_index_js-node_modules_primer_view-co-2c6968-d14fe7eeba42.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/github-elements-3485f2997bc6.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/element-registry-981cc2eaa259.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_github_catalyst_lib_index_js-node_modules_github_hydro-analytics-client_-978abc0-d5b921292620.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_lit-html_lit-html_js-4ccebb6ebf7d.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_github_mini-throttle_dist_index_js-node_modules_github_alive-client_dist-bf5aa2-504c8d53fb8e.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_morphdom_dist_morphdom-esm_js-b1fdd7158cf0.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_github_turbo_dist_turbo_es2017-esm_js-9a3541181451.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_color-convert_index_js-35b3ae68c408.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_behaviors_dist_esm_dimensions_js-node_modules_github_hotkey_dist_-8755d2-f721427ba08d.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_github_session-resume_dist_index_js-node_modules_primer_behaviors_dist_e-ac74c6-4e7cf4e77afd.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_github_paste-markdown_dist_index_esm_js-node_modules_github_quote-select-854ff4-b4a2793be3fe.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/app_assets_modules_github_details-dialog_ts-app_assets_modules_github_fetch_ts-add1ab03ecb3.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/app_assets_modules_github_updatable-content_ts-ui_packages_hydro-analytics_hydro-analytics_ts-0a5a30c9b976.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/app_assets_modules_github_onfocus_ts-app_assets_modules_github_sticky-scroll-into-view_ts-c56a5dfc8975.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/app_assets_modules_github_behaviors_task-list_ts-app_assets_modules_github_sso_ts-ui_packages-7d50ad-9491f2be61ee.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/app_assets_modules_github_behaviors_ajax-error_ts-app_assets_modules_github_behaviors_include-2e2258-d77f85c54572.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/app_assets_modules_github_behaviors_commenting_edit_ts-app_assets_modules_github_behaviors_ht-83c235-f22ac6b94445.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/behaviors-ac60f5882386.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_delegated-events_dist_index_js-node_modules_github_catalyst_lib_index_js-623425af41e1.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/notifications-global-0104a8043aa4.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/code-menu-6bd50a0647d6.js"></script>
  
  <script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/react-lib-210c4b5934c3.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_octicons-react_dist_index_esm_js-node_modules_primer_react_lib-es-2e8e7c-cf03673d2172.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_react_lib-esm_Box_Box_js-96a44addc402.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_react_lib-esm_Button_Button_js-node_modules_primer_react_lib-esm_-f6da63-1976b80d3486.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_react_node_modules_primer_octicons-react_dist_index_esm_js-03b6dd82d40a.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_react_lib-esm_Button_index_js-node_modules_primer_react_lib-esm_O-701f13-047a44a18d3a.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_react_lib-esm_Text_Text_js-node_modules_primer_react_lib-esm_Text-85a14b-0f28951279b7.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_react_lib-esm_ActionList_index_js-535c8ee1ebe8.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_react_lib-esm_ActionMenu_ActionMenu_js-2f08ef908241.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_behaviors_dist_esm_scroll-into-view_js-node_modules_primer_react_-04bb1b-a6096689d2d5.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_react_lib-esm_FormControl_FormControl_js-9b048a5a5ceb.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_react-router-dom_dist_index_js-4a785319b497.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_react_lib-esm_PageLayout_PageLayout_js-7693f4e3427d.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_react_lib-esm_Dialog_js-node_modules_primer_react_lib-esm_Flash_F-ad64b6-f3217651e114.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_react_lib-esm_UnderlineNav2_index_js-b739f40cf454.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_react_lib-esm_Avatar_Avatar_js-node_modules_primer_react_lib-esm_-9bd36c-c9a87fd5afd0.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_react_lib-esm_AvatarStack_AvatarStack_js-node_modules_primer_reac-6d3540-684005f5bdbe.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_primer_react_lib-esm_Breadcrumbs_Breadcrumbs_js-node_modules_primer_reac-31943d-f0539d68eb2b.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/ui_packages_react-core_create-browser-history_ts-ui_packages_react-core_deferred-registry_ts--ebbb92-1ee1e572fd0e.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/ui_packages_react-core_register-app_ts-afd2d748b726.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/ui_packages_ref-selector_RefSelector_tsx-bd2f6d26f4a6.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/app_assets_modules_github_blob-anchor_ts-app_assets_modules_github_filter-sort_ts-app_assets_-681869-f63e0555b81f.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/app_assets_modules_react-code-view_pages_CodeView_tsx-e1cade75e2ca.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/react-code-view-eb5ce0ba2c27.js"></script>


  <title>core/homeassistant/components/mazda/diagnostics.py at 2023.10.1 · home-assistant/core</title>



  <meta name="route-pattern" content="/:user_id/:repository/blob/*name(/*path)">

    
  <meta name="current-catalog-service-hash" content="82c569b93da5c18ed649ebd4c2c79437db4611a6a1373e805a3cb001c64130b7">


  <meta name="request-id" content="CD9A:2227:14F23F:1E186D:65282A29" data-turbo-transient="true" /><meta name="html-safe-nonce" content="06e32267733aec8799f3f928dfa1a3d0448a015a0680e54460a8862cc559fc12" data-turbo-transient="true" /><meta name="visitor-payload" content="eyJyZWZlcnJlciI6Imh0dHBzOi8vZ2l0aHViLmNvbS9ob21lLWFzc2lzdGFudC9jb3JlL3RyZWUvMjAyMy4xMC4xL2hvbWVhc3Npc3RhbnQvY29tcG9uZW50cy9tYXpkYSIsInJlcXVlc3RfaWQiOiJDRDlBOjIyMjc6MTRGMjNGOjFFMTg2RDo2NTI4MkEyOSIsInZpc2l0b3JfaWQiOiIzNDMyNzcyNDI5OTk1ODYxMDM0IiwicmVnaW9uX2VkZ2UiOiJpYWQiLCJyZWdpb25fcmVuZGVyIjoiaWFkIn0=" data-turbo-transient="true" /><meta name="visitor-hmac" content="d5f74081d631c65928a544dd339b9803a27fe525f21b44a4df27071bbb482e91" data-turbo-transient="true" />


    <meta name="hovercard-subject-tag" content="repository:12888993" data-turbo-transient>


  <meta name="github-keyboard-shortcuts" content="repository,source-code,file-tree" data-turbo-transient="true" />
  

  <meta name="selected-link" value="repo_source" data-turbo-transient>
  <link rel="assets" href="https://github.githubassets.com/">

    <meta name="google-site-verification" content="c1kuD-K2HIVF635lypcsWPoD4kilo5-jA_wBFyT4uMY">
  <meta name="google-site-verification" content="KT5gs8h0wvaagLKAVWq8bbeNwnZZK1r1XQysX3xurLU">
  <meta name="google-site-verification" content="ZzhVyEFwb7w3e0-uOTltm8Jsck2F5StVihD0exw2fsA">
  <meta name="google-site-verification" content="GXs5KoUUkNCoaAZn7wPN-t01Pywp9M3sEjnt_3_ZWPc">
  <meta name="google-site-verification" content="Apib7-x98H0j5cPqHWwSMm6dNU4GmODRoqxLiDzdx9I">

<meta name="octolytics-url" content="https://collector.github.com/github/collect" /><meta name="octolytics-actor-id" content="106836726" /><meta name="octolytics-actor-login" content="eufysecurity" /><meta name="octolytics-actor-hash" content="28bf03a64dfc1bc176455321ac0b6f9745f58fe67490bd294a4e79641cec5e07" />

  <meta name="analytics-location" content="/&lt;user-name&gt;/&lt;repo-name&gt;/blob/show" data-turbo-transient="true" />

  




  

    <meta name="user-login" content="eufysecurity">

  <link rel="sudo-modal" href="/sessions/sudo_modal">

    <meta name="viewport" content="width=device-width">
    
      <meta name="description" content=":house_with_garden: Open source home automation that puts local control and privacy first. - core/homeassistant/components/mazda/diagnostics.py at 2023.10.1 · home-assistant/core">
      <link rel="search" type="application/opensearchdescription+xml" href="/opensearch.xml" title="GitHub">
    <link rel="fluid-icon" href="https://github.com/fluidicon.png" title="GitHub">
    <meta property="fb:app_id" content="1401488693436528">
    <meta name="apple-itunes-app" content="app-id=1477376905, app-argument=https://github.com/home-assistant/core/blob/2023.10.1/homeassistant/components/mazda/diagnostics.py" />
      <meta name="twitter:image:src" content="https://repository-images.githubusercontent.com/12888993/0f9eb780-655b-11e9-85cb-0d3956096fe5" /><meta name="twitter:site" content="@github" /><meta name="twitter:card" content="summary_large_image" /><meta name="twitter:title" content="core/homeassistant/components/mazda/diagnostics.py at 2023.10.1 · home-assistant/core" /><meta name="twitter:description" content=":house_with_garden: Open source home automation that puts local control and privacy first. - home-assistant/core" />
      <meta property="og:image" content="https://repository-images.githubusercontent.com/12888993/0f9eb780-655b-11e9-85cb-0d3956096fe5" /><meta property="og:image:alt" content=":house_with_garden: Open source home automation that puts local control and privacy first. - home-assistant/core" /><meta property="og:site_name" content="GitHub" /><meta property="og:type" content="object" /><meta property="og:title" content="core/homeassistant/components/mazda/diagnostics.py at 2023.10.1 · home-assistant/core" /><meta property="og:url" content="https://github.com/home-assistant/core/blob/2023.10.1/homeassistant/components/mazda/diagnostics.py" /><meta property="og:description" content=":house_with_garden: Open source home automation that puts local control and privacy first. - home-assistant/core" />
      

      <link rel="shared-web-socket" href="wss://alive.github.com/_sockets/u/106836726/ws?session=eyJ2IjoiVjMiLCJ1IjoxMDY4MzY3MjYsInMiOjEyMjE3MDU5NzUsImMiOjE0NjQwNjc2MTMsInQiOjE2OTcxMzEwNTN9--2fc1f687d2c920edf1691202e2659c5786aa8c8ba454cfc7fda35e8f048545ec" data-refresh-url="/_alive" data-session-id="56073fd770b4a139a47820b7d307e41314d47ba86f52e9538796a795f6a86dc4">
      <link rel="shared-web-socket-src" href="/assets-cdn/worker/socket-worker-cee473359cfe.js">


        <meta name="hostname" content="github.com">


      <meta name="keyboard-shortcuts-preference" content="all">

        <meta name="expected-hostname" content="github.com">


  <meta http-equiv="x-pjax-version" content="2f5237bd11e4bd600c12e3b20916f3e0e822816cd3823ad6c4e945dcca05beca" data-turbo-track="reload">
  <meta http-equiv="x-pjax-csp-version" content="ee14a7165914197d62e19f664bfb961fcfdfc1ec31939a5c7b137fbab1751c87" data-turbo-track="reload">
  <meta http-equiv="x-pjax-css-version" content="9595620dadca1d298901f86485af2a446cfcf0446aa8aba556c30f01efc25ab9" data-turbo-track="reload">
  <meta http-equiv="x-pjax-js-version" content="b8147cb12df87655ea0f96e6fdec4cc353ec97981272c3df3394242d29e03db6" data-turbo-track="reload">

  <meta name="turbo-cache-control" content="no-preview" data-turbo-transient="">

      <meta name="turbo-cache-control" content="no-cache" data-turbo-transient>
    <meta data-hydrostats="publish">

  <meta name="go-import" content="github.com/home-assistant/core git https://github.com/home-assistant/core.git">

  <meta name="octolytics-dimension-user_id" content="13844975" /><meta name="octolytics-dimension-user_login" content="home-assistant" /><meta name="octolytics-dimension-repository_id" content="12888993" /><meta name="octolytics-dimension-repository_nwo" content="home-assistant/core" /><meta name="octolytics-dimension-repository_public" content="true" /><meta name="octolytics-dimension-repository_is_fork" content="false" /><meta name="octolytics-dimension-repository_network_root_id" content="12888993" /><meta name="octolytics-dimension-repository_network_root_nwo" content="home-assistant/core" />



  <meta name="turbo-body-classes" content="logged-in env-production page-responsive">


  <meta name="browser-stats-url" content="https://api.github.com/_private/browser/stats">

  <meta name="browser-errors-url" content="https://api.github.com/_private/browser/errors">

  <meta name="browser-optimizely-client-errors-url" content="https://api.github.com/_private/browser/optimizely_client/errors">

  <link rel="mask-icon" href="https://github.githubassets.com/pinned-octocat.svg" color="#000000">
  <link rel="alternate icon" class="js-site-favicon" type="image/png" href="https://github.githubassets.com/favicons/favicon.png">
  <link rel="icon" class="js-site-favicon" type="image/svg+xml" href="https://github.githubassets.com/favicons/favicon.svg">

<meta name="theme-color" content="#1e2327">
<meta name="color-scheme" content="light dark" />


  <link rel="manifest" href="/manifest.json" crossOrigin="use-credentials">

  </head>

  <body class="logged-in env-production page-responsive" style="word-wrap: break-word;">
    <div data-turbo-body class="logged-in env-production page-responsive" style="word-wrap: break-word;">
      


    <div class="position-relative js-header-wrapper ">
      <a href="#start-of-content" class="p-3 color-bg-accent-emphasis color-fg-on-emphasis show-on-focus js-skip-to-content">Skip to content</a>
      <span data-view-component="true" class="progress-pjax-loader Progress position-fixed width-full">
    <span style="width: 0%;" data-view-component="true" class="Progress-item progress-pjax-loader-bar left-0 top-0 color-bg-accent-emphasis"></span>
</span>      
      


      

        <script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_allex_crc32_lib_crc32_esm_js-node_modules_github_mini-throttle_dist_deco-b38cad-fb30c470f64b.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/vendors-node_modules_github_clipboard-copy-element_dist_index_esm_js-node_modules_delegated-e-b37f7d-4db36910a4bc.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/app_assets_modules_github_command-palette_items_help-item_ts-app_assets_modules_github_comman-48ad9d-00e5140a09e8.js"></script>
<script crossorigin="anonymous" defer="defer" type="application/javascript" src="https://github.githubassets.com/assets/command-palette-46bb1d1be80b.js"></script>

            <header class="AppHeader">
    

    <div class="AppHeader-globalBar pb-2 js-global-bar">
      <div class="AppHeader-globalBar-start">
          <deferred-side-panel data-url="/_side-panels/global">
  <include-fragment data-target="deferred-side-panel.fragment">
      
  <button aria-label="Open global navigation menu" data-action="click:deferred-side-panel#loadPanel click:deferred-side-panel#panelOpened" data-show-dialog-id="dialog-714d37e6-11e8-47b9-b9ab-208b4db37a08" id="dialog-show-dialog-714d37e6-11e8-47b9-b9ab-208b4db37a08" type="button" data-view-component="true" class="Button Button--iconOnly Button--secondary Button--medium AppHeader-button color-bg-transparent p-0 color-fg-muted">    <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-three-bars Button-visual">
    <path d="M1 2.75A.75.75 0 0 1 1.75 2h12.5a.75.75 0 0 1 0 1.5H1.75A.75.75 0 0 1 1 2.75Zm0 5A.75.75 0 0 1 1.75 7h12.5a.75.75 0 0 1 0 1.5H1.75A.75.75 0 0 1 1 7.75ZM1.75 12h12.5a.75.75 0 0 1 0 1.5H1.75a.75.75 0 0 1 0-1.5Z"></path>
</svg>
</button>  

<div class="Overlay--hidden Overlay-backdrop--side Overlay-backdrop--placement-left" data-modal-dialog-overlay>
  <modal-dialog data-target="deferred-side-panel.panel" role="dialog" id="dialog-714d37e6-11e8-47b9-b9ab-208b4db37a08" aria-modal="true" aria-disabled="true" aria-labelledby="dialog-714d37e6-11e8-47b9-b9ab-208b4db37a08-title" aria-describedby="dialog-714d37e6-11e8-47b9-b9ab-208b4db37a08-description" data-view-component="true" class="Overlay Overlay-whenNarrow Overlay--size-small-portrait Overlay--motion-scaleFade SidePanel">
    <div styles="flex-direction: row;" data-view-component="true" class="Overlay-header">
  <div class="Overlay-headerContentWrap">
    <div class="Overlay-titleWrap">
      <h1 class="Overlay-title sr-only" id="dialog-714d37e6-11e8-47b9-b9ab-208b4db37a08-title">
        Global navigation
      </h1>
            <div data-view-component="true" class="d-flex">
      <div data-view-component="true" class="AppHeader-logo position-relative">
        <svg aria-hidden="true" height="24" viewBox="0 0 16 16" version="1.1" width="24" data-view-component="true" class="octicon octicon-mark-github">
    <path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"></path>
</svg>
</div></div>
    </div>
    <div class="Overlay-actionWrap">
      <button data-close-dialog-id="dialog-714d37e6-11e8-47b9-b9ab-208b4db37a08" aria-label="Close" type="button" data-view-component="true" class="close-button Overlay-closeButton"><svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-x">
    <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.749.749 0 0 1 1.275.326.749.749 0 0 1-.215.734L9.06 8l3.22 3.22a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L8 9.06l-3.22 3.22a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"></path>
</svg></button>
    </div>
  </div>
</div>
      <div data-view-component="true" class="Overlay-body d-flex flex-column height-full px-2">      <nav aria-label="Site navigation" data-view-component="true" class="ActionList">
  
  <nav-list>
    <ul data-view-component="true" class="ActionListWrap">
        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-hotkey="g d" data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;HOME&quot;,&quot;label&quot;:null}" id="item-e2c6dcf5-e0a5-448b-8895-a82f3225c57c" href="/dashboard" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-home">
    <path d="M6.906.664a1.749 1.749 0 0 1 2.187 0l5.25 4.2c.415.332.657.835.657 1.367v7.019A1.75 1.75 0 0 1 13.25 15h-3.5a.75.75 0 0 1-.75-.75V9H7v5.25a.75.75 0 0 1-.75.75h-3.5A1.75 1.75 0 0 1 1 13.25V6.23c0-.531.242-1.034.657-1.366l5.25-4.2Zm1.25 1.171a.25.25 0 0 0-.312 0l-5.25 4.2a.25.25 0 0 0-.094.196v7.019c0 .138.112.25.25.25H5.5V8.25a.75.75 0 0 1 .75-.75h3.5a.75.75 0 0 1 .75.75v5.25h2.75a.25.25 0 0 0 .25-.25V6.23a.25.25 0 0 0-.094-.195Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          Home
</span></a>
  
  
</li>

        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-hotkey="g i" data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;ISSUES&quot;,&quot;label&quot;:null}" id="item-9ded7c33-add9-4bfc-8e2e-f44a54fea1d5" href="/issues" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-issue-opened">
    <path d="M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          Issues
</span></a>
  
  
</li>

        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-hotkey="g p" data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;PULL_REQUESTS&quot;,&quot;label&quot;:null}" id="item-8826d47f-e7df-408c-b983-3b35359b958e" href="/pulls" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-git-pull-request">
    <path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          Pull requests
</span></a>
  
  
</li>

        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;DISCUSSIONS&quot;,&quot;label&quot;:null}" id="item-42e297b7-5e72-4af2-a90c-b4f62c21f381" href="/discussions" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-comment-discussion">
    <path d="M1.75 1h8.5c.966 0 1.75.784 1.75 1.75v5.5A1.75 1.75 0 0 1 10.25 10H7.061l-2.574 2.573A1.458 1.458 0 0 1 2 11.543V10h-.25A1.75 1.75 0 0 1 0 8.25v-5.5C0 1.784.784 1 1.75 1ZM1.5 2.75v5.5c0 .138.112.25.25.25h1a.75.75 0 0 1 .75.75v2.19l2.72-2.72a.749.749 0 0 1 .53-.22h3.5a.25.25 0 0 0 .25-.25v-5.5a.25.25 0 0 0-.25-.25h-8.5a.25.25 0 0 0-.25.25Zm13 2a.25.25 0 0 0-.25-.25h-.5a.75.75 0 0 1 0-1.5h.5c.966 0 1.75.784 1.75 1.75v5.5A1.75 1.75 0 0 1 14.25 12H14v1.543a1.458 1.458 0 0 1-2.487 1.03L9.22 12.28a.749.749 0 0 1 .326-1.275.749.749 0 0 1 .734.215l2.22 2.22v-2.19a.75.75 0 0 1 .75-.75h1a.25.25 0 0 0 .25-.25Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          Discussions
</span></a>
  
  
</li>

        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;CODESPACES&quot;,&quot;label&quot;:null}" id="item-d8d4f352-b3ab-4f5c-9094-2e56e35c08bb" href="https://github.com/codespaces" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-codespaces">
    <path d="M0 11.25c0-.966.784-1.75 1.75-1.75h12.5c.966 0 1.75.784 1.75 1.75v3A1.75 1.75 0 0 1 14.25 16H1.75A1.75 1.75 0 0 1 0 14.25Zm2-9.5C2 .784 2.784 0 3.75 0h8.5C13.216 0 14 .784 14 1.75v5a1.75 1.75 0 0 1-1.75 1.75h-8.5A1.75 1.75 0 0 1 2 6.75Zm1.75-.25a.25.25 0 0 0-.25.25v5c0 .138.112.25.25.25h8.5a.25.25 0 0 0 .25-.25v-5a.25.25 0 0 0-.25-.25Zm-2 9.5a.25.25 0 0 0-.25.25v3c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25v-3a.25.25 0 0 0-.25-.25Z"></path><path d="M7 12.75a.75.75 0 0 1 .75-.75h4.5a.75.75 0 0 1 0 1.5h-4.5a.75.75 0 0 1-.75-.75Zm-4 0a.75.75 0 0 1 .75-.75h.5a.75.75 0 0 1 0 1.5h-.5a.75.75 0 0 1-.75-.75Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          Codespaces
</span></a>
  
  
</li>

        
          <li role="presentation" aria-hidden="true" data-view-component="true" class="ActionList-sectionDivider"></li>
        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;EXPLORE&quot;,&quot;label&quot;:null}" id="item-6c759a12-d180-42c6-ad82-deec015c4002" href="/explore" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-telescope">
    <path d="M14.184 1.143v-.001l1.422 2.464a1.75 1.75 0 0 1-.757 2.451L3.104 11.713a1.75 1.75 0 0 1-2.275-.702l-.447-.775a1.75 1.75 0 0 1 .53-2.32L11.682.573a1.748 1.748 0 0 1 2.502.57Zm-4.709 9.32h-.001l2.644 3.863a.75.75 0 1 1-1.238.848l-1.881-2.75v2.826a.75.75 0 0 1-1.5 0v-2.826l-1.881 2.75a.75.75 0 1 1-1.238-.848l2.049-2.992a.746.746 0 0 1 .293-.253l1.809-.87a.749.749 0 0 1 .944.252ZM9.436 3.92h-.001l-4.97 3.39.942 1.63 5.42-2.61Zm3.091-2.108h.001l-1.85 1.26 1.505 2.605 2.016-.97a.247.247 0 0 0 .13-.151.247.247 0 0 0-.022-.199l-1.422-2.464a.253.253 0 0 0-.161-.119.254.254 0 0 0-.197.038ZM1.756 9.157a.25.25 0 0 0-.075.33l.447.775a.25.25 0 0 0 .325.1l1.598-.769-.83-1.436-1.465 1Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          Explore
</span></a>
  
  
</li>

        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;MARKETPLACE&quot;,&quot;label&quot;:null}" id="item-79ca488a-2e06-4efe-8b7b-6264d4dd68ca" href="/marketplace" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-gift">
    <path d="M2 2.75A2.75 2.75 0 0 1 4.75 0c.983 0 1.873.42 2.57 1.232.268.318.497.668.68 1.042.183-.375.411-.725.68-1.044C9.376.42 10.266 0 11.25 0a2.75 2.75 0 0 1 2.45 4h.55c.966 0 1.75.784 1.75 1.75v2c0 .698-.409 1.301-1 1.582v4.918A1.75 1.75 0 0 1 13.25 16H2.75A1.75 1.75 0 0 1 1 14.25V9.332C.409 9.05 0 8.448 0 7.75v-2C0 4.784.784 4 1.75 4h.55c-.192-.375-.3-.8-.3-1.25ZM7.25 9.5H2.5v4.75c0 .138.112.25.25.25h4.5Zm1.5 0v5h4.5a.25.25 0 0 0 .25-.25V9.5Zm0-4V8h5.5a.25.25 0 0 0 .25-.25v-2a.25.25 0 0 0-.25-.25Zm-7 0a.25.25 0 0 0-.25.25v2c0 .138.112.25.25.25h5.5V5.5h-5.5Zm3-4a1.25 1.25 0 0 0 0 2.5h2.309c-.233-.818-.542-1.401-.878-1.793-.43-.502-.915-.707-1.431-.707ZM8.941 4h2.309a1.25 1.25 0 0 0 0-2.5c-.516 0-1 .205-1.43.707-.337.392-.646.975-.879 1.793Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          Marketplace
</span></a>
  
  
</li>

</ul>  </nav-list>
</nav>

      <div data-view-component="true" class="my-3 d-flex flex-justify-center height-full">
        <svg style="box-sizing: content-box; color: var(--color-icon-primary);" width="16" height="16" viewBox="0 0 16 16" fill="none" data-view-component="true" class="anim-rotate">
  <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-opacity="0.25" stroke-width="2" vector-effect="non-scaling-stroke" fill="none" />
  <path d="M15 8a7.002 7.002 0 00-7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" vector-effect="non-scaling-stroke" />
</svg>
</div>
</div>
      <div data-view-component="true" class="Overlay-footer Overlay-footer--alignEnd d-block pt-0">      <li role="presentation" aria-hidden="true" data-view-component="true" class="ActionList-sectionDivider mt-0 mb-1"></li>

        <nav aria-label="Additional navigation" data-view-component="true" class="ActionList px-0 flex-1">
  
  <nav-list>
    <ul data-view-component="true" class="ActionListWrap">
        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;FEEDBACK&quot;,&quot;label&quot;:null}" id="item-9457c805-0207-408c-9059-578c52a8f49e" href="https://gh.io/navigation-update" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-comment-discussion">
    <path d="M1.75 1h8.5c.966 0 1.75.784 1.75 1.75v5.5A1.75 1.75 0 0 1 10.25 10H7.061l-2.574 2.573A1.458 1.458 0 0 1 2 11.543V10h-.25A1.75 1.75 0 0 1 0 8.25v-5.5C0 1.784.784 1 1.75 1ZM1.5 2.75v5.5c0 .138.112.25.25.25h1a.75.75 0 0 1 .75.75v2.19l2.72-2.72a.749.749 0 0 1 .53-.22h3.5a.25.25 0 0 0 .25-.25v-5.5a.25.25 0 0 0-.25-.25h-8.5a.25.25 0 0 0-.25.25Zm13 2a.25.25 0 0 0-.25-.25h-.5a.75.75 0 0 1 0-1.5h.5c.966 0 1.75.784 1.75 1.75v5.5A1.75 1.75 0 0 1 14.25 12H14v1.543a1.458 1.458 0 0 1-2.487 1.03L9.22 12.28a.749.749 0 0 1 .326-1.275.749.749 0 0 1 .734.215l2.22 2.22v-2.19a.75.75 0 0 1 .75-.75h1a.25.25 0 0 0 .25-.25Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          Give new navigation feedback
</span>        <span class="ActionListItem-visual ActionListItem-visual--trailing">
          <span title="Beta" data-view-component="true" class="Counter color-bg-default color-border-success-emphasis color-fg-success">Beta</span>
        </span>
</a>
  
  
</li>

</ul>  </nav-list>
</nav>

      <div data-view-component="true" class="px-2">      <p class="color-fg-subtle text-small text-light">&copy; 2023 GitHub, Inc.</p>

      <div data-view-component="true" class="d-flex text-small text-light">
          <a target="_blank" href="/about" data-view-component="true" class="Link mr-2">About</a>
          <a target="_blank" href="https://github.blog" data-view-component="true" class="Link mr-2">Blog</a>
          <a target="_blank" href="https://docs.github.com/site-policy/github-terms/github-terms-of-service" data-view-component="true" class="Link mr-2">Terms</a>
          <a target="_blank" href="https://docs.github.com/site-policy/privacy-policies/github-privacy-statement" data-view-component="true" class="Link mr-2">Privacy</a>
          <a target="_blank" href="/security" data-view-component="true" class="Link mr-2">Security</a>
        <a target="_blank" href="https://www.githubstatus.com/" data-view-component="true" class="Link mr-3">Status</a>
</div></div>
</div>
</modal-dialog></div>

  </include-fragment>
</deferred-side-panel>

        <a
          class="AppHeader-logo ml-2"
          href="https://github.com/"
          data-hotkey="g d"
          aria-label="Homepage "
          data-turbo="false"
          data-analytics-event="{&quot;category&quot;:&quot;Header&quot;,&quot;action&quot;:&quot;go to dashboard&quot;,&quot;label&quot;:&quot;icon:logo&quot;}"
        >
          <svg height="32" aria-hidden="true" viewBox="0 0 16 16" version="1.1" width="32" data-view-component="true" class="octicon octicon-mark-github v-align-middle color-fg-default">
    <path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"></path>
</svg>
        </a>

          <div class="AppHeader-context" >
  <div class="AppHeader-context-compact">
        <button aria-expanded="false" aria-haspopup="dialog" aria-label="Page context: home-assistant / core" id="dialog-show-context-region-dialog" data-show-dialog-id="context-region-dialog" type="button" data-view-component="true" class="AppHeader-context-compact-trigger Truncate Button--secondary Button--medium Button box-shadow-none">    <span class="Button-content">
      <span class="Button-label"><span class="AppHeader-context-compact-lead">
                <span class="AppHeader-context-compact-parentItem">home-assistant</span>
                <span class="AppHeader-context-compact-separator">&nbsp;/</span>

            </span>

            <strong class="AppHeader-context-compact-mainItem d-flex flex-items-center Truncate" >
  <span class="Truncate-text ">core</span>

</strong></span>
    </span>
</button>  

<div class="Overlay--hidden Overlay-backdrop--center" data-modal-dialog-overlay>
  <modal-dialog role="dialog" id="context-region-dialog" aria-modal="true" aria-disabled="true" aria-labelledby="context-region-dialog-title" aria-describedby="context-region-dialog-description" data-view-component="true" class="Overlay Overlay-whenNarrow Overlay--size-medium Overlay--motion-scaleFade">
    <div data-view-component="true" class="Overlay-header">
  <div class="Overlay-headerContentWrap">
    <div class="Overlay-titleWrap">
      <h1 class="Overlay-title " id="context-region-dialog-title">
        Navigate back to
      </h1>
    </div>
    <div class="Overlay-actionWrap">
      <button data-close-dialog-id="context-region-dialog" aria-label="Close" type="button" data-view-component="true" class="close-button Overlay-closeButton"><svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-x">
    <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.749.749 0 0 1 1.275.326.749.749 0 0 1-.215.734L9.06 8l3.22 3.22a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L8 9.06l-3.22 3.22a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"></path>
</svg></button>
    </div>
  </div>
</div>
      <div data-view-component="true" class="Overlay-body">          <ul role="list" class="list-style-none" >
    <li>
      <a data-analytics-event="{&quot;category&quot;:&quot;SiteHeaderComponent&quot;,&quot;action&quot;:&quot;context_region_crumb&quot;,&quot;label&quot;:&quot;home-assistant&quot;,&quot;screen_size&quot;:&quot;compact&quot;}" href="/home-assistant" data-view-component="true" class="Link--primary Truncate d-flex flex-items-center py-1">
        <span class="AppHeader-context-item-label Truncate-text ">
            <svg aria-hidden="true" height="12" viewBox="0 0 16 16" version="1.1" width="12" data-view-component="true" class="octicon octicon-organization mr-1">
    <path d="M1.75 16A1.75 1.75 0 0 1 0 14.25V1.75C0 .784.784 0 1.75 0h8.5C11.216 0 12 .784 12 1.75v12.5c0 .085-.006.168-.018.25h2.268a.25.25 0 0 0 .25-.25V8.285a.25.25 0 0 0-.111-.208l-1.055-.703a.749.749 0 1 1 .832-1.248l1.055.703c.487.325.779.871.779 1.456v5.965A1.75 1.75 0 0 1 14.25 16h-3.5a.766.766 0 0 1-.197-.026c-.099.017-.2.026-.303.026h-3a.75.75 0 0 1-.75-.75V14h-1v1.25a.75.75 0 0 1-.75.75Zm-.25-1.75c0 .138.112.25.25.25H4v-1.25a.75.75 0 0 1 .75-.75h2.5a.75.75 0 0 1 .75.75v1.25h2.25a.25.25 0 0 0 .25-.25V1.75a.25.25 0 0 0-.25-.25h-8.5a.25.25 0 0 0-.25.25ZM3.75 6h.5a.75.75 0 0 1 0 1.5h-.5a.75.75 0 0 1 0-1.5ZM3 3.75A.75.75 0 0 1 3.75 3h.5a.75.75 0 0 1 0 1.5h-.5A.75.75 0 0 1 3 3.75Zm4 3A.75.75 0 0 1 7.75 6h.5a.75.75 0 0 1 0 1.5h-.5A.75.75 0 0 1 7 6.75ZM7.75 3h.5a.75.75 0 0 1 0 1.5h-.5a.75.75 0 0 1 0-1.5ZM3 9.75A.75.75 0 0 1 3.75 9h.5a.75.75 0 0 1 0 1.5h-.5A.75.75 0 0 1 3 9.75ZM7.75 9h.5a.75.75 0 0 1 0 1.5h-.5a.75.75 0 0 1 0-1.5Z"></path>
</svg>

          home-assistant
        </span>

</a>
    </li>
    <li>
      <a data-analytics-event="{&quot;category&quot;:&quot;SiteHeaderComponent&quot;,&quot;action&quot;:&quot;context_region_crumb&quot;,&quot;label&quot;:&quot;core&quot;,&quot;screen_size&quot;:&quot;compact&quot;}" href="/home-assistant/core" data-view-component="true" class="Link--primary Truncate d-flex flex-items-center py-1">
        <span class="AppHeader-context-item-label Truncate-text ">
            <svg aria-hidden="true" height="12" viewBox="0 0 16 16" version="1.1" width="12" data-view-component="true" class="octicon octicon-repo mr-1">
    <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"></path>
</svg>

          core
        </span>

</a>
    </li>
</ul>

</div>
      
</modal-dialog></div>
  </div>

  <div class="AppHeader-context-full">
    <nav role="navigation" aria-label="Page context">
      <ul role="list" class="list-style-none" >
    <li>
      <a data-analytics-event="{&quot;category&quot;:&quot;SiteHeaderComponent&quot;,&quot;action&quot;:&quot;context_region_crumb&quot;,&quot;label&quot;:&quot;home-assistant&quot;,&quot;screen_size&quot;:&quot;full&quot;}" data-hovercard-type="organization" data-hovercard-url="/orgs/home-assistant/hovercard" data-octo-click="hovercard-link-click" data-octo-dimensions="link_type:self" href="/home-assistant" data-view-component="true" class="AppHeader-context-item">
        <span class="AppHeader-context-item-label  ">

          home-assistant
        </span>

</a>
        <span class="AppHeader-context-item-separator">/</span>
    </li>
    <li>
      <a data-analytics-event="{&quot;category&quot;:&quot;SiteHeaderComponent&quot;,&quot;action&quot;:&quot;context_region_crumb&quot;,&quot;label&quot;:&quot;core&quot;,&quot;screen_size&quot;:&quot;full&quot;}" href="/home-assistant/core" data-view-component="true" class="AppHeader-context-item">
        <span class="AppHeader-context-item-label  ">

          core
        </span>

</a>
    </li>
</ul>

    </nav>
  </div>
</div>

      </div>
      <div class="AppHeader-globalBar-end">
          <div class="AppHeader-search" >
              


<qbsearch-input class="search-input" data-scope="repo:home-assistant/core" data-custom-scopes-path="/search/custom_scopes" data-delete-custom-scopes-csrf="-Ki2V1271huQ28r0rAuObLkRyjkAdFPZ6uLWtM559Ql030FeLRlwuthv-_sDLU11D5HBTRniowymps3fZHlIUA" data-max-custom-scopes="10" data-header-redesign-enabled="true" data-initial-value="" data-blackbird-suggestions-path="/search/suggestions" data-jump-to-suggestions-path="/_graphql/GetSuggestedNavigationDestinations" data-current-repository="home-assistant/core" data-current-org="home-assistant" data-current-owner="" data-logged-in="true">
  <div
    class="search-input-container search-with-dialog position-relative d-flex flex-row flex-items-center height-auto color-bg-transparent border-0 color-fg-subtle mx-0"
    data-action="click:qbsearch-input#searchInputContainerClicked"
  >
      
            <button type="button" data-action="click:qbsearch-input#handleExpand" class="AppHeader-button AppHeader-search-whenNarrow" aria-label="Search or jump to…" aria-expanded="false" aria-haspopup="dialog">
            <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-search">
    <path d="M10.68 11.74a6 6 0 0 1-7.922-8.982 6 6 0 0 1 8.982 7.922l3.04 3.04a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215ZM11.5 7a4.499 4.499 0 1 0-8.997 0A4.499 4.499 0 0 0 11.5 7Z"></path>
</svg>
          </button>


<div class="AppHeader-search-whenRegular">
  <div class="AppHeader-search-wrap AppHeader-search-wrap--hasTrailing">
    <div class="AppHeader-search-control">
      <label
        for="AppHeader-searchInput"
        aria-label="Search or jump to…"
        class="AppHeader-search-visual--leading"
      >
        <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-search">
    <path d="M10.68 11.74a6 6 0 0 1-7.922-8.982 6 6 0 0 1 8.982 7.922l3.04 3.04a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215ZM11.5 7a4.499 4.499 0 1 0-8.997 0A4.499 4.499 0 0 0 11.5 7Z"></path>
</svg>
      </label>

                <button
            type="button"
            data-target="qbsearch-input.inputButton"
            data-action="click:qbsearch-input#handleExpand"
            class="AppHeader-searchButton form-control input-contrast text-left color-fg-subtle no-wrap"
            data-hotkey="s,/"
            data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;SEARCH&quot;,&quot;label&quot;:null}"
          >
            <div class="overflow-hidden">
              <span id="qb-input-query" data-target="qbsearch-input.inputButtonText">
                  Type <kbd class="AppHeader-search-kbd">/</kbd> to search
              </span>
            </div>
          </button>

    </div>


      <button type="button" id="AppHeader-commandPalette-button" class="AppHeader-search-action--trailing js-activate-command-palette" data-analytics-event="{&quot;category&quot;:&quot;SiteHeaderComponent&quot;,&quot;action&quot;:&quot;command_palette&quot;,&quot;label&quot;:&quot;open command palette&quot;}">
        <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-command-palette">
    <path d="m6.354 8.04-4.773 4.773a.75.75 0 1 0 1.061 1.06L7.945 8.57a.75.75 0 0 0 0-1.06L2.642 2.206a.75.75 0 0 0-1.06 1.061L6.353 8.04ZM8.75 11.5a.75.75 0 0 0 0 1.5h5.5a.75.75 0 0 0 0-1.5h-5.5Z"></path>
</svg>
      </button>

      <tool-tip id="tooltip-26be27df-5518-44a9-beb4-6bc33a5ab0ec" for="AppHeader-commandPalette-button" popover="manual" data-direction="s" data-type="label" data-view-component="true" class="sr-only position-absolute">Command palette</tool-tip>
  </div>
</div>

    <input type="hidden" name="type" class="js-site-search-type-field">

    
<div class="Overlay--hidden " data-modal-dialog-overlay>
  <modal-dialog data-action="close:qbsearch-input#handleClose cancel:qbsearch-input#handleClose" data-target="qbsearch-input.searchSuggestionsDialog" role="dialog" id="search-suggestions-dialog" aria-modal="true" aria-labelledby="search-suggestions-dialog-header" data-view-component="true" class="Overlay Overlay--width-medium Overlay--height-auto">
      <h1 id="search-suggestions-dialog-header" class="sr-only">Search code, repositories, users, issues, pull requests...</h1>
    <div class="Overlay-body Overlay-body--paddingNone">
      
          <div data-view-component="true">        <div class="search-suggestions position-absolute width-full color-shadow-large border color-fg-default color-bg-default overflow-hidden d-flex flex-column query-builder-container"
          style="border-radius: 12px;"
          data-target="qbsearch-input.queryBuilderContainer"
          hidden
        >
          <!-- '"` --><!-- </textarea></xmp> --></option></form><form id="query-builder-test-form" action="" accept-charset="UTF-8" method="get">
  <query-builder data-target="qbsearch-input.queryBuilder" id="query-builder-query-builder-test" data-filter-key=":" data-view-component="true" class="QueryBuilder search-query-builder">
    <div class="FormControl FormControl--fullWidth">
      <label id="query-builder-test-label" for="query-builder-test" class="FormControl-label sr-only">
        Search
      </label>
      <div
        class="QueryBuilder-StyledInput width-fit "
        data-target="query-builder.styledInput"
      >
          <span id="query-builder-test-leadingvisual-wrap" class="FormControl-input-leadingVisualWrap QueryBuilder-leadingVisualWrap">
            <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-search FormControl-input-leadingVisual">
    <path d="M10.68 11.74a6 6 0 0 1-7.922-8.982 6 6 0 0 1 8.982 7.922l3.04 3.04a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215ZM11.5 7a4.499 4.499 0 1 0-8.997 0A4.499 4.499 0 0 0 11.5 7Z"></path>
</svg>
          </span>
        <div data-target="query-builder.styledInputContainer" class="QueryBuilder-StyledInputContainer">
          <div
            aria-hidden="true"
            class="QueryBuilder-StyledInputContent"
            data-target="query-builder.styledInputContent"
          ></div>
          <div class="QueryBuilder-InputWrapper">
            <div aria-hidden="true" class="QueryBuilder-Sizer" data-target="query-builder.sizer"></div>
            <input id="query-builder-test" name="query-builder-test" value="" autocomplete="off" type="text" role="combobox" spellcheck="false" aria-expanded="false" aria-describedby="validation-5f24ea0e-9822-480e-b857-ff866a2f25b8" data-target="query-builder.input" data-action="
          input:query-builder#inputChange
          blur:query-builder#inputBlur
          keydown:query-builder#inputKeydown
          focus:query-builder#inputFocus
        " data-view-component="true" class="FormControl-input QueryBuilder-Input FormControl-medium" />
          </div>
        </div>
          <span class="sr-only" id="query-builder-test-clear">Clear</span>
          
  <button role="button" id="query-builder-test-clear-button" aria-labelledby="query-builder-test-clear query-builder-test-label" data-target="query-builder.clearButton" data-action="
                click:query-builder#clear
                focus:query-builder#clearButtonFocus
                blur:query-builder#clearButtonBlur
              " variant="small" hidden="hidden" type="button" data-view-component="true" class="Button Button--iconOnly Button--invisible Button--medium mr-1 px-2 py-0 d-flex flex-items-center rounded-1 color-fg-muted">    <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-x-circle-fill Button-visual">
    <path d="M2.343 13.657A8 8 0 1 1 13.658 2.343 8 8 0 0 1 2.343 13.657ZM6.03 4.97a.751.751 0 0 0-1.042.018.751.751 0 0 0-.018 1.042L6.94 8 4.97 9.97a.749.749 0 0 0 .326 1.275.749.749 0 0 0 .734-.215L8 9.06l1.97 1.97a.749.749 0 0 0 1.275-.326.749.749 0 0 0-.215-.734L9.06 8l1.97-1.97a.749.749 0 0 0-.326-1.275.749.749 0 0 0-.734.215L8 6.94Z"></path>
</svg>
</button>  

      </div>
      <template id="search-icon">
  <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-search">
    <path d="M10.68 11.74a6 6 0 0 1-7.922-8.982 6 6 0 0 1 8.982 7.922l3.04 3.04a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215ZM11.5 7a4.499 4.499 0 1 0-8.997 0A4.499 4.499 0 0 0 11.5 7Z"></path>
</svg>
</template>

<template id="code-icon">
  <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-code">
    <path d="m11.28 3.22 4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.749.749 0 0 1-1.275-.326.749.749 0 0 1 .215-.734L13.94 8l-3.72-3.72a.749.749 0 0 1 .326-1.275.749.749 0 0 1 .734.215Zm-6.56 0a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042L2.06 8l3.72 3.72a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L.47 8.53a.75.75 0 0 1 0-1.06Z"></path>
</svg>
</template>

<template id="file-code-icon">
  <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-file-code">
    <path d="M4 1.75C4 .784 4.784 0 5.75 0h5.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v8.586A1.75 1.75 0 0 1 14.25 15h-9a.75.75 0 0 1 0-1.5h9a.25.25 0 0 0 .25-.25V6h-2.75A1.75 1.75 0 0 1 10 4.25V1.5H5.75a.25.25 0 0 0-.25.25v2.5a.75.75 0 0 1-1.5 0Zm1.72 4.97a.75.75 0 0 1 1.06 0l2 2a.75.75 0 0 1 0 1.06l-2 2a.749.749 0 0 1-1.275-.326.749.749 0 0 1 .215-.734l1.47-1.47-1.47-1.47a.75.75 0 0 1 0-1.06ZM3.28 7.78 1.81 9.25l1.47 1.47a.751.751 0 0 1-.018 1.042.751.751 0 0 1-1.042.018l-2-2a.75.75 0 0 1 0-1.06l2-2a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042Zm8.22-6.218V4.25c0 .138.112.25.25.25h2.688l-.011-.013-2.914-2.914-.013-.011Z"></path>
</svg>
</template>

<template id="history-icon">
  <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-history">
    <path d="m.427 1.927 1.215 1.215a8.002 8.002 0 1 1-1.6 5.685.75.75 0 1 1 1.493-.154 6.5 6.5 0 1 0 1.18-4.458l1.358 1.358A.25.25 0 0 1 3.896 6H.25A.25.25 0 0 1 0 5.75V2.104a.25.25 0 0 1 .427-.177ZM7.75 4a.75.75 0 0 1 .75.75v2.992l2.028.812a.75.75 0 0 1-.557 1.392l-2.5-1A.751.751 0 0 1 7 8.25v-3.5A.75.75 0 0 1 7.75 4Z"></path>
</svg>
</template>

<template id="repo-icon">
  <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-repo">
    <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"></path>
</svg>
</template>

<template id="bookmark-icon">
  <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-bookmark">
    <path d="M3 2.75C3 1.784 3.784 1 4.75 1h6.5c.966 0 1.75.784 1.75 1.75v11.5a.75.75 0 0 1-1.227.579L8 11.722l-3.773 3.107A.751.751 0 0 1 3 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v9.91l3.023-2.489a.75.75 0 0 1 .954 0l3.023 2.49V2.75a.25.25 0 0 0-.25-.25Z"></path>
</svg>
</template>

<template id="plus-circle-icon">
  <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-plus-circle">
    <path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Zm7.25-3.25v2.5h2.5a.75.75 0 0 1 0 1.5h-2.5v2.5a.75.75 0 0 1-1.5 0v-2.5h-2.5a.75.75 0 0 1 0-1.5h2.5v-2.5a.75.75 0 0 1 1.5 0Z"></path>
</svg>
</template>

<template id="circle-icon">
  <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-dot-fill">
    <path d="M8 4a4 4 0 1 1 0 8 4 4 0 0 1 0-8Z"></path>
</svg>
</template>

<template id="trash-icon">
  <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-trash">
    <path d="M11 1.75V3h2.25a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1 0-1.5H5V1.75C5 .784 5.784 0 6.75 0h2.5C10.216 0 11 .784 11 1.75ZM4.496 6.675l.66 6.6a.25.25 0 0 0 .249.225h5.19a.25.25 0 0 0 .249-.225l.66-6.6a.75.75 0 0 1 1.492.149l-.66 6.6A1.748 1.748 0 0 1 10.595 15h-5.19a1.75 1.75 0 0 1-1.741-1.575l-.66-6.6a.75.75 0 1 1 1.492-.15ZM6.5 1.75V3h3V1.75a.25.25 0 0 0-.25-.25h-2.5a.25.25 0 0 0-.25.25Z"></path>
</svg>
</template>

<template id="team-icon">
  <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-people">
    <path d="M2 5.5a3.5 3.5 0 1 1 5.898 2.549 5.508 5.508 0 0 1 3.034 4.084.75.75 0 1 1-1.482.235 4 4 0 0 0-7.9 0 .75.75 0 0 1-1.482-.236A5.507 5.507 0 0 1 3.102 8.05 3.493 3.493 0 0 1 2 5.5ZM11 4a3.001 3.001 0 0 1 2.22 5.018 5.01 5.01 0 0 1 2.56 3.012.749.749 0 0 1-.885.954.752.752 0 0 1-.549-.514 3.507 3.507 0 0 0-2.522-2.372.75.75 0 0 1-.574-.73v-.352a.75.75 0 0 1 .416-.672A1.5 1.5 0 0 0 11 5.5.75.75 0 0 1 11 4Zm-5.5-.5a2 2 0 1 0-.001 3.999A2 2 0 0 0 5.5 3.5Z"></path>
</svg>
</template>

<template id="project-icon">
  <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-project">
    <path d="M1.75 0h12.5C15.216 0 16 .784 16 1.75v12.5A1.75 1.75 0 0 1 14.25 16H1.75A1.75 1.75 0 0 1 0 14.25V1.75C0 .784.784 0 1.75 0ZM1.5 1.75v12.5c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25V1.75a.25.25 0 0 0-.25-.25H1.75a.25.25 0 0 0-.25.25ZM11.75 3a.75.75 0 0 1 .75.75v7.5a.75.75 0 0 1-1.5 0v-7.5a.75.75 0 0 1 .75-.75Zm-8.25.75a.75.75 0 0 1 1.5 0v5.5a.75.75 0 0 1-1.5 0ZM8 3a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 8 3Z"></path>
</svg>
</template>

<template id="pencil-icon">
  <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-pencil">
    <path d="M11.013 1.427a1.75 1.75 0 0 1 2.474 0l1.086 1.086a1.75 1.75 0 0 1 0 2.474l-8.61 8.61c-.21.21-.47.364-.756.445l-3.251.93a.75.75 0 0 1-.927-.928l.929-3.25c.081-.286.235-.547.445-.758l8.61-8.61Zm.176 4.823L9.75 4.81l-6.286 6.287a.253.253 0 0 0-.064.108l-.558 1.953 1.953-.558a.253.253 0 0 0 .108-.064Zm1.238-3.763a.25.25 0 0 0-.354 0L10.811 3.75l1.439 1.44 1.263-1.263a.25.25 0 0 0 0-.354Z"></path>
</svg>
</template>

        <div class="position-relative">
                <ul
                  role="listbox"
                  class="ActionListWrap QueryBuilder-ListWrap"
                  aria-label="Suggestions"
                  data-action="
                    combobox-commit:query-builder#comboboxCommit
                    mousedown:query-builder#resultsMousedown
                  "
                  data-target="query-builder.resultsList"
                  data-persist-list=false
                  id="query-builder-test-results"
                ></ul>
        </div>
      <div class="FormControl-inlineValidation" id="validation-5f24ea0e-9822-480e-b857-ff866a2f25b8" hidden="hidden">
        <span class="FormControl-inlineValidation--visual">
          <svg aria-hidden="true" height="12" viewBox="0 0 12 12" version="1.1" width="12" data-view-component="true" class="octicon octicon-alert-fill">
    <path d="M4.855.708c.5-.896 1.79-.896 2.29 0l4.675 8.351a1.312 1.312 0 0 1-1.146 1.954H1.33A1.313 1.313 0 0 1 .183 9.058ZM7 7V3H5v4Zm-1 3a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"></path>
</svg>
        </span>
        <span></span>
</div>    </div>
    <div data-target="query-builder.screenReaderFeedback" aria-live="polite" aria-atomic="true" class="sr-only"></div>
</query-builder></form>
          <div class="d-flex flex-row color-fg-muted px-3 text-small color-bg-default search-feedback-prompt">
            <a target="_blank" href="https://docs.github.com/en/search-github/github-code-search/understanding-github-code-search-syntax" data-view-component="true" class="Link color-fg-accent text-normal ml-2">
              Search syntax tips
</a>            <div class="d-flex flex-1"></div>
                <button data-action="click:qbsearch-input#showFeedbackDialog" type="button" data-view-component="true" class="Button--link Button--medium Button color-fg-accent text-normal ml-2">    <span class="Button-content">
      <span class="Button-label">Give feedback</span>
    </span>
</button>  
          </div>
        </div>
</div>

    </div>
</modal-dialog></div>
  </div>
  <div data-action="click:qbsearch-input#retract" class="dark-backdrop position-fixed" hidden data-target="qbsearch-input.darkBackdrop"></div>
  <div class="color-fg-default">
    
<div class="Overlay--hidden Overlay-backdrop--center" data-modal-dialog-overlay>
  <modal-dialog data-target="qbsearch-input.feedbackDialog" data-action="close:qbsearch-input#handleDialogClose cancel:qbsearch-input#handleDialogClose" role="dialog" id="feedback-dialog" aria-modal="true" aria-disabled="true" aria-labelledby="feedback-dialog-title" aria-describedby="feedback-dialog-description" data-view-component="true" class="Overlay Overlay-whenNarrow Overlay--size-medium Overlay--motion-scaleFade">
    <div data-view-component="true" class="Overlay-header">
  <div class="Overlay-headerContentWrap">
    <div class="Overlay-titleWrap">
      <h1 class="Overlay-title " id="feedback-dialog-title">
        Provide feedback
      </h1>
    </div>
    <div class="Overlay-actionWrap">
      <button data-close-dialog-id="feedback-dialog" aria-label="Close" type="button" data-view-component="true" class="close-button Overlay-closeButton"><svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-x">
    <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.749.749 0 0 1 1.275.326.749.749 0 0 1-.215.734L9.06 8l3.22 3.22a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L8 9.06l-3.22 3.22a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"></path>
</svg></button>
    </div>
  </div>
</div>
      <div data-view-component="true" class="Overlay-body">        <!-- '"` --><!-- </textarea></xmp> --></option></form><form id="code-search-feedback-form" data-turbo="false" action="/search/feedback" accept-charset="UTF-8" method="post"><input type="hidden" name="authenticity_token" value="BhSovfRK1shwJuMfNo4Wv3kpwGLtrdG-3-U3jJCtCr3KOWaNjEHuYRydK55PpEqCdNDV7mAzH_a_SRepKUDy3Q" />
          <p>We read every piece of feedback, and take your input very seriously.</p>
          <textarea name="feedback" class="form-control width-full mb-2" style="height: 120px" id="feedback"></textarea>
          <input name="include_email" id="include_email" aria-label="Include my email address so I can be contacted" class="form-control mr-2" type="checkbox">
          <label for="include_email" style="font-weight: normal">Include my email address so I can be contacted</label>
</form></div>
      <div data-view-component="true" class="Overlay-footer Overlay-footer--alignEnd">          <button data-close-dialog-id="feedback-dialog" type="button" data-view-component="true" class="btn">    Cancel
</button>
          <button form="code-search-feedback-form" data-action="click:qbsearch-input#submitFeedback" type="submit" data-view-component="true" class="btn-primary btn">    Submit feedback
</button>
</div>
</modal-dialog></div>

    <custom-scopes data-target="qbsearch-input.customScopesManager">
    
<div class="Overlay--hidden Overlay-backdrop--center" data-modal-dialog-overlay>
  <modal-dialog data-target="custom-scopes.customScopesModalDialog" data-action="close:qbsearch-input#handleDialogClose cancel:qbsearch-input#handleDialogClose" role="dialog" id="custom-scopes-dialog" aria-modal="true" aria-disabled="true" aria-labelledby="custom-scopes-dialog-title" aria-describedby="custom-scopes-dialog-description" data-view-component="true" class="Overlay Overlay-whenNarrow Overlay--size-medium Overlay--motion-scaleFade">
    <div data-view-component="true" class="Overlay-header Overlay-header--divided">
  <div class="Overlay-headerContentWrap">
    <div class="Overlay-titleWrap">
      <h1 class="Overlay-title " id="custom-scopes-dialog-title">
        Saved searches
      </h1>
        <h2 id="custom-scopes-dialog-description" class="Overlay-description">Use saved searches to filter your results more quickly</h2>
    </div>
    <div class="Overlay-actionWrap">
      <button data-close-dialog-id="custom-scopes-dialog" aria-label="Close" type="button" data-view-component="true" class="close-button Overlay-closeButton"><svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-x">
    <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.749.749 0 0 1 1.275.326.749.749 0 0 1-.215.734L9.06 8l3.22 3.22a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L8 9.06l-3.22 3.22a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"></path>
</svg></button>
    </div>
  </div>
</div>
      <div data-view-component="true" class="Overlay-body">        <div data-target="custom-scopes.customScopesModalDialogFlash"></div>

        <div hidden class="create-custom-scope-form" data-target="custom-scopes.createCustomScopeForm">
        <!-- '"` --><!-- </textarea></xmp> --></option></form><form id="custom-scopes-dialog-form" data-turbo="false" action="/search/custom_scopes" accept-charset="UTF-8" method="post"><input type="hidden" name="authenticity_token" value="1FPcBafF5jP8N2Ipj5CQcdl2_t_ATHSZc0RxVPhfXdhHiqj8CWzCh_jOCwHRJr2VxLkWJVXiWzFwT4UWN3IGZw" />
          <div data-target="custom-scopes.customScopesModalDialogFlash"></div>

          <input type="hidden" id="custom_scope_id" name="custom_scope_id" data-target="custom-scopes.customScopesIdField">

          <div class="form-group">
            <label for="custom_scope_name">Name</label>
            <auto-check src="/search/custom_scopes/check_name" required>
              <input
                type="text"
                name="custom_scope_name"
                id="custom_scope_name"
                data-target="custom-scopes.customScopesNameField"
                class="form-control"
                autocomplete="off"
                placeholder="github-ruby"
                required
                maxlength="50">
              <input type="hidden" value="d8tC2JAxQOLTQNmvleFUK_pw-HNkcEWkUjLZAJYFVtpGYNCkbiae3GLpTHXT7kE9CGALHYGso8fHPOgxs7nY0w" data-csrf="true" />
            </auto-check>
          </div>

          <div class="form-group">
            <label for="custom_scope_query">Query</label>
            <input
              type="text"
              name="custom_scope_query"
              id="custom_scope_query"
              data-target="custom-scopes.customScopesQueryField"
              class="form-control"
              autocomplete="off"
              placeholder="(repo:mona/a OR repo:mona/b) AND lang:python"
              required
              maxlength="500">
          </div>

          <p class="text-small color-fg-muted">
            To see all available qualifiers, see our <a class="Link--inTextBlock" href="https://docs.github.com/en/search-github/github-code-search/understanding-github-code-search-syntax">documentation</a>.
          </p>
</form>        </div>

        <div data-target="custom-scopes.manageCustomScopesForm">
          <div data-target="custom-scopes.list"></div>
        </div>

</div>
      <div data-view-component="true" class="Overlay-footer Overlay-footer--alignEnd Overlay-footer--divided">          <button data-action="click:custom-scopes#customScopesCancel" type="button" data-view-component="true" class="btn">    Cancel
</button>
          <button form="custom-scopes-dialog-form" data-action="click:custom-scopes#customScopesSubmit" data-target="custom-scopes.customScopesSubmitButton" type="submit" data-view-component="true" class="btn-primary btn">    Create saved search
</button>
</div>
</modal-dialog></div>
    </custom-scopes>
  </div>
</qbsearch-input><input type="hidden" value="IRCgkwu_xzaWSEX1mbkemd_ZIthQJ5EIpRYODeVLsUI9P-AkByEM-w2EpwTvvXn1Sw1n9eFEk59Mgc0Mp5M5mQ" data-csrf="true" class="js-data-jump-to-suggestions-path-csrf" />

          </div>

        <div class="AppHeader-actions position-relative">
          <action-menu data-select-variant="none" data-view-component="true">
  <focus-group direction="vertical" mnemonics retain>
    <div data-view-component="true" class="Button-withTooltip">  <button id="global-create-menu-button" popovertarget="global-create-menu-overlay" aria-label="Create something new" aria-controls="global-create-menu-list" aria-haspopup="true" type="button" data-view-component="true" class="AppHeader-button Button--secondary Button--small Button width-auto color-fg-muted">    <span class="Button-content">
        <span class="Button-visual Button-leadingVisual">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-plus">
    <path d="M7.75 2a.75.75 0 0 1 .75.75V7h4.25a.75.75 0 0 1 0 1.5H8.5v4.25a.75.75 0 0 1-1.5 0V8.5H2.75a.75.75 0 0 1 0-1.5H7V2.75A.75.75 0 0 1 7.75 2Z"></path>
</svg>
        </span>
      <span class="Button-label"><svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-triangle-down">
    <path d="m4.427 7.427 3.396 3.396a.25.25 0 0 0 .354 0l3.396-3.396A.25.25 0 0 0 11.396 7H4.604a.25.25 0 0 0-.177.427Z"></path>
</svg></span>
    </span>
</button>  <tool-tip id="tooltip-32511b54-2102-48f2-a058-52526433b5dd" for="global-create-menu-button" popover="manual" data-direction="s" data-type="description" data-view-component="true" class="sr-only position-absolute">Create new...</tool-tip>
</div>

<anchored-position id="global-create-menu-overlay" anchor="global-create-menu-button" align="end" side="outside-bottom" anchor-offset="normal" popover="auto" data-view-component="true">
  <div data-view-component="true" class="Overlay Overlay--size-auto">
    
      
        <div data-view-component="true">
  <ul aria-labelledby="global-create-menu-button" id="global-create-menu-list" role="menu" data-view-component="true" class="ActionListWrap--inset ActionListWrap">
      <li data-analytics-event="{&quot;category&quot;:&quot;SiteHeaderComponent&quot;,&quot;action&quot;:&quot;add_dropdown&quot;,&quot;label&quot;:&quot;new repository&quot;}" data-targets="action-list.items" role="none" data-view-component="true" class="ActionListItem">
    
    <a href="/new" tabindex="-1" id="item-8d029faa-0c21-4b0d-8725-cd32c972e11a" role="menuitem" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-repo">
    <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
              New repository

</span></a>
  
  
</li>
      <li data-analytics-event="{&quot;category&quot;:&quot;SiteHeaderComponent&quot;,&quot;action&quot;:&quot;add_dropdown&quot;,&quot;label&quot;:&quot;import repository&quot;}" data-targets="action-list.items" role="none" data-view-component="true" class="ActionListItem">
    
    <a href="/new/import" tabindex="-1" id="item-c5239d1c-3533-42e1-983b-d18c1d2c70f6" role="menuitem" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-repo-push">
    <path d="M1 2.5A2.5 2.5 0 0 1 3.5 0h8.75a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0V1.5h-8a1 1 0 0 0-1 1v6.708A2.493 2.493 0 0 1 3.5 9h3.25a.75.75 0 0 1 0 1.5H3.5a1 1 0 0 0 0 2h5.75a.75.75 0 0 1 0 1.5H3.5A2.5 2.5 0 0 1 1 11.5Zm13.23 7.79h-.001l-1.224-1.224v6.184a.75.75 0 0 1-1.5 0V9.066L10.28 10.29a.75.75 0 0 1-1.06-1.061l2.505-2.504a.75.75 0 0 1 1.06 0L15.29 9.23a.751.751 0 0 1-.018 1.042.751.751 0 0 1-1.042.018Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
                Import repository

</span></a>
  
  
</li>
      <li role="presentation" aria-hidden="true" data-view-component="true" class="ActionList-sectionDivider"></li>
      <li data-analytics-event="{&quot;category&quot;:&quot;SiteHeaderComponent&quot;,&quot;action&quot;:&quot;add_dropdown&quot;,&quot;label&quot;:&quot;new codespace&quot;}" data-targets="action-list.items" role="none" data-view-component="true" class="ActionListItem">
    
    <a href="/codespaces/new" tabindex="-1" id="item-d5ca1c54-7e34-47d8-8078-29d01e0334e2" role="menuitem" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-codespaces">
    <path d="M0 11.25c0-.966.784-1.75 1.75-1.75h12.5c.966 0 1.75.784 1.75 1.75v3A1.75 1.75 0 0 1 14.25 16H1.75A1.75 1.75 0 0 1 0 14.25Zm2-9.5C2 .784 2.784 0 3.75 0h8.5C13.216 0 14 .784 14 1.75v5a1.75 1.75 0 0 1-1.75 1.75h-8.5A1.75 1.75 0 0 1 2 6.75Zm1.75-.25a.25.25 0 0 0-.25.25v5c0 .138.112.25.25.25h8.5a.25.25 0 0 0 .25-.25v-5a.25.25 0 0 0-.25-.25Zm-2 9.5a.25.25 0 0 0-.25.25v3c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25v-3a.25.25 0 0 0-.25-.25Z"></path><path d="M7 12.75a.75.75 0 0 1 .75-.75h4.5a.75.75 0 0 1 0 1.5h-4.5a.75.75 0 0 1-.75-.75Zm-4 0a.75.75 0 0 1 .75-.75h.5a.75.75 0 0 1 0 1.5h-.5a.75.75 0 0 1-.75-.75Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
                New codespace

</span></a>
  
  
</li>
      <li data-analytics-event="{&quot;category&quot;:&quot;SiteHeaderComponent&quot;,&quot;action&quot;:&quot;add_dropdown&quot;,&quot;label&quot;:&quot;new gist&quot;}" data-targets="action-list.items" role="none" data-view-component="true" class="ActionListItem">
    
    <a href="https://gist.github.com/" tabindex="-1" id="item-ba8d5651-856c-4470-b0e8-719561eb45f1" role="menuitem" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-code">
    <path d="m11.28 3.22 4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.749.749 0 0 1-1.275-.326.749.749 0 0 1 .215-.734L13.94 8l-3.72-3.72a.749.749 0 0 1 .326-1.275.749.749 0 0 1 .734.215Zm-6.56 0a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042L2.06 8l3.72 3.72a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L.47 8.53a.75.75 0 0 1 0-1.06Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
                New gist

</span></a>
  
  
</li>
      <li role="presentation" aria-hidden="true" data-view-component="true" class="ActionList-sectionDivider"></li>
      <li data-analytics-event="{&quot;category&quot;:&quot;SiteHeaderComponent&quot;,&quot;action&quot;:&quot;add_dropdown&quot;,&quot;label&quot;:&quot;new organization&quot;}" data-targets="action-list.items" role="none" data-view-component="true" class="ActionListItem">
    
    <a href="/account/organizations/new" tabindex="-1" id="item-6cbc9a59-9d93-4036-a0ad-39d846cdafe2" role="menuitem" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-organization">
    <path d="M1.75 16A1.75 1.75 0 0 1 0 14.25V1.75C0 .784.784 0 1.75 0h8.5C11.216 0 12 .784 12 1.75v12.5c0 .085-.006.168-.018.25h2.268a.25.25 0 0 0 .25-.25V8.285a.25.25 0 0 0-.111-.208l-1.055-.703a.749.749 0 1 1 .832-1.248l1.055.703c.487.325.779.871.779 1.456v5.965A1.75 1.75 0 0 1 14.25 16h-3.5a.766.766 0 0 1-.197-.026c-.099.017-.2.026-.303.026h-3a.75.75 0 0 1-.75-.75V14h-1v1.25a.75.75 0 0 1-.75.75Zm-.25-1.75c0 .138.112.25.25.25H4v-1.25a.75.75 0 0 1 .75-.75h2.5a.75.75 0 0 1 .75.75v1.25h2.25a.25.25 0 0 0 .25-.25V1.75a.25.25 0 0 0-.25-.25h-8.5a.25.25 0 0 0-.25.25ZM3.75 6h.5a.75.75 0 0 1 0 1.5h-.5a.75.75 0 0 1 0-1.5ZM3 3.75A.75.75 0 0 1 3.75 3h.5a.75.75 0 0 1 0 1.5h-.5A.75.75 0 0 1 3 3.75Zm4 3A.75.75 0 0 1 7.75 6h.5a.75.75 0 0 1 0 1.5h-.5A.75.75 0 0 1 7 6.75ZM7.75 3h.5a.75.75 0 0 1 0 1.5h-.5a.75.75 0 0 1 0-1.5ZM3 9.75A.75.75 0 0 1 3.75 9h.5a.75.75 0 0 1 0 1.5h-.5A.75.75 0 0 1 3 9.75ZM7.75 9h.5a.75.75 0 0 1 0 1.5h-.5a.75.75 0 0 1 0-1.5Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
                New organization

</span></a>
  
  
</li>
</ul>  
</div>

</div></anchored-position>  </focus-group>
</action-menu>

          <div data-view-component="true" class="Button-withTooltip">
  <a href="/issues" data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;ISSUES_HEADER&quot;,&quot;label&quot;:null}" id="icon-button-8e5e48c9-0fee-4808-b3d3-7f90ace5799a" aria-labelledby="tooltip-d596bfdb-a2f5-4744-b939-0072f0903c0a" data-view-component="true" class="Button Button--iconOnly Button--secondary Button--medium AppHeader-button color-fg-muted">    <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-issue-opened Button-visual">
    <path d="M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z"></path>
</svg>
</a>  <tool-tip id="tooltip-d596bfdb-a2f5-4744-b939-0072f0903c0a" for="icon-button-8e5e48c9-0fee-4808-b3d3-7f90ace5799a" popover="manual" data-direction="s" data-type="label" data-view-component="true" class="sr-only position-absolute">Issues</tool-tip>
</div>
          <div data-view-component="true" class="Button-withTooltip">
  <a href="/pulls" data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;PULL_REQUESTS_HEADER&quot;,&quot;label&quot;:null}" id="icon-button-c1af1866-f79c-453c-9101-47f4a761f3ba" aria-labelledby="tooltip-933e0c74-61ba-4590-a3b7-43e6a196d2a7" data-view-component="true" class="Button Button--iconOnly Button--secondary Button--medium AppHeader-button color-fg-muted">    <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-git-pull-request Button-visual">
    <path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z"></path>
</svg>
</a>  <tool-tip id="tooltip-933e0c74-61ba-4590-a3b7-43e6a196d2a7" for="icon-button-c1af1866-f79c-453c-9101-47f4a761f3ba" popover="manual" data-direction="s" data-type="label" data-view-component="true" class="sr-only position-absolute">Pull requests</tool-tip>
</div>
          
        </div>

        

<notification-indicator data-channel="eyJjIjoibm90aWZpY2F0aW9uLWNoYW5nZWQ6MTA2ODM2NzI2IiwidCI6MTY5NzEzMTA1M30=--1c03b06da7113b20310879a9c808bf9997d7add4598f6efae6a4b0536dedfc20" data-indicator-mode="none" data-tooltip-global="You have unread notifications" data-tooltip-unavailable="Notifications are unavailable at the moment." data-tooltip-none="You have no unread notifications" data-header-redesign-enabled="true" data-fetch-indicator-src="/notifications/indicator" data-fetch-indicator-enabled="true" data-view-component="true" class="js-socket-channel">
  <a id="AppHeader-notifications-button" href="/notifications"
    class="AppHeader-button Button--secondary"

    style="width:32px;height:32px;"

    data-hotkey="g n"
    data-target="notification-indicator.link"
    aria-label="Notifications"

      data-analytics-event="{&quot;category&quot;:&quot;SiteHeaderComponent&quot;,&quot;action&quot;:&quot;notifications&quot;,&quot;label&quot;:null}"
  >

    <span
      data-target="notification-indicator.badge"
      class="mail-status unread d-none" hidden>
    </span>

      <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-inbox color-fg-muted mr-0">
    <path d="M2.8 2.06A1.75 1.75 0 0 1 4.41 1h7.18c.7 0 1.333.417 1.61 1.06l2.74 6.395c.04.093.06.194.06.295v4.5A1.75 1.75 0 0 1 14.25 15H1.75A1.75 1.75 0 0 1 0 13.25v-4.5c0-.101.02-.202.06-.295Zm1.61.44a.25.25 0 0 0-.23.152L1.887 8H4.75a.75.75 0 0 1 .6.3L6.625 10h2.75l1.275-1.7a.75.75 0 0 1 .6-.3h2.863L11.82 2.652a.25.25 0 0 0-.23-.152Zm10.09 7h-2.875l-1.275 1.7a.75.75 0 0 1-.6.3h-3.5a.75.75 0 0 1-.6-.3L4.375 9.5H1.5v3.75c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25Z"></path>
</svg>
  </a>

    <tool-tip data-target="notification-indicator.tooltip" id="tooltip-2a6e1139-f693-4329-8b0c-fd8998dbb973" for="AppHeader-notifications-button" popover="manual" data-direction="s" data-type="description" data-view-component="true" class="sr-only position-absolute">Notifications</tool-tip>
</notification-indicator>

        

        <div class="AppHeader-user">
          <deferred-side-panel data-url="/_side-panels/user?memex_enabled=true&amp;repository=core&amp;user=eufysecurity&amp;user_can_create_organizations=true&amp;user_id=106836726">
  <include-fragment data-target="deferred-side-panel.fragment">
      <user-drawer-side-panel>
      <button aria-label="Open user account menu" data-action="click:deferred-side-panel#loadPanel click:deferred-side-panel#panelOpened" data-show-dialog-id="dialog-188d4ef0-2bc2-4ba4-8c02-bf9b76805716" id="dialog-show-dialog-188d4ef0-2bc2-4ba4-8c02-bf9b76805716" type="button" data-view-component="true" class="AppHeader-logo Button--invisible Button--medium Button Button--invisible-noVisuals color-bg-transparent p-0">    <span class="Button-content">
      <span class="Button-label"><img src="https://avatars.githubusercontent.com/u/106836726?v=4" alt="" size="32" height="32" width="32" data-view-component="true" class="avatar circle" /></span>
    </span>
</button>  

<div class="Overlay--hidden Overlay-backdrop--side Overlay-backdrop--placement-right" data-modal-dialog-overlay>
  <modal-dialog data-target="deferred-side-panel.panel" role="dialog" id="dialog-188d4ef0-2bc2-4ba4-8c02-bf9b76805716" aria-modal="true" aria-disabled="true" aria-labelledby="dialog-188d4ef0-2bc2-4ba4-8c02-bf9b76805716-title" aria-describedby="dialog-188d4ef0-2bc2-4ba4-8c02-bf9b76805716-description" data-view-component="true" class="Overlay Overlay-whenNarrow Overlay--size-small-portrait Overlay--motion-scaleFade SidePanel">
    <div styles="flex-direction: row;" data-view-component="true" class="Overlay-header">
  <div class="Overlay-headerContentWrap">
    <div class="Overlay-titleWrap">
      <h1 class="Overlay-title sr-only" id="dialog-188d4ef0-2bc2-4ba4-8c02-bf9b76805716-title">
        Account menu
      </h1>
            <div data-view-component="true" class="d-flex">
      <div data-view-component="true" class="AppHeader-logo position-relative">
        <img src="https://avatars.githubusercontent.com/u/106836726?v=4" alt="" size="32" height="32" width="32" data-view-component="true" class="avatar circle" />
</div>        <div data-view-component="true" class="overflow-hidden d-flex width-full">        <div data-view-component="true" class="lh-condensed overflow-hidden d-flex flex-column flex-justify-center ml-2 f5 mr-auto width-full">
          <span data-view-component="true" class="Truncate text-bold">
    <span data-view-component="true" class="Truncate-text">
            eufysecurity
</span>
</span>          </div>
</div>
</div>
    </div>
    <div class="Overlay-actionWrap">
      <button data-close-dialog-id="dialog-188d4ef0-2bc2-4ba4-8c02-bf9b76805716" aria-label="Close" type="button" data-view-component="true" class="close-button Overlay-closeButton"><svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-x">
    <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.749.749 0 0 1 1.275.326.749.749 0 0 1-.215.734L9.06 8l3.22 3.22a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L8 9.06l-3.22 3.22a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"></path>
</svg></button>
    </div>
  </div>
</div>
      <div data-view-component="true" class="Overlay-body d-flex flex-column height-full px-2">      <nav aria-label="User navigation" data-view-component="true" class="ActionList">
  
  <nav-list>
    <ul data-view-component="true" class="ActionListWrap">
        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <button id="item-396af3c3-b2f5-4281-b91c-52b6f6ce08c7" type="button" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <span data-view-component="true" class="d-flex flex-items-center">    <svg style="box-sizing: content-box; color: var(--color-icon-primary);" width="16" height="16" viewBox="0 0 16 16" fill="none" data-view-component="true" class="anim-rotate">
  <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-opacity="0.25" stroke-width="2" vector-effect="non-scaling-stroke" fill="none" />
  <path d="M15 8a7.002 7.002 0 00-7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" vector-effect="non-scaling-stroke" />
</svg>
</span>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          

  <span class="color-fg-muted">
    Loading...
  </span>

</span></button>
  
  
</li>

        
          <li role="presentation" aria-hidden="true" data-view-component="true" class="ActionList-sectionDivider"></li>
        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;PROFILE&quot;,&quot;label&quot;:null}" id="item-d2d0024f-6e5b-460b-9854-4f58ea1965f6" href="https://github.com/eufysecurity" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-person">
    <path d="M10.561 8.073a6.005 6.005 0 0 1 3.432 5.142.75.75 0 1 1-1.498.07 4.5 4.5 0 0 0-8.99 0 .75.75 0 0 1-1.498-.07 6.004 6.004 0 0 1 3.431-5.142 3.999 3.999 0 1 1 5.123 0ZM10.5 5a2.5 2.5 0 1 0-5 0 2.5 2.5 0 0 0 5 0Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          Your profile
</span></a>
  
  
</li>

        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <button id="item-b75e3f04-ada8-4748-9f65-469b7e8fb6d3" type="button" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <span data-view-component="true" class="d-flex flex-items-center">    <svg style="box-sizing: content-box; color: var(--color-icon-primary);" width="16" height="16" viewBox="0 0 16 16" fill="none" data-view-component="true" class="anim-rotate">
  <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-opacity="0.25" stroke-width="2" vector-effect="non-scaling-stroke" fill="none" />
  <path d="M15 8a7.002 7.002 0 00-7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" vector-effect="non-scaling-stroke" />
</svg>
</span>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          

  <span class="color-fg-muted">
    Loading...
  </span>

</span></button>
  
  
</li>

        
          <li role="presentation" aria-hidden="true" data-view-component="true" class="ActionList-sectionDivider"></li>
        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;YOUR_REPOSITORIES&quot;,&quot;label&quot;:null}" id="item-289060f2-c8ba-43ab-ae22-e138b89dead1" href="/eufysecurity?tab=repositories" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-repo">
    <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          Your repositories
</span></a>
  
  
</li>

        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;YOUR_PROJECTS&quot;,&quot;label&quot;:null}" id="item-42c400f2-827b-479f-9428-2f20b285cd83" href="/eufysecurity?tab=projects" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-project">
    <path d="M1.75 0h12.5C15.216 0 16 .784 16 1.75v12.5A1.75 1.75 0 0 1 14.25 16H1.75A1.75 1.75 0 0 1 0 14.25V1.75C0 .784.784 0 1.75 0ZM1.5 1.75v12.5c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25V1.75a.25.25 0 0 0-.25-.25H1.75a.25.25 0 0 0-.25.25ZM11.75 3a.75.75 0 0 1 .75.75v7.5a.75.75 0 0 1-1.5 0v-7.5a.75.75 0 0 1 .75-.75Zm-8.25.75a.75.75 0 0 1 1.5 0v5.5a.75.75 0 0 1-1.5 0ZM8 3a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 8 3Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          Your projects
</span></a>
  
  
</li>

        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <button id="item-981da4a9-901f-4cf2-a921-91a440a3084e" type="button" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <span data-view-component="true" class="d-flex flex-items-center">    <svg style="box-sizing: content-box; color: var(--color-icon-primary);" width="16" height="16" viewBox="0 0 16 16" fill="none" data-view-component="true" class="anim-rotate">
  <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-opacity="0.25" stroke-width="2" vector-effect="non-scaling-stroke" fill="none" />
  <path d="M15 8a7.002 7.002 0 00-7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" vector-effect="non-scaling-stroke" />
</svg>
</span>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          

  <span class="color-fg-muted">
    Loading...
  </span>

</span></button>
  
  
</li>

        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;YOUR_STARS&quot;,&quot;label&quot;:null}" id="item-23424bc7-d63c-4879-bd0e-4fc31401df72" href="/eufysecurity?tab=stars" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-star">
    <path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Zm0 2.445L6.615 5.5a.75.75 0 0 1-.564.41l-3.097.45 2.24 2.184a.75.75 0 0 1 .216.664l-.528 3.084 2.769-1.456a.75.75 0 0 1 .698 0l2.77 1.456-.53-3.084a.75.75 0 0 1 .216-.664l2.24-2.183-3.096-.45a.75.75 0 0 1-.564-.41L8 2.694Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          Your stars
</span></a>
  
  
</li>

        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;SPONSORS&quot;,&quot;label&quot;:null}" id="item-306aa087-bf58-4ded-a57d-898e17c85161" href="/sponsors/accounts" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-heart">
    <path d="m8 14.25.345.666a.75.75 0 0 1-.69 0l-.008-.004-.018-.01a7.152 7.152 0 0 1-.31-.17 22.055 22.055 0 0 1-3.434-2.414C2.045 10.731 0 8.35 0 5.5 0 2.836 2.086 1 4.25 1 5.797 1 7.153 1.802 8 3.02 8.847 1.802 10.203 1 11.75 1 13.914 1 16 2.836 16 5.5c0 2.85-2.045 5.231-3.885 6.818a22.066 22.066 0 0 1-3.744 2.584l-.018.01-.006.003h-.002ZM4.25 2.5c-1.336 0-2.75 1.164-2.75 3 0 2.15 1.58 4.144 3.365 5.682A20.58 20.58 0 0 0 8 13.393a20.58 20.58 0 0 0 3.135-2.211C12.92 9.644 14.5 7.65 14.5 5.5c0-1.836-1.414-3-2.75-3-1.373 0-2.609.986-3.029 2.456a.749.749 0 0 1-1.442 0C6.859 3.486 5.623 2.5 4.25 2.5Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          Your sponsors
</span></a>
  
  
</li>

        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;YOUR_GISTS&quot;,&quot;label&quot;:null}" id="item-c65781f6-703b-40b4-8417-67def3007752" href="https://gist.github.com/mine" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-code-square">
    <path d="M0 1.75C0 .784.784 0 1.75 0h12.5C15.216 0 16 .784 16 1.75v12.5A1.75 1.75 0 0 1 14.25 16H1.75A1.75 1.75 0 0 1 0 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25V1.75a.25.25 0 0 0-.25-.25Zm7.47 3.97a.75.75 0 0 1 1.06 0l2 2a.75.75 0 0 1 0 1.06l-2 2a.749.749 0 0 1-1.275-.326.749.749 0 0 1 .215-.734L10.69 8 9.22 6.53a.75.75 0 0 1 0-1.06ZM6.78 6.53 5.31 8l1.47 1.47a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215l-2-2a.75.75 0 0 1 0-1.06l2-2a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          Your gists
</span></a>
  
  
</li>

        
          <li role="presentation" aria-hidden="true" data-view-component="true" class="ActionList-sectionDivider"></li>
        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <button id="item-5a574dd1-740d-401b-9a99-c8f19f9d7c89" type="button" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <span data-view-component="true" class="d-flex flex-items-center">    <svg style="box-sizing: content-box; color: var(--color-icon-primary);" width="16" height="16" viewBox="0 0 16 16" fill="none" data-view-component="true" class="anim-rotate">
  <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-opacity="0.25" stroke-width="2" vector-effect="non-scaling-stroke" fill="none" />
  <path d="M15 8a7.002 7.002 0 00-7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" vector-effect="non-scaling-stroke" />
</svg>
</span>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          

  <span class="color-fg-muted">
    Loading...
  </span>

</span></button>
  
  
</li>

        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <button id="item-64afbcaf-0b1f-47bf-be3d-84144c826490" type="button" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <span data-view-component="true" class="d-flex flex-items-center">    <svg style="box-sizing: content-box; color: var(--color-icon-primary);" width="16" height="16" viewBox="0 0 16 16" fill="none" data-view-component="true" class="anim-rotate">
  <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-opacity="0.25" stroke-width="2" vector-effect="non-scaling-stroke" fill="none" />
  <path d="M15 8a7.002 7.002 0 00-7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" vector-effect="non-scaling-stroke" />
</svg>
</span>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          

  <span class="color-fg-muted">
    Loading...
  </span>

</span></button>
  
  
</li>

        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <button id="item-0aa7a0bc-79dc-4086-97fe-f088d395b6b6" type="button" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <span data-view-component="true" class="d-flex flex-items-center">    <svg style="box-sizing: content-box; color: var(--color-icon-primary);" width="16" height="16" viewBox="0 0 16 16" fill="none" data-view-component="true" class="anim-rotate">
  <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-opacity="0.25" stroke-width="2" vector-effect="non-scaling-stroke" fill="none" />
  <path d="M15 8a7.002 7.002 0 00-7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" vector-effect="non-scaling-stroke" />
</svg>
</span>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          

  <span class="color-fg-muted">
    Loading...
  </span>

</span></button>
  
  
</li>

        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;SETTINGS&quot;,&quot;label&quot;:null}" id="item-b0a84c72-cf9d-4d5b-a12c-943f51db46b5" href="/settings/profile" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-gear">
    <path d="M8 0a8.2 8.2 0 0 1 .701.031C9.444.095 9.99.645 10.16 1.29l.288 1.107c.018.066.079.158.212.224.231.114.454.243.668.386.123.082.233.09.299.071l1.103-.303c.644-.176 1.392.021 1.82.63.27.385.506.792.704 1.218.315.675.111 1.422-.364 1.891l-.814.806c-.049.048-.098.147-.088.294.016.257.016.515 0 .772-.01.147.038.246.088.294l.814.806c.475.469.679 1.216.364 1.891a7.977 7.977 0 0 1-.704 1.217c-.428.61-1.176.807-1.82.63l-1.102-.302c-.067-.019-.177-.011-.3.071a5.909 5.909 0 0 1-.668.386c-.133.066-.194.158-.211.224l-.29 1.106c-.168.646-.715 1.196-1.458 1.26a8.006 8.006 0 0 1-1.402 0c-.743-.064-1.289-.614-1.458-1.26l-.289-1.106c-.018-.066-.079-.158-.212-.224a5.738 5.738 0 0 1-.668-.386c-.123-.082-.233-.09-.299-.071l-1.103.303c-.644.176-1.392-.021-1.82-.63a8.12 8.12 0 0 1-.704-1.218c-.315-.675-.111-1.422.363-1.891l.815-.806c.05-.048.098-.147.088-.294a6.214 6.214 0 0 1 0-.772c.01-.147-.038-.246-.088-.294l-.815-.806C.635 6.045.431 5.298.746 4.623a7.92 7.92 0 0 1 .704-1.217c.428-.61 1.176-.807 1.82-.63l1.102.302c.067.019.177.011.3-.071.214-.143.437-.272.668-.386.133-.066.194-.158.211-.224l.29-1.106C6.009.645 6.556.095 7.299.03 7.53.01 7.764 0 8 0Zm-.571 1.525c-.036.003-.108.036-.137.146l-.289 1.105c-.147.561-.549.967-.998 1.189-.173.086-.34.183-.5.29-.417.278-.97.423-1.529.27l-1.103-.303c-.109-.03-.175.016-.195.045-.22.312-.412.644-.573.99-.014.031-.021.11.059.19l.815.806c.411.406.562.957.53 1.456a4.709 4.709 0 0 0 0 .582c.032.499-.119 1.05-.53 1.456l-.815.806c-.081.08-.073.159-.059.19.162.346.353.677.573.989.02.03.085.076.195.046l1.102-.303c.56-.153 1.113-.008 1.53.27.161.107.328.204.501.29.447.222.85.629.997 1.189l.289 1.105c.029.109.101.143.137.146a6.6 6.6 0 0 0 1.142 0c.036-.003.108-.036.137-.146l.289-1.105c.147-.561.549-.967.998-1.189.173-.086.34-.183.5-.29.417-.278.97-.423 1.529-.27l1.103.303c.109.029.175-.016.195-.045.22-.313.411-.644.573-.99.014-.031.021-.11-.059-.19l-.815-.806c-.411-.406-.562-.957-.53-1.456a4.709 4.709 0 0 0 0-.582c-.032-.499.119-1.05.53-1.456l.815-.806c.081-.08.073-.159.059-.19a6.464 6.464 0 0 0-.573-.989c-.02-.03-.085-.076-.195-.046l-1.102.303c-.56.153-1.113.008-1.53-.27a4.44 4.44 0 0 0-.501-.29c-.447-.222-.85-.629-.997-1.189l-.289-1.105c-.029-.11-.101-.143-.137-.146a6.6 6.6 0 0 0-1.142 0ZM11 8a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM9.5 8a1.5 1.5 0 1 0-3.001.001A1.5 1.5 0 0 0 9.5 8Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          Settings
</span></a>
  
  
</li>

        
          <li role="presentation" aria-hidden="true" data-view-component="true" class="ActionList-sectionDivider"></li>
        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;DOCS&quot;,&quot;label&quot;:null}" id="item-dc87faed-0f15-4c30-9894-7b87f321481c" href="https://docs.github.com" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-book">
    <path d="M0 1.75A.75.75 0 0 1 .75 1h4.253c1.227 0 2.317.59 3 1.501A3.743 3.743 0 0 1 11.006 1h4.245a.75.75 0 0 1 .75.75v10.5a.75.75 0 0 1-.75.75h-4.507a2.25 2.25 0 0 0-1.591.659l-.622.621a.75.75 0 0 1-1.06 0l-.622-.621A2.25 2.25 0 0 0 5.258 13H.75a.75.75 0 0 1-.75-.75Zm7.251 10.324.004-5.073-.002-2.253A2.25 2.25 0 0 0 5.003 2.5H1.5v9h3.757a3.75 3.75 0 0 1 1.994.574ZM8.755 4.75l-.004 7.322a3.752 3.752 0 0 1 1.992-.572H14.5v-9h-3.495a2.25 2.25 0 0 0-2.25 2.25Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          GitHub Docs
</span></a>
  
  
</li>

        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;SUPPORT&quot;,&quot;label&quot;:null}" id="item-3211e120-f47c-402e-8cf9-d2eedfde2c87" href="https://support.github.com" data-view-component="true" class="ActionListContent ActionListContent--visual16">
        <span class="ActionListItem-visual ActionListItem-visual--leading">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-people">
    <path d="M2 5.5a3.5 3.5 0 1 1 5.898 2.549 5.508 5.508 0 0 1 3.034 4.084.75.75 0 1 1-1.482.235 4 4 0 0 0-7.9 0 .75.75 0 0 1-1.482-.236A5.507 5.507 0 0 1 3.102 8.05 3.493 3.493 0 0 1 2 5.5ZM11 4a3.001 3.001 0 0 1 2.22 5.018 5.01 5.01 0 0 1 2.56 3.012.749.749 0 0 1-.885.954.752.752 0 0 1-.549-.514 3.507 3.507 0 0 0-2.522-2.372.75.75 0 0 1-.574-.73v-.352a.75.75 0 0 1 .416-.672A1.5 1.5 0 0 0 11 5.5.75.75 0 0 1 11 4Zm-5.5-.5a2 2 0 1 0-.001 3.999A2 2 0 0 0 5.5 3.5Z"></path>
</svg>
        </span>
      
        <span data-view-component="true" class="ActionListItem-label">
          GitHub Support
</span></a>
  
  
</li>

        
          <li role="presentation" aria-hidden="true" data-view-component="true" class="ActionList-sectionDivider"></li>
        
          
<li data-item-id="" data-targets="nav-list.items" data-view-component="true" class="ActionListItem">
    
    <a data-analytics-event="{&quot;category&quot;:&quot;Global navigation&quot;,&quot;action&quot;:&quot;LOGOUT&quot;,&quot;label&quot;:null}" id="item-9ba97644-a7c0-475b-a094-3070480befc1" href="/logout" data-view-component="true" class="ActionListContent">
      
        <span data-view-component="true" class="ActionListItem-label">
          Sign out
</span></a>
  
  
</li>

</ul>  </nav-list>
</nav>


</div>
      
</modal-dialog></div>
  </user-drawer-side-panel>

  </include-fragment>
</deferred-side-panel>
        </div>

        <div class="position-absolute mt-2">
            
<site-header-logged-in-user-menu>

</site-header-logged-in-user-menu>

        </div>
      </div>
    </div>


      <div class="AppHeader-localBar" >
        <nav data-pjax="#js-repo-pjax-container" aria-label="Repository" data-view-component="true" class="js-repo-nav js-sidenav-container-pjax js-responsive-underlinenav overflow-hidden UnderlineNav">

  <ul data-view-component="true" class="UnderlineNav-body list-style-none">
      <li data-view-component="true" class="d-inline-flex">
  <a id="code-tab" href="/home-assistant/core/tree/2023.10.1" data-tab-item="i0code-tab" data-selected-links="repo_source repo_downloads repo_commits repo_releases repo_tags repo_branches repo_packages repo_deployments repo_attestations /home-assistant/core/tree/2023.10.1" data-pjax="#repo-content-pjax-container" data-turbo-frame="repo-content-turbo-frame" data-hotkey="g c" data-analytics-event="{&quot;category&quot;:&quot;Underline navbar&quot;,&quot;action&quot;:&quot;Click tab&quot;,&quot;label&quot;:&quot;Code&quot;,&quot;target&quot;:&quot;UNDERLINE_NAV.TAB&quot;}" data-view-component="true" class="UnderlineNav-item no-wrap js-responsive-underlinenav-item js-selected-navigation-item">
    
              <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-code UnderlineNav-octicon d-none d-sm-inline">
    <path d="m11.28 3.22 4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.749.749 0 0 1-1.275-.326.749.749 0 0 1 .215-.734L13.94 8l-3.72-3.72a.749.749 0 0 1 .326-1.275.749.749 0 0 1 .734.215Zm-6.56 0a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042L2.06 8l3.72 3.72a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L.47 8.53a.75.75 0 0 1 0-1.06Z"></path>
</svg>
        <span data-content="Code">Code</span>
          <span id="code-repo-tab-count" data-pjax-replace="" data-turbo-replace="" title="Not available" data-view-component="true" class="Counter"></span>


    
</a></li>
      <li data-view-component="true" class="d-inline-flex">
  <a id="issues-tab" href="/home-assistant/core/issues" data-tab-item="i1issues-tab" data-selected-links="repo_issues repo_labels repo_milestones /home-assistant/core/issues" data-pjax="#repo-content-pjax-container" data-turbo-frame="repo-content-turbo-frame" data-hotkey="g i" data-analytics-event="{&quot;category&quot;:&quot;Underline navbar&quot;,&quot;action&quot;:&quot;Click tab&quot;,&quot;label&quot;:&quot;Issues&quot;,&quot;target&quot;:&quot;UNDERLINE_NAV.TAB&quot;}" data-view-component="true" class="UnderlineNav-item no-wrap js-responsive-underlinenav-item js-selected-navigation-item">
    
              <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-issue-opened UnderlineNav-octicon d-none d-sm-inline">
    <path d="M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z"></path>
</svg>
        <span data-content="Issues">Issues</span>
          <span id="issues-repo-tab-count" data-pjax-replace="" data-turbo-replace="" title="2,134" data-view-component="true" class="Counter">2.1k</span>


    
</a></li>
      <li data-view-component="true" class="d-inline-flex">
  <a id="pull-requests-tab" href="/home-assistant/core/pulls" data-tab-item="i2pull-requests-tab" data-selected-links="repo_pulls checks /home-assistant/core/pulls" data-pjax="#repo-content-pjax-container" data-turbo-frame="repo-content-turbo-frame" data-hotkey="g p" data-analytics-event="{&quot;category&quot;:&quot;Underline navbar&quot;,&quot;action&quot;:&quot;Click tab&quot;,&quot;label&quot;:&quot;Pull requests&quot;,&quot;target&quot;:&quot;UNDERLINE_NAV.TAB&quot;}" data-view-component="true" class="UnderlineNav-item no-wrap js-responsive-underlinenav-item js-selected-navigation-item">
    
              <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-git-pull-request UnderlineNav-octicon d-none d-sm-inline">
    <path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z"></path>
</svg>
        <span data-content="Pull requests">Pull requests</span>
          <span id="pull-requests-repo-tab-count" data-pjax-replace="" data-turbo-replace="" title="450" data-view-component="true" class="Counter">450</span>


    
</a></li>
      <li data-view-component="true" class="d-inline-flex">
  <a id="actions-tab" href="/home-assistant/core/actions" data-tab-item="i3actions-tab" data-selected-links="repo_actions /home-assistant/core/actions" data-pjax="#repo-content-pjax-container" data-turbo-frame="repo-content-turbo-frame" data-hotkey="g a" data-analytics-event="{&quot;category&quot;:&quot;Underline navbar&quot;,&quot;action&quot;:&quot;Click tab&quot;,&quot;label&quot;:&quot;Actions&quot;,&quot;target&quot;:&quot;UNDERLINE_NAV.TAB&quot;}" data-view-component="true" class="UnderlineNav-item no-wrap js-responsive-underlinenav-item js-selected-navigation-item">
    
              <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-play UnderlineNav-octicon d-none d-sm-inline">
    <path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Zm4.879-2.773 4.264 2.559a.25.25 0 0 1 0 .428l-4.264 2.559A.25.25 0 0 1 6 10.559V5.442a.25.25 0 0 1 .379-.215Z"></path>
</svg>
        <span data-content="Actions">Actions</span>
          <span id="actions-repo-tab-count" data-pjax-replace="" data-turbo-replace="" title="Not available" data-view-component="true" class="Counter"></span>


    
</a></li>
      <li data-view-component="true" class="d-inline-flex">
  <a id="projects-tab" href="/home-assistant/core/projects" data-tab-item="i4projects-tab" data-selected-links="repo_projects new_repo_project repo_project /home-assistant/core/projects" data-pjax="#repo-content-pjax-container" data-turbo-frame="repo-content-turbo-frame" data-hotkey="g b" data-analytics-event="{&quot;category&quot;:&quot;Underline navbar&quot;,&quot;action&quot;:&quot;Click tab&quot;,&quot;label&quot;:&quot;Projects&quot;,&quot;target&quot;:&quot;UNDERLINE_NAV.TAB&quot;}" data-view-component="true" class="UnderlineNav-item no-wrap js-responsive-underlinenav-item js-selected-navigation-item">
    
              <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-table UnderlineNav-octicon d-none d-sm-inline">
    <path d="M0 1.75C0 .784.784 0 1.75 0h12.5C15.216 0 16 .784 16 1.75v12.5A1.75 1.75 0 0 1 14.25 16H1.75A1.75 1.75 0 0 1 0 14.25ZM6.5 6.5v8h7.75a.25.25 0 0 0 .25-.25V6.5Zm8-1.5V1.75a.25.25 0 0 0-.25-.25H6.5V5Zm-13 1.5v7.75c0 .138.112.25.25.25H5v-8ZM5 5V1.5H1.75a.25.25 0 0 0-.25.25V5Z"></path>
</svg>
        <span data-content="Projects">Projects</span>
          <span id="projects-repo-tab-count" data-pjax-replace="" data-turbo-replace="" title="2" data-view-component="true" class="Counter">2</span>


    
</a></li>
      <li data-view-component="true" class="d-inline-flex">
  <a id="security-tab" href="/home-assistant/core/security" data-tab-item="i5security-tab" data-selected-links="security overview alerts policy token_scanning code_scanning /home-assistant/core/security" data-pjax="#repo-content-pjax-container" data-turbo-frame="repo-content-turbo-frame" data-hotkey="g s" data-analytics-event="{&quot;category&quot;:&quot;Underline navbar&quot;,&quot;action&quot;:&quot;Click tab&quot;,&quot;label&quot;:&quot;Security&quot;,&quot;target&quot;:&quot;UNDERLINE_NAV.TAB&quot;}" data-view-component="true" class="UnderlineNav-item no-wrap js-responsive-underlinenav-item js-selected-navigation-item">
    
              <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-shield UnderlineNav-octicon d-none d-sm-inline">
    <path d="M7.467.133a1.748 1.748 0 0 1 1.066 0l5.25 1.68A1.75 1.75 0 0 1 15 3.48V7c0 1.566-.32 3.182-1.303 4.682-.983 1.498-2.585 2.813-5.032 3.855a1.697 1.697 0 0 1-1.33 0c-2.447-1.042-4.049-2.357-5.032-3.855C1.32 10.182 1 8.566 1 7V3.48a1.75 1.75 0 0 1 1.217-1.667Zm.61 1.429a.25.25 0 0 0-.153 0l-5.25 1.68a.25.25 0 0 0-.174.238V7c0 1.358.275 2.666 1.057 3.86.784 1.194 2.121 2.34 4.366 3.297a.196.196 0 0 0 .154 0c2.245-.956 3.582-2.104 4.366-3.298C13.225 9.666 13.5 8.36 13.5 7V3.48a.251.251 0 0 0-.174-.237l-5.25-1.68ZM8.75 4.75v3a.75.75 0 0 1-1.5 0v-3a.75.75 0 0 1 1.5 0ZM9 10.5a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"></path>
</svg>
        <span data-content="Security">Security</span>
          <include-fragment src="/home-assistant/core/security/overall-count" accept="text/fragment+html"></include-fragment>

    
</a></li>
      <li data-view-component="true" class="d-inline-flex">
  <a id="insights-tab" href="/home-assistant/core/pulse" data-tab-item="i6insights-tab" data-selected-links="repo_graphs repo_contributors dependency_graph dependabot_updates pulse people community /home-assistant/core/pulse" data-pjax="#repo-content-pjax-container" data-turbo-frame="repo-content-turbo-frame" data-analytics-event="{&quot;category&quot;:&quot;Underline navbar&quot;,&quot;action&quot;:&quot;Click tab&quot;,&quot;label&quot;:&quot;Insights&quot;,&quot;target&quot;:&quot;UNDERLINE_NAV.TAB&quot;}" data-view-component="true" class="UnderlineNav-item no-wrap js-responsive-underlinenav-item js-selected-navigation-item">
    
              <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-graph UnderlineNav-octicon d-none d-sm-inline">
    <path d="M1.5 1.75V13.5h13.75a.75.75 0 0 1 0 1.5H.75a.75.75 0 0 1-.75-.75V1.75a.75.75 0 0 1 1.5 0Zm14.28 2.53-5.25 5.25a.75.75 0 0 1-1.06 0L7 7.06 4.28 9.78a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042l3.25-3.25a.75.75 0 0 1 1.06 0L10 7.94l4.72-4.72a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042Z"></path>
</svg>
        <span data-content="Insights">Insights</span>
          <span id="insights-repo-tab-count" data-pjax-replace="" data-turbo-replace="" title="Not available" data-view-component="true" class="Counter"></span>


    
</a></li>
</ul>
    <div style="visibility:hidden;" data-view-component="true" class="UnderlineNav-actions js-responsive-underlinenav-overflow position-absolute pr-3 pr-md-4 pr-lg-5 right-0">        <details data-view-component="true" class="details-overlay details-reset position-relative">
    <summary role="button" data-view-component="true">          <div class="UnderlineNav-item mr-0 border-0">
            <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-kebab-horizontal">
    <path d="M8 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM1.5 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Zm13 0a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path>
</svg>
            <span class="sr-only">More</span>
          </div>
</summary>
    <details-menu role="menu" data-view-component="true" class="dropdown-menu dropdown-menu-sw">
          <ul>
              <li data-menu-item="i0code-tab" hidden>
                <a role="menuitem" class="js-selected-navigation-item dropdown-item" data-selected-links="repo_source repo_downloads repo_commits repo_releases repo_tags repo_branches repo_packages repo_deployments repo_attestations /home-assistant/core/tree/2023.10.1" href="/home-assistant/core/tree/2023.10.1">
                  Code
</a>              </li>
              <li data-menu-item="i1issues-tab" hidden>
                <a role="menuitem" class="js-selected-navigation-item dropdown-item" data-selected-links="repo_issues repo_labels repo_milestones /home-assistant/core/issues" href="/home-assistant/core/issues">
                  Issues
</a>              </li>
              <li data-menu-item="i2pull-requests-tab" hidden>
                <a role="menuitem" class="js-selected-navigation-item dropdown-item" data-selected-links="repo_pulls checks /home-assistant/core/pulls" href="/home-assistant/core/pulls">
                  Pull requests
</a>              </li>
              <li data-menu-item="i3actions-tab" hidden>
                <a role="menuitem" class="js-selected-navigation-item dropdown-item" data-selected-links="repo_actions /home-assistant/core/actions" href="/home-assistant/core/actions">
                  Actions
</a>              </li>
              <li data-menu-item="i4projects-tab" hidden>
                <a role="menuitem" class="js-selected-navigation-item dropdown-item" data-selected-links="repo_projects new_repo_project repo_project /home-assistant/core/projects" href="/home-assistant/core/projects">
                  Projects
</a>              </li>
              <li data-menu-item="i5security-tab" hidden>
                <a role="menuitem" class="js-selected-navigation-item dropdown-item" data-selected-links="security overview alerts policy token_scanning code_scanning /home-assistant/core/security" href="/home-assistant/core/security">
                  Security
</a>              </li>
              <li data-menu-item="i6insights-tab" hidden>
                <a role="menuitem" class="js-selected-navigation-item dropdown-item" data-selected-links="repo_graphs repo_contributors dependency_graph dependabot_updates pulse people community /home-assistant/core/pulse" href="/home-assistant/core/pulse">
                  Insights
</a>              </li>
          </ul>
</details-menu>
</details></div>
</nav>
      </div>
</header>


      <div hidden="hidden" data-view-component="true" class="js-stale-session-flash stale-session-flash flash flash-warn mb-3">
  
        <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-alert">
    <path d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575Zm1.763.707a.25.25 0 0 0-.44 0L1.698 13.132a.25.25 0 0 0 .22.368h12.164a.25.25 0 0 0 .22-.368Zm.53 3.996v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"></path>
</svg>
        <span class="js-stale-session-flash-signed-in" hidden>You signed in with another tab or window. <a class="Link--inTextBlock" href="">Reload</a> to refresh your session.</span>
        <span class="js-stale-session-flash-signed-out" hidden>You signed out in another tab or window. <a class="Link--inTextBlock" href="">Reload</a> to refresh your session.</span>
        <span class="js-stale-session-flash-switched" hidden>You switched accounts on another tab or window. <a class="Link--inTextBlock" href="">Reload</a> to refresh your session.</span>

    <div data-view-component="true" class="flash-close">
  <button id="icon-button-7a1d7011-32de-4c5e-ba2a-50e292f738b7" aria-labelledby="tooltip-f38a00d9-32ff-4821-8a19-cf022d6d881d" type="button" data-view-component="true" class="Button Button--iconOnly Button--invisible Button--medium js-flash-close">    <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-x Button-visual">
    <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.749.749 0 0 1 1.275.326.749.749 0 0 1-.215.734L9.06 8l3.22 3.22a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L8 9.06l-3.22 3.22a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"></path>
</svg>
</button>  <tool-tip id="tooltip-f38a00d9-32ff-4821-8a19-cf022d6d881d" for="icon-button-7a1d7011-32de-4c5e-ba2a-50e292f738b7" popover="manual" data-direction="s" data-type="label" data-view-component="true" class="sr-only position-absolute">Dismiss alert</tool-tip>
</div>

  
</div>
          
    </div>

  <div id="start-of-content" class="show-on-focus"></div>








    <div id="js-flash-container" data-turbo-replace>





  <template class="js-flash-template">
    
<div class="flash flash-full   {{ className }}">
  <div class="px-2" >
    <button autofocus class="flash-close js-flash-close" type="button" aria-label="Dismiss this message">
      <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-x">
    <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.749.749 0 0 1 1.275.326.749.749 0 0 1-.215.734L9.06 8l3.22 3.22a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L8 9.06l-3.22 3.22a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"></path>
</svg>
    </button>
    <div aria-atomic="true" role="alert" class="js-flash-alert">
      
      <div>{{ message }}</div>

    </div>
  </div>
</div>
  </template>
</div>


    
    <notification-shelf-watcher data-base-url="https://github.com/notifications/beta/shelf" data-channel="eyJjIjoibm90aWZpY2F0aW9uLWNoYW5nZWQ6MTA2ODM2NzI2IiwidCI6MTY5NzEzMTA1M30=--1c03b06da7113b20310879a9c808bf9997d7add4598f6efae6a4b0536dedfc20" data-view-component="true" class="js-socket-channel"></notification-shelf-watcher>
  <div hidden data-initial data-target="notification-shelf-watcher.placeholder"></div>






      <details
  class="details-reset details-overlay details-overlay-dark js-command-palette-dialog"
  id="command-palette-pjax-container"
  data-turbo-replace
>
  <summary aria-label="Command palette trigger" tabindex="-1"></summary>
  <details-dialog class="command-palette-details-dialog d-flex flex-column flex-justify-center height-fit" aria-label="Command palette">
    <command-palette
      class="command-palette color-bg-default rounded-3 border color-shadow-small"
      return-to=/home-assistant/core/blob/2023.10.1/homeassistant/components/mazda/diagnostics.py
      user-id="106836726"
      activation-hotkey="Mod+k,Mod+Alt+k"
      command-mode-hotkey="Mod+Shift+k"
      data-action="
        command-palette-input-ready:command-palette#inputReady
        command-palette-page-stack-updated:command-palette#updateInputScope
        itemsUpdated:command-palette#itemsUpdated
        keydown:command-palette#onKeydown
        loadingStateChanged:command-palette#loadingStateChanged
        selectedItemChanged:command-palette#selectedItemChanged
        pageFetchError:command-palette#pageFetchError
      ">

        <command-palette-mode
          data-char="#"
            data-scope-types="[&quot;&quot;]"
            data-placeholder="Search issues and pull requests"
        ></command-palette-mode>
        <command-palette-mode
          data-char="#"
            data-scope-types="[&quot;owner&quot;,&quot;repository&quot;]"
            data-placeholder="Search issues, pull requests, discussions, and projects"
        ></command-palette-mode>
        <command-palette-mode
          data-char="!"
            data-scope-types="[&quot;owner&quot;,&quot;repository&quot;]"
            data-placeholder="Search projects"
        ></command-palette-mode>
        <command-palette-mode
          data-char="@"
            data-scope-types="[&quot;&quot;]"
            data-placeholder="Search or jump to a user, organization, or repository"
        ></command-palette-mode>
        <command-palette-mode
          data-char="@"
            data-scope-types="[&quot;owner&quot;]"
            data-placeholder="Search or jump to a repository"
        ></command-palette-mode>
        <command-palette-mode
          data-char="/"
            data-scope-types="[&quot;repository&quot;]"
            data-placeholder="Search files"
        ></command-palette-mode>
        <command-palette-mode
          data-char="?"
        ></command-palette-mode>
        <command-palette-mode
          data-char="&gt;"
            data-placeholder="Run a command"
        ></command-palette-mode>
        <command-palette-mode
          data-char=""
            data-scope-types="[&quot;&quot;]"
            data-placeholder="Search or jump to..."
        ></command-palette-mode>
        <command-palette-mode
          data-char=""
            data-scope-types="[&quot;owner&quot;]"
            data-placeholder="Search or jump to..."
        ></command-palette-mode>
      <command-palette-mode
        class="js-command-palette-default-mode"
        data-char=""
        data-placeholder="Search or jump to..."
      ></command-palette-mode>

      <command-palette-input placeholder="Search or jump to..."

        data-action="
          command-palette-input:command-palette#onInput
          command-palette-select:command-palette#onSelect
          command-palette-descope:command-palette#onDescope
          command-palette-cleared:command-palette#onInputClear
        "
      >
        <div class="js-search-icon d-flex flex-items-center mr-2" style="height: 26px">
          <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-search color-fg-muted">
    <path d="M10.68 11.74a6 6 0 0 1-7.922-8.982 6 6 0 0 1 8.982 7.922l3.04 3.04a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215ZM11.5 7a4.499 4.499 0 1 0-8.997 0A4.499 4.499 0 0 0 11.5 7Z"></path>
</svg>
        </div>
        <div class="js-spinner d-flex flex-items-center mr-2 color-fg-muted" hidden>
          <svg aria-label="Loading" class="anim-rotate" viewBox="0 0 16 16" fill="none" width="16" height="16">
            <circle
              cx="8"
              cy="8"
              r="7"
              stroke="currentColor"
              stroke-opacity="0.25"
              stroke-width="2"
              vector-effect="non-scaling-stroke"
            ></circle>
            <path
              d="M15 8a7.002 7.002 0 00-7-7"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              vector-effect="non-scaling-stroke"
            ></path>
          </svg>
        </div>
        <command-palette-scope >
          <div data-target="command-palette-scope.placeholder" hidden class="color-fg-subtle">/&nbsp;&nbsp;<span class="text-semibold color-fg-default">...</span>&nbsp;&nbsp;/&nbsp;&nbsp;</div>
              <command-palette-token
                data-text="home-assistant"
                data-id="MDEyOk9yZ2FuaXphdGlvbjEzODQ0OTc1"
                data-type="owner"
                data-value="home-assistant"
                data-targets="command-palette-scope.tokens"
                class="color-fg-default text-semibold"
                style="white-space:nowrap;line-height:20px;"
                >home-assistant<span class="color-fg-subtle text-normal">&nbsp;&nbsp;/&nbsp;&nbsp;</span></command-palette-token>
              <command-palette-token
                data-text="core"
                data-id="MDEwOlJlcG9zaXRvcnkxMjg4ODk5Mw=="
                data-type="repository"
                data-value="core"
                data-targets="command-palette-scope.tokens"
                class="color-fg-default text-semibold"
                style="white-space:nowrap;line-height:20px;"
                >core<span class="color-fg-subtle text-normal">&nbsp;&nbsp;/&nbsp;&nbsp;</span></command-palette-token>
        </command-palette-scope>
        <div class="command-palette-input-group flex-1 form-control border-0 box-shadow-none" style="z-index: 0">
          <div class="command-palette-typeahead position-absolute d-flex flex-items-center Truncate">
            <span class="typeahead-segment input-mirror" data-target="command-palette-input.mirror"></span>
            <span class="Truncate-text" data-target="command-palette-input.typeaheadText"></span>
            <span class="typeahead-segment" data-target="command-palette-input.typeaheadPlaceholder"></span>
          </div>
          <input
            class="js-overlay-input typeahead-input d-none"
            disabled
            tabindex="-1"
            aria-label="Hidden input for typeahead"
          >
          <input
            type="text"
            autocomplete="off"
            autocorrect="off"
            autocapitalize="off"
            spellcheck="false"
            class="js-input typeahead-input form-control border-0 box-shadow-none input-block width-full no-focus-indicator"
            aria-label="Command palette input"
            aria-haspopup="listbox"
            aria-expanded="false"
            aria-autocomplete="list"
            aria-controls="command-palette-page-stack"
            role="combobox"
            data-action="
              input:command-palette-input#onInput
              keydown:command-palette-input#onKeydown
            "
          >
        </div>
          <div data-view-component="true" class="position-relative d-inline-block">
    <button aria-keyshortcuts="Control+Backspace" data-action="click:command-palette-input#onClear keypress:command-palette-input#onClear" data-target="command-palette-input.clearButton" id="command-palette-clear-button" hidden="hidden" type="button" data-view-component="true" class="btn-octicon command-palette-input-clear-button">      <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-x-circle-fill">
    <path d="M2.343 13.657A8 8 0 1 1 13.658 2.343 8 8 0 0 1 2.343 13.657ZM6.03 4.97a.751.751 0 0 0-1.042.018.751.751 0 0 0-.018 1.042L6.94 8 4.97 9.97a.749.749 0 0 0 .326 1.275.749.749 0 0 0 .734-.215L8 9.06l1.97 1.97a.749.749 0 0 0 1.275-.326.749.749 0 0 0-.215-.734L9.06 8l1.97-1.97a.749.749 0 0 0-.326-1.275.749.749 0 0 0-.734.215L8 6.94Z"></path>
</svg>
</button>    <tool-tip id="tooltip-618871ca-7561-49ca-9cea-0a3baef6d206" for="command-palette-clear-button" popover="manual" data-direction="w" data-type="label" data-view-component="true" class="sr-only position-absolute">Clear Command Palette</tool-tip>
</div>
      </command-palette-input>

      <command-palette-page-stack
        data-default-scope-id="MDEwOlJlcG9zaXRvcnkxMjg4ODk5Mw=="
        data-default-scope-type="Repository"
        data-action="command-palette-page-octicons-cached:command-palette-page-stack#cacheOcticons"
      >
          <command-palette-tip
            class="color-fg-muted f6 px-3 py-1 my-2"
              data-scope-types="[&quot;&quot;,&quot;owner&quot;,&quot;repository&quot;]"
            data-mode=""
            data-value="">
            <div class="d-flex flex-items-start flex-justify-between">
              <div>
                <span class="text-bold">Tip:</span>
                  Type <kbd class="hx_kbd">#</kbd> to search pull requests
              </div>
              <div class="ml-2 flex-shrink-0">
                Type <kbd class="hx_kbd">?</kbd> for help and tips
              </div>
            </div>
          </command-palette-tip>
          <command-palette-tip
            class="color-fg-muted f6 px-3 py-1 my-2"
              data-scope-types="[&quot;&quot;,&quot;owner&quot;,&quot;repository&quot;]"
            data-mode=""
            data-value="">
            <div class="d-flex flex-items-start flex-justify-between">
              <div>
                <span class="text-bold">Tip:</span>
                  Type <kbd class="hx_kbd">#</kbd> to search issues
              </div>
              <div class="ml-2 flex-shrink-0">
                Type <kbd class="hx_kbd">?</kbd> for help and tips
              </div>
            </div>
          </command-palette-tip>
          <command-palette-tip
            class="color-fg-muted f6 px-3 py-1 my-2"
              data-scope-types="[&quot;owner&quot;,&quot;repository&quot;]"
            data-mode=""
            data-value="">
            <div class="d-flex flex-items-start flex-justify-between">
              <div>
                <span class="text-bold">Tip:</span>
                  Type <kbd class="hx_kbd">#</kbd> to search discussions
              </div>
              <div class="ml-2 flex-shrink-0">
                Type <kbd class="hx_kbd">?</kbd> for help and tips
              </div>
            </div>
          </command-palette-tip>
          <command-palette-tip
            class="color-fg-muted f6 px-3 py-1 my-2"
              data-scope-types="[&quot;owner&quot;,&quot;repository&quot;]"
            data-mode=""
            data-value="">
            <div class="d-flex flex-items-start flex-justify-between">
              <div>
                <span class="text-bold">Tip:</span>
                  Type <kbd class="hx_kbd">!</kbd> to search projects
              </div>
              <div class="ml-2 flex-shrink-0">
                Type <kbd class="hx_kbd">?</kbd> for help and tips
              </div>
            </div>
          </command-palette-tip>
          <command-palette-tip
            class="color-fg-muted f6 px-3 py-1 my-2"
              data-scope-types="[&quot;owner&quot;]"
            data-mode=""
            data-value="">
            <div class="d-flex flex-items-start flex-justify-between">
              <div>
                <span class="text-bold">Tip:</span>
                  Type <kbd class="hx_kbd">@</kbd> to search teams
              </div>
              <div class="ml-2 flex-shrink-0">
                Type <kbd class="hx_kbd">?</kbd> for help and tips
              </div>
            </div>
          </command-palette-tip>
          <command-palette-tip
            class="color-fg-muted f6 px-3 py-1 my-2"
              data-scope-types="[&quot;&quot;]"
            data-mode=""
            data-value="">
            <div class="d-flex flex-items-start flex-justify-between">
              <div>
                <span class="text-bold">Tip:</span>
                  Type <kbd class="hx_kbd">@</kbd> to search people and organizations
              </div>
              <div class="ml-2 flex-shrink-0">
                Type <kbd class="hx_kbd">?</kbd> for help and tips
              </div>
            </div>
          </command-palette-tip>
          <command-palette-tip
            class="color-fg-muted f6 px-3 py-1 my-2"
              data-scope-types="[&quot;&quot;,&quot;owner&quot;,&quot;repository&quot;]"
            data-mode=""
            data-value="">
            <div class="d-flex flex-items-start flex-justify-between">
              <div>
                <span class="text-bold">Tip:</span>
                  Type <kbd class="hx_kbd">&gt;</kbd> to activate command mode
              </div>
              <div class="ml-2 flex-shrink-0">
                Type <kbd class="hx_kbd">?</kbd> for help and tips
              </div>
            </div>
          </command-palette-tip>
          <command-palette-tip
            class="color-fg-muted f6 px-3 py-1 my-2"
              data-scope-types="[&quot;&quot;,&quot;owner&quot;,&quot;repository&quot;]"
            data-mode=""
            data-value="">
            <div class="d-flex flex-items-start flex-justify-between">
              <div>
                <span class="text-bold">Tip:</span>
                  Go to your accessibility settings to change your keyboard shortcuts
              </div>
              <div class="ml-2 flex-shrink-0">
                Type <kbd class="hx_kbd">?</kbd> for help and tips
              </div>
            </div>
          </command-palette-tip>
          <command-palette-tip
            class="color-fg-muted f6 px-3 py-1 my-2"
              data-scope-types="[&quot;&quot;,&quot;owner&quot;,&quot;repository&quot;]"
            data-mode="#"
            data-value="">
            <div class="d-flex flex-items-start flex-justify-between">
              <div>
                <span class="text-bold">Tip:</span>
                  Type author:@me to search your content
              </div>
              <div class="ml-2 flex-shrink-0">
                Type <kbd class="hx_kbd">?</kbd> for help and tips
              </div>
            </div>
          </command-palette-tip>
          <command-palette-tip
            class="color-fg-muted f6 px-3 py-1 my-2"
              data-scope-types="[&quot;&quot;,&quot;owner&quot;,&quot;repository&quot;]"
            data-mode="#"
            data-value="">
            <div class="d-flex flex-items-start flex-justify-between">
              <div>
                <span class="text-bold">Tip:</span>
                  Type is:pr to filter to pull requests
              </div>
              <div class="ml-2 flex-shrink-0">
                Type <kbd class="hx_kbd">?</kbd> for help and tips
              </div>
            </div>
          </command-palette-tip>
          <command-palette-tip
            class="color-fg-muted f6 px-3 py-1 my-2"
              data-scope-types="[&quot;&quot;,&quot;owner&quot;,&quot;repository&quot;]"
            data-mode="#"
            data-value="">
            <div class="d-flex flex-items-start flex-justify-between">
              <div>
                <span class="text-bold">Tip:</span>
                  Type is:issue to filter to issues
              </div>
              <div class="ml-2 flex-shrink-0">
                Type <kbd class="hx_kbd">?</kbd> for help and tips
              </div>
            </div>
          </command-palette-tip>
          <command-palette-tip
            class="color-fg-muted f6 px-3 py-1 my-2"
              data-scope-types="[&quot;owner&quot;,&quot;repository&quot;]"
            data-mode="#"
            data-value="">
            <div class="d-flex flex-items-start flex-justify-between">
              <div>
                <span class="text-bold">Tip:</span>
                  Type is:project to filter to projects
              </div>
              <div class="ml-2 flex-shrink-0">
                Type <kbd class="hx_kbd">?</kbd> for help and tips
              </div>
            </div>
          </command-palette-tip>
          <command-palette-tip
            class="color-fg-muted f6 px-3 py-1 my-2"
              data-scope-types="[&quot;&quot;,&quot;owner&quot;,&quot;repository&quot;]"
            data-mode="#"
            data-value="">
            <div class="d-flex flex-items-start flex-justify-between">
              <div>
                <span class="text-bold">Tip:</span>
                  Type is:open to filter to open content
              </div>
              <div class="ml-2 flex-shrink-0">
                Type <kbd class="hx_kbd">?</kbd> for help and tips
              </div>
            </div>
          </command-palette-tip>
        <command-palette-tip class="mx-3 my-2 flash flash-error d-flex flex-items-center" data-scope-types="*" data-on-error>
          <div>
            <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-alert">
    <path d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575Zm1.763.707a.25.25 0 0 0-.44 0L1.698 13.132a.25.25 0 0 0 .22.368h12.164a.25.25 0 0 0 .22-.368Zm.53 3.996v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"></path>
</svg>
          </div>
          <div class="px-2">
            We’ve encountered an error and some results aren't available at this time. Type a new search or try again later.
          </div>
        </command-palette-tip>
        <command-palette-tip class="h4 color-fg-default pl-3 pb-2 pt-3" data-on-empty data-scope-types="*" data-match-mode="[^?]|^$">
          No results matched your search
        </command-palette-tip>

        <div hidden>

            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="arrow-right-color-fg-muted">
              <svg height="16" class="octicon octicon-arrow-right color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M8.22 2.97a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042l2.97-2.97H3.75a.75.75 0 0 1 0-1.5h7.44L8.22 4.03a.75.75 0 0 1 0-1.06Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="arrow-right-color-fg-default">
              <svg height="16" class="octicon octicon-arrow-right color-fg-default" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M8.22 2.97a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042l2.97-2.97H3.75a.75.75 0 0 1 0-1.5h7.44L8.22 4.03a.75.75 0 0 1 0-1.06Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="codespaces-color-fg-muted">
              <svg height="16" class="octicon octicon-codespaces color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M0 11.25c0-.966.784-1.75 1.75-1.75h12.5c.966 0 1.75.784 1.75 1.75v3A1.75 1.75 0 0 1 14.25 16H1.75A1.75 1.75 0 0 1 0 14.25Zm2-9.5C2 .784 2.784 0 3.75 0h8.5C13.216 0 14 .784 14 1.75v5a1.75 1.75 0 0 1-1.75 1.75h-8.5A1.75 1.75 0 0 1 2 6.75Zm1.75-.25a.25.25 0 0 0-.25.25v5c0 .138.112.25.25.25h8.5a.25.25 0 0 0 .25-.25v-5a.25.25 0 0 0-.25-.25Zm-2 9.5a.25.25 0 0 0-.25.25v3c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25v-3a.25.25 0 0 0-.25-.25Z"></path><path d="M7 12.75a.75.75 0 0 1 .75-.75h4.5a.75.75 0 0 1 0 1.5h-4.5a.75.75 0 0 1-.75-.75Zm-4 0a.75.75 0 0 1 .75-.75h.5a.75.75 0 0 1 0 1.5h-.5a.75.75 0 0 1-.75-.75Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="copy-color-fg-muted">
              <svg height="16" class="octicon octicon-copy color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="dash-color-fg-muted">
              <svg height="16" class="octicon octicon-dash color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M2 7.75A.75.75 0 0 1 2.75 7h10a.75.75 0 0 1 0 1.5h-10A.75.75 0 0 1 2 7.75Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="file-color-fg-muted">
              <svg height="16" class="octicon octicon-file color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M2 1.75C2 .784 2.784 0 3.75 0h6.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0 1 13.25 16h-9.5A1.75 1.75 0 0 1 2 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25h9.5a.25.25 0 0 0 .25-.25V6h-2.75A1.75 1.75 0 0 1 9 4.25V1.5Zm6.75.062V4.25c0 .138.112.25.25.25h2.688l-.011-.013-2.914-2.914-.013-.011Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="gear-color-fg-muted">
              <svg height="16" class="octicon octicon-gear color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M8 0a8.2 8.2 0 0 1 .701.031C9.444.095 9.99.645 10.16 1.29l.288 1.107c.018.066.079.158.212.224.231.114.454.243.668.386.123.082.233.09.299.071l1.103-.303c.644-.176 1.392.021 1.82.63.27.385.506.792.704 1.218.315.675.111 1.422-.364 1.891l-.814.806c-.049.048-.098.147-.088.294.016.257.016.515 0 .772-.01.147.038.246.088.294l.814.806c.475.469.679 1.216.364 1.891a7.977 7.977 0 0 1-.704 1.217c-.428.61-1.176.807-1.82.63l-1.102-.302c-.067-.019-.177-.011-.3.071a5.909 5.909 0 0 1-.668.386c-.133.066-.194.158-.211.224l-.29 1.106c-.168.646-.715 1.196-1.458 1.26a8.006 8.006 0 0 1-1.402 0c-.743-.064-1.289-.614-1.458-1.26l-.289-1.106c-.018-.066-.079-.158-.212-.224a5.738 5.738 0 0 1-.668-.386c-.123-.082-.233-.09-.299-.071l-1.103.303c-.644.176-1.392-.021-1.82-.63a8.12 8.12 0 0 1-.704-1.218c-.315-.675-.111-1.422.363-1.891l.815-.806c.05-.048.098-.147.088-.294a6.214 6.214 0 0 1 0-.772c.01-.147-.038-.246-.088-.294l-.815-.806C.635 6.045.431 5.298.746 4.623a7.92 7.92 0 0 1 .704-1.217c.428-.61 1.176-.807 1.82-.63l1.102.302c.067.019.177.011.3-.071.214-.143.437-.272.668-.386.133-.066.194-.158.211-.224l.29-1.106C6.009.645 6.556.095 7.299.03 7.53.01 7.764 0 8 0Zm-.571 1.525c-.036.003-.108.036-.137.146l-.289 1.105c-.147.561-.549.967-.998 1.189-.173.086-.34.183-.5.29-.417.278-.97.423-1.529.27l-1.103-.303c-.109-.03-.175.016-.195.045-.22.312-.412.644-.573.99-.014.031-.021.11.059.19l.815.806c.411.406.562.957.53 1.456a4.709 4.709 0 0 0 0 .582c.032.499-.119 1.05-.53 1.456l-.815.806c-.081.08-.073.159-.059.19.162.346.353.677.573.989.02.03.085.076.195.046l1.102-.303c.56-.153 1.113-.008 1.53.27.161.107.328.204.501.29.447.222.85.629.997 1.189l.289 1.105c.029.109.101.143.137.146a6.6 6.6 0 0 0 1.142 0c.036-.003.108-.036.137-.146l.289-1.105c.147-.561.549-.967.998-1.189.173-.086.34-.183.5-.29.417-.278.97-.423 1.529-.27l1.103.303c.109.029.175-.016.195-.045.22-.313.411-.644.573-.99.014-.031.021-.11-.059-.19l-.815-.806c-.411-.406-.562-.957-.53-1.456a4.709 4.709 0 0 0 0-.582c-.032-.499.119-1.05.53-1.456l.815-.806c.081-.08.073-.159.059-.19a6.464 6.464 0 0 0-.573-.989c-.02-.03-.085-.076-.195-.046l-1.102.303c-.56.153-1.113.008-1.53-.27a4.44 4.44 0 0 0-.501-.29c-.447-.222-.85-.629-.997-1.189l-.289-1.105c-.029-.11-.101-.143-.137-.146a6.6 6.6 0 0 0-1.142 0ZM11 8a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM9.5 8a1.5 1.5 0 1 0-3.001.001A1.5 1.5 0 0 0 9.5 8Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="lock-color-fg-muted">
              <svg height="16" class="octicon octicon-lock color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M4 4a4 4 0 0 1 8 0v2h.25c.966 0 1.75.784 1.75 1.75v5.5A1.75 1.75 0 0 1 12.25 15h-8.5A1.75 1.75 0 0 1 2 13.25v-5.5C2 6.784 2.784 6 3.75 6H4Zm8.25 3.5h-8.5a.25.25 0 0 0-.25.25v5.5c0 .138.112.25.25.25h8.5a.25.25 0 0 0 .25-.25v-5.5a.25.25 0 0 0-.25-.25ZM10.5 6V4a2.5 2.5 0 1 0-5 0v2Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="moon-color-fg-muted">
              <svg height="16" class="octicon octicon-moon color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M9.598 1.591a.749.749 0 0 1 .785-.175 7.001 7.001 0 1 1-8.967 8.967.75.75 0 0 1 .961-.96 5.5 5.5 0 0 0 7.046-7.046.75.75 0 0 1 .175-.786Zm1.616 1.945a7 7 0 0 1-7.678 7.678 5.499 5.499 0 1 0 7.678-7.678Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="person-color-fg-muted">
              <svg height="16" class="octicon octicon-person color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M10.561 8.073a6.005 6.005 0 0 1 3.432 5.142.75.75 0 1 1-1.498.07 4.5 4.5 0 0 0-8.99 0 .75.75 0 0 1-1.498-.07 6.004 6.004 0 0 1 3.431-5.142 3.999 3.999 0 1 1 5.123 0ZM10.5 5a2.5 2.5 0 1 0-5 0 2.5 2.5 0 0 0 5 0Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="pencil-color-fg-muted">
              <svg height="16" class="octicon octicon-pencil color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M11.013 1.427a1.75 1.75 0 0 1 2.474 0l1.086 1.086a1.75 1.75 0 0 1 0 2.474l-8.61 8.61c-.21.21-.47.364-.756.445l-3.251.93a.75.75 0 0 1-.927-.928l.929-3.25c.081-.286.235-.547.445-.758l8.61-8.61Zm.176 4.823L9.75 4.81l-6.286 6.287a.253.253 0 0 0-.064.108l-.558 1.953 1.953-.558a.253.253 0 0 0 .108-.064Zm1.238-3.763a.25.25 0 0 0-.354 0L10.811 3.75l1.439 1.44 1.263-1.263a.25.25 0 0 0 0-.354Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="issue-opened-open">
              <svg height="16" class="octicon octicon-issue-opened open" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="git-pull-request-draft-color-fg-muted">
              <svg height="16" class="octicon octicon-git-pull-request-draft color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M3.25 1A2.25 2.25 0 0 1 4 5.372v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.251 2.251 0 0 1 3.25 1Zm9.5 14a2.25 2.25 0 1 1 0-4.5 2.25 2.25 0 0 1 0 4.5ZM2.5 3.25a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0ZM3.25 12a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm9.5 0a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5ZM14 7.5a1.25 1.25 0 1 1-2.5 0 1.25 1.25 0 0 1 2.5 0Zm0-4.25a1.25 1.25 0 1 1-2.5 0 1.25 1.25 0 0 1 2.5 0Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="search-color-fg-muted">
              <svg height="16" class="octicon octicon-search color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M10.68 11.74a6 6 0 0 1-7.922-8.982 6 6 0 0 1 8.982 7.922l3.04 3.04a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215ZM11.5 7a4.499 4.499 0 1 0-8.997 0A4.499 4.499 0 0 0 11.5 7Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="sun-color-fg-muted">
              <svg height="16" class="octicon octicon-sun color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M8 12a4 4 0 1 1 0-8 4 4 0 0 1 0 8Zm0-1.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Zm5.657-8.157a.75.75 0 0 1 0 1.061l-1.061 1.06a.749.749 0 0 1-1.275-.326.749.749 0 0 1 .215-.734l1.06-1.06a.75.75 0 0 1 1.06 0Zm-9.193 9.193a.75.75 0 0 1 0 1.06l-1.06 1.061a.75.75 0 1 1-1.061-1.06l1.06-1.061a.75.75 0 0 1 1.061 0ZM8 0a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0V.75A.75.75 0 0 1 8 0ZM3 8a.75.75 0 0 1-.75.75H.75a.75.75 0 0 1 0-1.5h1.5A.75.75 0 0 1 3 8Zm13 0a.75.75 0 0 1-.75.75h-1.5a.75.75 0 0 1 0-1.5h1.5A.75.75 0 0 1 16 8Zm-8 5a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0v-1.5A.75.75 0 0 1 8 13Zm3.536-1.464a.75.75 0 0 1 1.06 0l1.061 1.06a.75.75 0 0 1-1.06 1.061l-1.061-1.06a.75.75 0 0 1 0-1.061ZM2.343 2.343a.75.75 0 0 1 1.061 0l1.06 1.061a.751.751 0 0 1-.018 1.042.751.751 0 0 1-1.042.018l-1.06-1.06a.75.75 0 0 1 0-1.06Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="sync-color-fg-muted">
              <svg height="16" class="octicon octicon-sync color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M1.705 8.005a.75.75 0 0 1 .834.656 5.5 5.5 0 0 0 9.592 2.97l-1.204-1.204a.25.25 0 0 1 .177-.427h3.646a.25.25 0 0 1 .25.25v3.646a.25.25 0 0 1-.427.177l-1.38-1.38A7.002 7.002 0 0 1 1.05 8.84a.75.75 0 0 1 .656-.834ZM8 2.5a5.487 5.487 0 0 0-4.131 1.869l1.204 1.204A.25.25 0 0 1 4.896 6H1.25A.25.25 0 0 1 1 5.75V2.104a.25.25 0 0 1 .427-.177l1.38 1.38A7.002 7.002 0 0 1 14.95 7.16a.75.75 0 0 1-1.49.178A5.5 5.5 0 0 0 8 2.5Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="trash-color-fg-muted">
              <svg height="16" class="octicon octicon-trash color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M11 1.75V3h2.25a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1 0-1.5H5V1.75C5 .784 5.784 0 6.75 0h2.5C10.216 0 11 .784 11 1.75ZM4.496 6.675l.66 6.6a.25.25 0 0 0 .249.225h5.19a.25.25 0 0 0 .249-.225l.66-6.6a.75.75 0 0 1 1.492.149l-.66 6.6A1.748 1.748 0 0 1 10.595 15h-5.19a1.75 1.75 0 0 1-1.741-1.575l-.66-6.6a.75.75 0 1 1 1.492-.15ZM6.5 1.75V3h3V1.75a.25.25 0 0 0-.25-.25h-2.5a.25.25 0 0 0-.25.25Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="key-color-fg-muted">
              <svg height="16" class="octicon octicon-key color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M10.5 0a5.499 5.499 0 1 1-1.288 10.848l-.932.932a.749.749 0 0 1-.53.22H7v.75a.749.749 0 0 1-.22.53l-.5.5a.749.749 0 0 1-.53.22H5v.75a.749.749 0 0 1-.22.53l-.5.5a.749.749 0 0 1-.53.22h-2A1.75 1.75 0 0 1 0 14.25v-2c0-.199.079-.389.22-.53l4.932-4.932A5.5 5.5 0 0 1 10.5 0Zm-4 5.5c-.001.431.069.86.205 1.269a.75.75 0 0 1-.181.768L1.5 12.56v1.69c0 .138.112.25.25.25h1.69l.06-.06v-1.19a.75.75 0 0 1 .75-.75h1.19l.06-.06v-1.19a.75.75 0 0 1 .75-.75h1.19l1.023-1.025a.75.75 0 0 1 .768-.18A4 4 0 1 0 6.5 5.5ZM11 6a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="comment-discussion-color-fg-muted">
              <svg height="16" class="octicon octicon-comment-discussion color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M1.75 1h8.5c.966 0 1.75.784 1.75 1.75v5.5A1.75 1.75 0 0 1 10.25 10H7.061l-2.574 2.573A1.458 1.458 0 0 1 2 11.543V10h-.25A1.75 1.75 0 0 1 0 8.25v-5.5C0 1.784.784 1 1.75 1ZM1.5 2.75v5.5c0 .138.112.25.25.25h1a.75.75 0 0 1 .75.75v2.19l2.72-2.72a.749.749 0 0 1 .53-.22h3.5a.25.25 0 0 0 .25-.25v-5.5a.25.25 0 0 0-.25-.25h-8.5a.25.25 0 0 0-.25.25Zm13 2a.25.25 0 0 0-.25-.25h-.5a.75.75 0 0 1 0-1.5h.5c.966 0 1.75.784 1.75 1.75v5.5A1.75 1.75 0 0 1 14.25 12H14v1.543a1.458 1.458 0 0 1-2.487 1.03L9.22 12.28a.749.749 0 0 1 .326-1.275.749.749 0 0 1 .734.215l2.22 2.22v-2.19a.75.75 0 0 1 .75-.75h1a.25.25 0 0 0 .25-.25Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="bell-color-fg-muted">
              <svg height="16" class="octicon octicon-bell color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M8 16a2 2 0 0 0 1.985-1.75c.017-.137-.097-.25-.235-.25h-3.5c-.138 0-.252.113-.235.25A2 2 0 0 0 8 16ZM3 5a5 5 0 0 1 10 0v2.947c0 .05.015.098.042.139l1.703 2.555A1.519 1.519 0 0 1 13.482 13H2.518a1.516 1.516 0 0 1-1.263-2.36l1.703-2.554A.255.255 0 0 0 3 7.947Zm5-3.5A3.5 3.5 0 0 0 4.5 5v2.947c0 .346-.102.683-.294.97l-1.703 2.556a.017.017 0 0 0-.003.01l.001.006c0 .002.002.004.004.006l.006.004.007.001h10.964l.007-.001.006-.004.004-.006.001-.007a.017.017 0 0 0-.003-.01l-1.703-2.554a1.745 1.745 0 0 1-.294-.97V5A3.5 3.5 0 0 0 8 1.5Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="bell-slash-color-fg-muted">
              <svg height="16" class="octicon octicon-bell-slash color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="m4.182 4.31.016.011 10.104 7.316.013.01 1.375.996a.75.75 0 1 1-.88 1.214L13.626 13H2.518a1.516 1.516 0 0 1-1.263-2.36l1.703-2.554A.255.255 0 0 0 3 7.947V5.305L.31 3.357a.75.75 0 1 1 .88-1.214Zm7.373 7.19L4.5 6.391v1.556c0 .346-.102.683-.294.97l-1.703 2.556a.017.017 0 0 0-.003.01c0 .005.002.009.005.012l.006.004.007.001ZM8 1.5c-.997 0-1.895.416-2.534 1.086A.75.75 0 1 1 4.38 1.55 5 5 0 0 1 13 5v2.373a.75.75 0 0 1-1.5 0V5A3.5 3.5 0 0 0 8 1.5ZM8 16a2 2 0 0 1-1.985-1.75c-.017-.137.097-.25.235-.25h3.5c.138 0 .252.113.235.25A2 2 0 0 1 8 16Z"></path></svg>
            </div>
            <div data-targets="command-palette-page-stack.localOcticons" data-octicon-id="paintbrush-color-fg-muted">
              <svg height="16" class="octicon octicon-paintbrush color-fg-muted" viewBox="0 0 16 16" version="1.1" width="16" aria-hidden="true"><path d="M11.134 1.535c.7-.509 1.416-.942 2.076-1.155.649-.21 1.463-.267 2.069.34.603.601.568 1.411.368 2.07-.202.668-.624 1.39-1.125 2.096-1.011 1.424-2.496 2.987-3.775 4.249-1.098 1.084-2.132 1.839-3.04 2.3a3.744 3.744 0 0 1-1.055 3.217c-.431.431-1.065.691-1.657.861-.614.177-1.294.287-1.914.357A21.151 21.151 0 0 1 .797 16H.743l.007-.75H.749L.742 16a.75.75 0 0 1-.743-.742l.743-.008-.742.007v-.054a21.25 21.25 0 0 1 .13-2.284c.067-.647.187-1.287.358-1.914.17-.591.43-1.226.86-1.657a3.746 3.746 0 0 1 3.227-1.054c.466-.893 1.225-1.907 2.314-2.982 1.271-1.255 2.833-2.75 4.245-3.777ZM1.62 13.089c-.051.464-.086.929-.104 1.395.466-.018.932-.053 1.396-.104a10.511 10.511 0 0 0 1.668-.309c.526-.151.856-.325 1.011-.48a2.25 2.25 0 1 0-3.182-3.182c-.155.155-.329.485-.48 1.01a10.515 10.515 0 0 0-.309 1.67Zm10.396-10.34c-1.224.89-2.605 2.189-3.822 3.384l1.718 1.718c1.21-1.205 2.51-2.597 3.387-3.833.47-.662.78-1.227.912-1.662.134-.444.032-.551.009-.575h-.001V1.78c-.014-.014-.113-.113-.548.027-.432.14-.995.462-1.655.942Zm-4.832 7.266-.001.001a9.859 9.859 0 0 0 1.63-1.142L7.155 7.216a9.7 9.7 0 0 0-1.161 1.607c.482.302.889.71 1.19 1.192Z"></path></svg>
            </div>

            <command-palette-item-group
              data-group-id="top"
              data-group-title="Top result"
              data-group-hint=""
              data-group-limits="{}"
              data-default-priority="0"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="commands"
              data-group-title="Commands"
              data-group-hint="Type &gt; to filter"
              data-group-limits="{&quot;static_items_page&quot;:50,&quot;issue&quot;:50,&quot;pull_request&quot;:50,&quot;discussion&quot;:50}"
              data-default-priority="1"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="global_commands"
              data-group-title="Global Commands"
              data-group-hint="Type &gt; to filter"
              data-group-limits="{&quot;issue&quot;:0,&quot;pull_request&quot;:0,&quot;discussion&quot;:0}"
              data-default-priority="2"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="this_page"
              data-group-title="This Page"
              data-group-hint=""
              data-group-limits="{}"
              data-default-priority="3"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="files"
              data-group-title="Files"
              data-group-hint=""
              data-group-limits="{}"
              data-default-priority="4"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="default"
              data-group-title="Default"
              data-group-hint=""
              data-group-limits="{&quot;static_items_page&quot;:50}"
              data-default-priority="5"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="pages"
              data-group-title="Pages"
              data-group-hint=""
              data-group-limits="{&quot;repository&quot;:10}"
              data-default-priority="6"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="access_policies"
              data-group-title="Access Policies"
              data-group-hint=""
              data-group-limits="{}"
              data-default-priority="7"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="organizations"
              data-group-title="Organizations"
              data-group-hint=""
              data-group-limits="{}"
              data-default-priority="8"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="repositories"
              data-group-title="Repositories"
              data-group-hint=""
              data-group-limits="{}"
              data-default-priority="9"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="references"
              data-group-title="Issues, pull requests, and discussions"
              data-group-hint="Type # to filter"
              data-group-limits="{}"
              data-default-priority="10"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="teams"
              data-group-title="Teams"
              data-group-hint=""
              data-group-limits="{}"
              data-default-priority="11"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="users"
              data-group-title="Users"
              data-group-hint=""
              data-group-limits="{}"
              data-default-priority="12"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="memex_projects"
              data-group-title="Projects"
              data-group-hint=""
              data-group-limits="{}"
              data-default-priority="13"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="projects"
              data-group-title="Projects (classic)"
              data-group-hint=""
              data-group-limits="{}"
              data-default-priority="14"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="footer"
              data-group-title="Footer"
              data-group-hint=""
              data-group-limits="{}"
              data-default-priority="15"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="modes_help"
              data-group-title="Modes"
              data-group-hint=""
              data-group-limits="{}"
              data-default-priority="16"
            >
            </command-palette-item-group>
            <command-palette-item-group
              data-group-id="filters_help"
              data-group-title="Use filters in issues, pull requests, discussions, and projects"
              data-group-hint=""
              data-group-limits="{}"
              data-default-priority="17"
            >
            </command-palette-item-group>

            <command-palette-page
              data-page-title="home-assistant"
              data-scope-id="MDEyOk9yZ2FuaXphdGlvbjEzODQ0OTc1"
              data-scope-type="owner"
              data-targets="command-palette-page-stack.defaultPages"
              hidden
            >
            </command-palette-page>
            <command-palette-page
              data-page-title="core"
              data-scope-id="MDEwOlJlcG9zaXRvcnkxMjg4ODk5Mw=="
              data-scope-type="repository"
              data-targets="command-palette-page-stack.defaultPages"
              hidden
            >
            </command-palette-page>
        </div>

        <command-palette-page data-is-root>
        </command-palette-page>
          <command-palette-page
            data-page-title="home-assistant"
            data-scope-id="MDEyOk9yZ2FuaXphdGlvbjEzODQ0OTc1"
            data-scope-type="owner"
          >
          </command-palette-page>
          <command-palette-page
            data-page-title="core"
            data-scope-id="MDEwOlJlcG9zaXRvcnkxMjg4ODk5Mw=="
            data-scope-type="repository"
          >
          </command-palette-page>
      </command-palette-page-stack>

      <server-defined-provider data-type="search-links" data-targets="command-palette.serverDefinedProviderElements"></server-defined-provider>
      <server-defined-provider data-type="help" data-targets="command-palette.serverDefinedProviderElements">
          <command-palette-help
            data-group="modes_help"
              data-prefix="#"
              data-scope-types="[&quot;&quot;]"
          >
            <span data-target="command-palette-help.titleElement">Search for <strong>issues</strong> and <strong>pull requests</strong></span>
              <span data-target="command-palette-help.hintElement">
                <kbd class="hx_kbd">#</kbd>
              </span>
          </command-palette-help>
          <command-palette-help
            data-group="modes_help"
              data-prefix="#"
              data-scope-types="[&quot;owner&quot;,&quot;repository&quot;]"
          >
            <span data-target="command-palette-help.titleElement">Search for <strong>issues, pull requests, discussions,</strong> and <strong>projects</strong></span>
              <span data-target="command-palette-help.hintElement">
                <kbd class="hx_kbd">#</kbd>
              </span>
          </command-palette-help>
          <command-palette-help
            data-group="modes_help"
              data-prefix="@"
              data-scope-types="[&quot;&quot;]"
          >
            <span data-target="command-palette-help.titleElement">Search for <strong>organizations, repositories,</strong> and <strong>users</strong></span>
              <span data-target="command-palette-help.hintElement">
                <kbd class="hx_kbd">@</kbd>
              </span>
          </command-palette-help>
          <command-palette-help
            data-group="modes_help"
              data-prefix="!"
              data-scope-types="[&quot;owner&quot;,&quot;repository&quot;]"
          >
            <span data-target="command-palette-help.titleElement">Search for <strong>projects</strong></span>
              <span data-target="command-palette-help.hintElement">
                <kbd class="hx_kbd">!</kbd>
              </span>
          </command-palette-help>
          <command-palette-help
            data-group="modes_help"
              data-prefix="/"
              data-scope-types="[&quot;repository&quot;]"
          >
            <span data-target="command-palette-help.titleElement">Search for <strong>files</strong></span>
              <span data-target="command-palette-help.hintElement">
                <kbd class="hx_kbd">/</kbd>
              </span>
          </command-palette-help>
          <command-palette-help
            data-group="modes_help"
              data-prefix="&gt;"
          >
            <span data-target="command-palette-help.titleElement">Activate <strong>command mode</strong></span>
              <span data-target="command-palette-help.hintElement">
                <kbd class="hx_kbd">&gt;</kbd>
              </span>
          </command-palette-help>
          <command-palette-help
            data-group="filters_help"
              data-prefix="# author:@me"
          >
            <span data-target="command-palette-help.titleElement">Search your issues, pull requests, and discussions</span>
              <span data-target="command-palette-help.hintElement">
                <kbd class="hx_kbd"># author:@me</kbd>
              </span>
          </command-palette-help>
          <command-palette-help
            data-group="filters_help"
              data-prefix="# author:@me"
          >
            <span data-target="command-palette-help.titleElement">Search your issues, pull requests, and discussions</span>
              <span data-target="command-palette-help.hintElement">
                <kbd class="hx_kbd"># author:@me</kbd>
              </span>
          </command-palette-help>
          <command-palette-help
            data-group="filters_help"
              data-prefix="# is:pr"
          >
            <span data-target="command-palette-help.titleElement">Filter to pull requests</span>
              <span data-target="command-palette-help.hintElement">
                <kbd class="hx_kbd"># is:pr</kbd>
              </span>
          </command-palette-help>
          <command-palette-help
            data-group="filters_help"
              data-prefix="# is:issue"
          >
            <span data-target="command-palette-help.titleElement">Filter to issues</span>
              <span data-target="command-palette-help.hintElement">
                <kbd class="hx_kbd"># is:issue</kbd>
              </span>
          </command-palette-help>
          <command-palette-help
            data-group="filters_help"
              data-prefix="# is:discussion"
              data-scope-types="[&quot;owner&quot;,&quot;repository&quot;]"
          >
            <span data-target="command-palette-help.titleElement">Filter to discussions</span>
              <span data-target="command-palette-help.hintElement">
                <kbd class="hx_kbd"># is:discussion</kbd>
              </span>
          </command-palette-help>
          <command-palette-help
            data-group="filters_help"
              data-prefix="# is:project"
              data-scope-types="[&quot;owner&quot;,&quot;repository&quot;]"
          >
            <span data-target="command-palette-help.titleElement">Filter to projects</span>
              <span data-target="command-palette-help.hintElement">
                <kbd class="hx_kbd"># is:project</kbd>
              </span>
          </command-palette-help>
          <command-palette-help
            data-group="filters_help"
              data-prefix="# is:open"
          >
            <span data-target="command-palette-help.titleElement">Filter to open issues, pull requests, and discussions</span>
              <span data-target="command-palette-help.hintElement">
                <kbd class="hx_kbd"># is:open</kbd>
              </span>
          </command-palette-help>
      </server-defined-provider>

        <server-defined-provider
          data-type="commands"
          data-fetch-debounce="0"
            data-src="/command_palette/commands"
          data-supported-modes="[]"
            data-supports-commands
          
          data-targets="command-palette.serverDefinedProviderElements"
          ></server-defined-provider>
        <server-defined-provider
          data-type="prefetched"
          data-fetch-debounce="0"
            data-src="/command_palette/jump_to_page_navigation"
          data-supported-modes="[&quot;&quot;]"
            data-supported-scope-types="[&quot;&quot;,&quot;owner&quot;,&quot;repository&quot;]"
          
          data-targets="command-palette.serverDefinedProviderElements"
          ></server-defined-provider>
        <server-defined-provider
          data-type="remote"
          data-fetch-debounce="200"
            data-src="/command_palette/issues"
          data-supported-modes="[&quot;#&quot;,&quot;#&quot;]"
            data-supported-scope-types="[&quot;owner&quot;,&quot;repository&quot;,&quot;&quot;]"
          
          data-targets="command-palette.serverDefinedProviderElements"
          ></server-defined-provider>
        <server-defined-provider
          data-type="remote"
          data-fetch-debounce="200"
            data-src="/command_palette/jump_to"
          data-supported-modes="[&quot;@&quot;,&quot;@&quot;]"
            data-supported-scope-types="[&quot;&quot;,&quot;owner&quot;]"
          
          data-targets="command-palette.serverDefinedProviderElements"
          ></server-defined-provider>
        <server-defined-provider
          data-type="remote"
          data-fetch-debounce="200"
            data-src="/command_palette/jump_to_members_only"
          data-supported-modes="[&quot;@&quot;,&quot;@&quot;,&quot;&quot;,&quot;&quot;]"
            data-supported-scope-types="[&quot;&quot;,&quot;owner&quot;]"
          
          data-targets="command-palette.serverDefinedProviderElements"
          ></server-defined-provider>
        <server-defined-provider
          data-type="prefetched"
          data-fetch-debounce="0"
            data-src="/command_palette/jump_to_members_only_prefetched"
          data-supported-modes="[&quot;@&quot;,&quot;@&quot;,&quot;&quot;,&quot;&quot;]"
            data-supported-scope-types="[&quot;&quot;,&quot;owner&quot;]"
          
          data-targets="command-palette.serverDefinedProviderElements"
          ></server-defined-provider>
        <server-defined-provider
          data-type="files"
          data-fetch-debounce="0"
            data-src="/command_palette/files"
          data-supported-modes="[&quot;/&quot;]"
            data-supported-scope-types="[&quot;repository&quot;]"
          
          data-targets="command-palette.serverDefinedProviderElements"
          ></server-defined-provider>
        <server-defined-provider
          data-type="remote"
          data-fetch-debounce="200"
            data-src="/command_palette/discussions"
          data-supported-modes="[&quot;#&quot;]"
            data-supported-scope-types="[&quot;owner&quot;,&quot;repository&quot;]"
          
          data-targets="command-palette.serverDefinedProviderElements"
          ></server-defined-provider>
        <server-defined-provider
          data-type="remote"
          data-fetch-debounce="200"
            data-src="/command_palette/projects"
          data-supported-modes="[&quot;#&quot;,&quot;!&quot;]"
            data-supported-scope-types="[&quot;owner&quot;,&quot;repository&quot;]"
          
          data-targets="command-palette.serverDefinedProviderElements"
          ></server-defined-provider>
        <server-defined-provider
          data-type="prefetched"
          data-fetch-debounce="0"
            data-src="/command_palette/recent_issues"
          data-supported-modes="[&quot;#&quot;,&quot;#&quot;]"
            data-supported-scope-types="[&quot;owner&quot;,&quot;repository&quot;,&quot;&quot;]"
          
          data-targets="command-palette.serverDefinedProviderElements"
          ></server-defined-provider>
        <server-defined-provider
          data-type="remote"
          data-fetch-debounce="200"
            data-src="/command_palette/teams"
          data-supported-modes="[&quot;@&quot;,&quot;&quot;]"
            data-supported-scope-types="[&quot;owner&quot;]"
          
          data-targets="command-palette.serverDefinedProviderElements"
          ></server-defined-provider>
        <server-defined-provider
          data-type="remote"
          data-fetch-debounce="200"
            data-src="/command_palette/name_with_owner_repository"
          data-supported-modes="[&quot;@&quot;,&quot;@&quot;,&quot;&quot;,&quot;&quot;]"
            data-supported-scope-types="[&quot;&quot;,&quot;owner&quot;]"
          
          data-targets="command-palette.serverDefinedProviderElements"
          ></server-defined-provider>
    </command-palette>
  </details-dialog>
</details>

<div class="position-fixed bottom-0 left-0 ml-5 mb-5 js-command-palette-toasts" style="z-index: 1000">
  <div hidden class="Toast Toast--loading">
    <span class="Toast-icon">
      <svg class="Toast--spinner" viewBox="0 0 32 32" width="18" height="18" aria-hidden="true">
        <path
          fill="#959da5"
          d="M16 0 A16 16 0 0 0 16 32 A16 16 0 0 0 16 0 M16 4 A12 12 0 0 1 16 28 A12 12 0 0 1 16 4"
        />
        <path fill="#ffffff" d="M16 0 A16 16 0 0 1 32 16 L28 16 A12 12 0 0 0 16 4z"></path>
      </svg>
    </span>
    <span class="Toast-content"></span>
  </div>

  <div hidden class="anim-fade-in fast Toast Toast--error">
    <span class="Toast-icon">
      <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-stop">
    <path d="M4.47.22A.749.749 0 0 1 5 0h6c.199 0 .389.079.53.22l4.25 4.25c.141.14.22.331.22.53v6a.749.749 0 0 1-.22.53l-4.25 4.25A.749.749 0 0 1 11 16H5a.749.749 0 0 1-.53-.22L.22 11.53A.749.749 0 0 1 0 11V5c0-.199.079-.389.22-.53Zm.84 1.28L1.5 5.31v5.38l3.81 3.81h5.38l3.81-3.81V5.31L10.69 1.5ZM8 4a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 8 4Zm0 8a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"></path>
</svg>
    </span>
    <span class="Toast-content"></span>
  </div>

  <div hidden class="anim-fade-in fast Toast Toast--warning">
    <span class="Toast-icon">
      <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-alert">
    <path d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575Zm1.763.707a.25.25 0 0 0-.44 0L1.698 13.132a.25.25 0 0 0 .22.368h12.164a.25.25 0 0 0 .22-.368Zm.53 3.996v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"></path>
</svg>
    </span>
    <span class="Toast-content"></span>
  </div>


  <div hidden class="anim-fade-in fast Toast Toast--success">
    <span class="Toast-icon">
      <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-check">
    <path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path>
</svg>
    </span>
    <span class="Toast-content"></span>
  </div>

  <div hidden class="anim-fade-in fast Toast">
    <span class="Toast-icon">
      <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-info">
    <path d="M0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm8-6.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM6.5 7.75A.75.75 0 0 1 7.25 7h1a.75.75 0 0 1 .75.75v2.75h.25a.75.75 0 0 1 0 1.5h-2a.75.75 0 0 1 0-1.5h.25v-2h-.25a.75.75 0 0 1-.75-.75ZM8 6a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"></path>
</svg>
    </span>
    <span class="Toast-content"></span>
  </div>
</div>


  <div
    class="application-main "
    data-commit-hovercards-enabled
    data-discussion-hovercards-enabled
    data-issue-and-pr-hovercards-enabled
  >
        <div itemscope itemtype="http://schema.org/SoftwareSourceCode" class="">
    <main id="js-repo-pjax-container" >
      
      
      
    

    






    
  <div id="repository-container-header" data-turbo-replace hidden></div>




<turbo-frame id="repo-content-turbo-frame" target="_top" data-turbo-action="advance" class="">
    <div id="repo-content-pjax-container" class="repository-content " >
      <a href="https://github.dev/" class="d-none js-github-dev-shortcut" data-hotkey=".,Alt+Meta+≥,Control+Alt+.">Open in github.dev</a>
  <a href="https://github.dev/" class="d-none js-github-dev-new-tab-shortcut" data-hotkey="Shift+.,Shift+&gt;,&gt;" target="_blank" rel="noopener noreferrer">Open in a new github.dev tab</a>
    <a class="d-none" data-hotkey=",,Alt+Meta+≤,Control+Alt+," target="_blank" href="/codespaces/new/home-assistant/core/tree/2023.10.1?resume=1">Open in codespace</a>



    
      
    





<react-app
  app-name="react-code-view"
  initial-path="/home-assistant/core/blob/2023.10.1/homeassistant/components/mazda/diagnostics.py"
  style="min-height: calc(100vh - 62px)"
  data-ssr="true"
  data-lazy="false"
  data-alternate="false"
>
  
  <script type="application/json" data-target="react-app.embeddedData">{"payload":{"allShortcutsEnabled":true,"fileTree":{"homeassistant/components/mazda":{"items":[{"name":"__init__.py","path":"homeassistant/components/mazda/__init__.py","contentType":"file"},{"name":"binary_sensor.py","path":"homeassistant/components/mazda/binary_sensor.py","contentType":"file"},{"name":"button.py","path":"homeassistant/components/mazda/button.py","contentType":"file"},{"name":"climate.py","path":"homeassistant/components/mazda/climate.py","contentType":"file"},{"name":"config_flow.py","path":"homeassistant/components/mazda/config_flow.py","contentType":"file"},{"name":"const.py","path":"homeassistant/components/mazda/const.py","contentType":"file"},{"name":"device_tracker.py","path":"homeassistant/components/mazda/device_tracker.py","contentType":"file"},{"name":"diagnostics.py","path":"homeassistant/components/mazda/diagnostics.py","contentType":"file"},{"name":"lock.py","path":"homeassistant/components/mazda/lock.py","contentType":"file"},{"name":"manifest.json","path":"homeassistant/components/mazda/manifest.json","contentType":"file"},{"name":"sensor.py","path":"homeassistant/components/mazda/sensor.py","contentType":"file"},{"name":"services.yaml","path":"homeassistant/components/mazda/services.yaml","contentType":"file"},{"name":"strings.json","path":"homeassistant/components/mazda/strings.json","contentType":"file"},{"name":"switch.py","path":"homeassistant/components/mazda/switch.py","contentType":"file"}],"totalCount":14},"homeassistant/components":{"items":[{"name":"3_day_blinds","path":"homeassistant/components/3_day_blinds","contentType":"directory"},{"name":"abode","path":"homeassistant/components/abode","contentType":"directory"},{"name":"accuweather","path":"homeassistant/components/accuweather","contentType":"directory"},{"name":"acer_projector","path":"homeassistant/components/acer_projector","contentType":"directory"},{"name":"acmeda","path":"homeassistant/components/acmeda","contentType":"directory"},{"name":"actiontec","path":"homeassistant/components/actiontec","contentType":"directory"},{"name":"adax","path":"homeassistant/components/adax","contentType":"directory"},{"name":"adguard","path":"homeassistant/components/adguard","contentType":"directory"},{"name":"ads","path":"homeassistant/components/ads","contentType":"directory"},{"name":"advantage_air","path":"homeassistant/components/advantage_air","contentType":"directory"},{"name":"aemet","path":"homeassistant/components/aemet","contentType":"directory"},{"name":"aftership","path":"homeassistant/components/aftership","contentType":"directory"},{"name":"agent_dvr","path":"homeassistant/components/agent_dvr","contentType":"directory"},{"name":"air_quality","path":"homeassistant/components/air_quality","contentType":"directory"},{"name":"airly","path":"homeassistant/components/airly","contentType":"directory"},{"name":"airnow","path":"homeassistant/components/airnow","contentType":"directory"},{"name":"airq","path":"homeassistant/components/airq","contentType":"directory"},{"name":"airthings","path":"homeassistant/components/airthings","contentType":"directory"},{"name":"airthings_ble","path":"homeassistant/components/airthings_ble","contentType":"directory"},{"name":"airtouch4","path":"homeassistant/components/airtouch4","contentType":"directory"},{"name":"airvisual","path":"homeassistant/components/airvisual","contentType":"directory"},{"name":"airvisual_pro","path":"homeassistant/components/airvisual_pro","contentType":"directory"},{"name":"airzone","path":"homeassistant/components/airzone","contentType":"directory"},{"name":"airzone_cloud","path":"homeassistant/components/airzone_cloud","contentType":"directory"},{"name":"aladdin_connect","path":"homeassistant/components/aladdin_connect","contentType":"directory"},{"name":"alarm_control_panel","path":"homeassistant/components/alarm_control_panel","contentType":"directory"},{"name":"alarmdecoder","path":"homeassistant/components/alarmdecoder","contentType":"directory"},{"name":"alert","path":"homeassistant/components/alert","contentType":"directory"},{"name":"alexa","path":"homeassistant/components/alexa","contentType":"directory"},{"name":"alpha_vantage","path":"homeassistant/components/alpha_vantage","contentType":"directory"},{"name":"amazon_polly","path":"homeassistant/components/amazon_polly","contentType":"directory"},{"name":"amberelectric","path":"homeassistant/components/amberelectric","contentType":"directory"},{"name":"ambiclimate","path":"homeassistant/components/ambiclimate","contentType":"directory"},{"name":"ambient_station","path":"homeassistant/components/ambient_station","contentType":"directory"},{"name":"amcrest","path":"homeassistant/components/amcrest","contentType":"directory"},{"name":"amp_motorization","path":"homeassistant/components/amp_motorization","contentType":"directory"},{"name":"ampio","path":"homeassistant/components/ampio","contentType":"directory"},{"name":"analytics","path":"homeassistant/components/analytics","contentType":"directory"},{"name":"android_ip_webcam","path":"homeassistant/components/android_ip_webcam","contentType":"directory"},{"name":"androidtv","path":"homeassistant/components/androidtv","contentType":"directory"},{"name":"androidtv_remote","path":"homeassistant/components/androidtv_remote","contentType":"directory"},{"name":"anel_pwrctrl","path":"homeassistant/components/anel_pwrctrl","contentType":"directory"},{"name":"anova","path":"homeassistant/components/anova","contentType":"directory"},{"name":"anthemav","path":"homeassistant/components/anthemav","contentType":"directory"},{"name":"anwb_energie","path":"homeassistant/components/anwb_energie","contentType":"directory"},{"name":"apache_kafka","path":"homeassistant/components/apache_kafka","contentType":"directory"},{"name":"apcupsd","path":"homeassistant/components/apcupsd","contentType":"directory"},{"name":"api","path":"homeassistant/components/api","contentType":"directory"},{"name":"apple_tv","path":"homeassistant/components/apple_tv","contentType":"directory"},{"name":"application_credentials","path":"homeassistant/components/application_credentials","contentType":"directory"},{"name":"apprise","path":"homeassistant/components/apprise","contentType":"directory"},{"name":"aprs","path":"homeassistant/components/aprs","contentType":"directory"},{"name":"aqualogic","path":"homeassistant/components/aqualogic","contentType":"directory"},{"name":"aquostv","path":"homeassistant/components/aquostv","contentType":"directory"},{"name":"aranet","path":"homeassistant/components/aranet","contentType":"directory"},{"name":"arcam_fmj","path":"homeassistant/components/arcam_fmj","contentType":"directory"},{"name":"arest","path":"homeassistant/components/arest","contentType":"directory"},{"name":"arris_tg2492lg","path":"homeassistant/components/arris_tg2492lg","contentType":"directory"},{"name":"aruba","path":"homeassistant/components/aruba","contentType":"directory"},{"name":"arwn","path":"homeassistant/components/arwn","contentType":"directory"},{"name":"aseko_pool_live","path":"homeassistant/components/aseko_pool_live","contentType":"directory"},{"name":"assist_pipeline","path":"homeassistant/components/assist_pipeline","contentType":"directory"},{"name":"asterisk_cdr","path":"homeassistant/components/asterisk_cdr","contentType":"directory"},{"name":"asterisk_mbox","path":"homeassistant/components/asterisk_mbox","contentType":"directory"},{"name":"asuswrt","path":"homeassistant/components/asuswrt","contentType":"directory"},{"name":"atag","path":"homeassistant/components/atag","contentType":"directory"},{"name":"aten_pe","path":"homeassistant/components/aten_pe","contentType":"directory"},{"name":"atlanticcityelectric","path":"homeassistant/components/atlanticcityelectric","contentType":"directory"},{"name":"atome","path":"homeassistant/components/atome","contentType":"directory"},{"name":"august","path":"homeassistant/components/august","contentType":"directory"},{"name":"august_ble","path":"homeassistant/components/august_ble","contentType":"directory"},{"name":"aurora","path":"homeassistant/components/aurora","contentType":"directory"},{"name":"aurora_abb_powerone","path":"homeassistant/components/aurora_abb_powerone","contentType":"directory"},{"name":"aussie_broadband","path":"homeassistant/components/aussie_broadband","contentType":"directory"},{"name":"auth","path":"homeassistant/components/auth","contentType":"directory"},{"name":"automation","path":"homeassistant/components/automation","contentType":"directory"},{"name":"avea","path":"homeassistant/components/avea","contentType":"directory"},{"name":"avion","path":"homeassistant/components/avion","contentType":"directory"},{"name":"awair","path":"homeassistant/components/awair","contentType":"directory"},{"name":"aws","path":"homeassistant/components/aws","contentType":"directory"},{"name":"axis","path":"homeassistant/components/axis","contentType":"directory"},{"name":"azure_devops","path":"homeassistant/components/azure_devops","contentType":"directory"},{"name":"azure_event_hub","path":"homeassistant/components/azure_event_hub","contentType":"directory"},{"name":"azure_service_bus","path":"homeassistant/components/azure_service_bus","contentType":"directory"},{"name":"backup","path":"homeassistant/components/backup","contentType":"directory"},{"name":"baf","path":"homeassistant/components/baf","contentType":"directory"},{"name":"baidu","path":"homeassistant/components/baidu","contentType":"directory"},{"name":"balboa","path":"homeassistant/components/balboa","contentType":"directory"},{"name":"bayesian","path":"homeassistant/components/bayesian","contentType":"directory"},{"name":"bbox","path":"homeassistant/components/bbox","contentType":"directory"},{"name":"beewi_smartclim","path":"homeassistant/components/beewi_smartclim","contentType":"directory"},{"name":"bge","path":"homeassistant/components/bge","contentType":"directory"},{"name":"binary_sensor","path":"homeassistant/components/binary_sensor","contentType":"directory"},{"name":"bitcoin","path":"homeassistant/components/bitcoin","contentType":"directory"},{"name":"bizkaibus","path":"homeassistant/components/bizkaibus","contentType":"directory"},{"name":"blackbird","path":"homeassistant/components/blackbird","contentType":"directory"},{"name":"blebox","path":"homeassistant/components/blebox","contentType":"directory"},{"name":"blink","path":"homeassistant/components/blink","contentType":"directory"},{"name":"blinksticklight","path":"homeassistant/components/blinksticklight","contentType":"directory"},{"name":"bliss_automation","path":"homeassistant/components/bliss_automation","contentType":"directory"},{"name":"bloc_blinds","path":"homeassistant/components/bloc_blinds","contentType":"directory"},{"name":"blockchain","path":"homeassistant/components/blockchain","contentType":"directory"},{"name":"bloomsky","path":"homeassistant/components/bloomsky","contentType":"directory"},{"name":"bluemaestro","path":"homeassistant/components/bluemaestro","contentType":"directory"},{"name":"blueprint","path":"homeassistant/components/blueprint","contentType":"directory"},{"name":"bluesound","path":"homeassistant/components/bluesound","contentType":"directory"},{"name":"bluetooth","path":"homeassistant/components/bluetooth","contentType":"directory"},{"name":"bluetooth_adapters","path":"homeassistant/components/bluetooth_adapters","contentType":"directory"},{"name":"bluetooth_le_tracker","path":"homeassistant/components/bluetooth_le_tracker","contentType":"directory"},{"name":"bluetooth_tracker","path":"homeassistant/components/bluetooth_tracker","contentType":"directory"},{"name":"bmw_connected_drive","path":"homeassistant/components/bmw_connected_drive","contentType":"directory"},{"name":"bond","path":"homeassistant/components/bond","contentType":"directory"},{"name":"bosch_shc","path":"homeassistant/components/bosch_shc","contentType":"directory"},{"name":"brandt","path":"homeassistant/components/brandt","contentType":"directory"},{"name":"braviatv","path":"homeassistant/components/braviatv","contentType":"directory"},{"name":"brel_home","path":"homeassistant/components/brel_home","contentType":"directory"},{"name":"broadlink","path":"homeassistant/components/broadlink","contentType":"directory"},{"name":"brother","path":"homeassistant/components/brother","contentType":"directory"},{"name":"brottsplatskartan","path":"homeassistant/components/brottsplatskartan","contentType":"directory"},{"name":"browser","path":"homeassistant/components/browser","contentType":"directory"},{"name":"brunt","path":"homeassistant/components/brunt","contentType":"directory"},{"name":"bsblan","path":"homeassistant/components/bsblan","contentType":"directory"},{"name":"bswitch","path":"homeassistant/components/bswitch","contentType":"directory"},{"name":"bt_home_hub_5","path":"homeassistant/components/bt_home_hub_5","contentType":"directory"},{"name":"bt_smarthub","path":"homeassistant/components/bt_smarthub","contentType":"directory"},{"name":"bthome","path":"homeassistant/components/bthome","contentType":"directory"},{"name":"bticino","path":"homeassistant/components/bticino","contentType":"directory"},{"name":"bubendorff","path":"homeassistant/components/bubendorff","contentType":"directory"},{"name":"buienradar","path":"homeassistant/components/buienradar","contentType":"directory"},{"name":"button","path":"homeassistant/components/button","contentType":"directory"},{"name":"caldav","path":"homeassistant/components/caldav","contentType":"directory"},{"name":"calendar","path":"homeassistant/components/calendar","contentType":"directory"},{"name":"camera","path":"homeassistant/components/camera","contentType":"directory"},{"name":"canary","path":"homeassistant/components/canary","contentType":"directory"},{"name":"cast","path":"homeassistant/components/cast","contentType":"directory"},{"name":"cert_expiry","path":"homeassistant/components/cert_expiry","contentType":"directory"},{"name":"channels","path":"homeassistant/components/channels","contentType":"directory"},{"name":"circuit","path":"homeassistant/components/circuit","contentType":"directory"},{"name":"cisco_ios","path":"homeassistant/components/cisco_ios","contentType":"directory"},{"name":"cisco_mobility_express","path":"homeassistant/components/cisco_mobility_express","contentType":"directory"},{"name":"cisco_webex_teams","path":"homeassistant/components/cisco_webex_teams","contentType":"directory"},{"name":"citybikes","path":"homeassistant/components/citybikes","contentType":"directory"},{"name":"clementine","path":"homeassistant/components/clementine","contentType":"directory"},{"name":"clickatell","path":"homeassistant/components/clickatell","contentType":"directory"},{"name":"clicksend","path":"homeassistant/components/clicksend","contentType":"directory"},{"name":"clicksend_tts","path":"homeassistant/components/clicksend_tts","contentType":"directory"},{"name":"climate","path":"homeassistant/components/climate","contentType":"directory"},{"name":"cloud","path":"homeassistant/components/cloud","contentType":"directory"},{"name":"cloudflare","path":"homeassistant/components/cloudflare","contentType":"directory"},{"name":"cmus","path":"homeassistant/components/cmus","contentType":"directory"},{"name":"co2signal","path":"homeassistant/components/co2signal","contentType":"directory"},{"name":"coinbase","path":"homeassistant/components/coinbase","contentType":"directory"},{"name":"color_extractor","path":"homeassistant/components/color_extractor","contentType":"directory"},{"name":"comed","path":"homeassistant/components/comed","contentType":"directory"},{"name":"comed_hourly_pricing","path":"homeassistant/components/comed_hourly_pricing","contentType":"directory"},{"name":"comelit","path":"homeassistant/components/comelit","contentType":"directory"},{"name":"comfoconnect","path":"homeassistant/components/comfoconnect","contentType":"directory"},{"name":"command_line","path":"homeassistant/components/command_line","contentType":"directory"},{"name":"compensation","path":"homeassistant/components/compensation","contentType":"directory"},{"name":"concord232","path":"homeassistant/components/concord232","contentType":"directory"},{"name":"coned","path":"homeassistant/components/coned","contentType":"directory"},{"name":"config","path":"homeassistant/components/config","contentType":"directory"},{"name":"configurator","path":"homeassistant/components/configurator","contentType":"directory"},{"name":"control4","path":"homeassistant/components/control4","contentType":"directory"},{"name":"conversation","path":"homeassistant/components/conversation","contentType":"directory"},{"name":"coolmaster","path":"homeassistant/components/coolmaster","contentType":"directory"},{"name":"counter","path":"homeassistant/components/counter","contentType":"directory"},{"name":"cover","path":"homeassistant/components/cover","contentType":"directory"},{"name":"cozytouch","path":"homeassistant/components/cozytouch","contentType":"directory"},{"name":"cppm_tracker","path":"homeassistant/components/cppm_tracker","contentType":"directory"},{"name":"cpuspeed","path":"homeassistant/components/cpuspeed","contentType":"directory"},{"name":"crownstone","path":"homeassistant/components/crownstone","contentType":"directory"},{"name":"cups","path":"homeassistant/components/cups","contentType":"directory"},{"name":"currencylayer","path":"homeassistant/components/currencylayer","contentType":"directory"},{"name":"dacia","path":"homeassistant/components/dacia","contentType":"directory"},{"name":"daikin","path":"homeassistant/components/daikin","contentType":"directory"},{"name":"danfoss_air","path":"homeassistant/components/danfoss_air","contentType":"directory"},{"name":"datadog","path":"homeassistant/components/datadog","contentType":"directory"},{"name":"date","path":"homeassistant/components/date","contentType":"directory"},{"name":"datetime","path":"homeassistant/components/datetime","contentType":"directory"},{"name":"ddwrt","path":"homeassistant/components/ddwrt","contentType":"directory"},{"name":"debugpy","path":"homeassistant/components/debugpy","contentType":"directory"},{"name":"deconz","path":"homeassistant/components/deconz","contentType":"directory"},{"name":"decora","path":"homeassistant/components/decora","contentType":"directory"},{"name":"decora_wifi","path":"homeassistant/components/decora_wifi","contentType":"directory"},{"name":"default_config","path":"homeassistant/components/default_config","contentType":"directory"},{"name":"delijn","path":"homeassistant/components/delijn","contentType":"directory"},{"name":"delmarva","path":"homeassistant/components/delmarva","contentType":"directory"},{"name":"deluge","path":"homeassistant/components/deluge","contentType":"directory"},{"name":"demo","path":"homeassistant/components/demo","contentType":"directory"},{"name":"denon","path":"homeassistant/components/denon","contentType":"directory"},{"name":"denonavr","path":"homeassistant/components/denonavr","contentType":"directory"},{"name":"derivative","path":"homeassistant/components/derivative","contentType":"directory"},{"name":"device_automation","path":"homeassistant/components/device_automation","contentType":"directory"},{"name":"device_sun_light_trigger","path":"homeassistant/components/device_sun_light_trigger","contentType":"directory"},{"name":"device_tracker","path":"homeassistant/components/device_tracker","contentType":"directory"},{"name":"devolo_home_control","path":"homeassistant/components/devolo_home_control","contentType":"directory"},{"name":"devolo_home_network","path":"homeassistant/components/devolo_home_network","contentType":"directory"},{"name":"dexcom","path":"homeassistant/components/dexcom","contentType":"directory"},{"name":"dhcp","path":"homeassistant/components/dhcp","contentType":"directory"},{"name":"diagnostics","path":"homeassistant/components/diagnostics","contentType":"directory"},{"name":"dialogflow","path":"homeassistant/components/dialogflow","contentType":"directory"},{"name":"diaz","path":"homeassistant/components/diaz","contentType":"directory"},{"name":"digital_loggers","path":"homeassistant/components/digital_loggers","contentType":"directory"},{"name":"digital_ocean","path":"homeassistant/components/digital_ocean","contentType":"directory"},{"name":"directv","path":"homeassistant/components/directv","contentType":"directory"},{"name":"discogs","path":"homeassistant/components/discogs","contentType":"directory"},{"name":"discord","path":"homeassistant/components/discord","contentType":"directory"},{"name":"discovergy","path":"homeassistant/components/discovergy","contentType":"directory"},{"name":"dlib_face_detect","path":"homeassistant/components/dlib_face_detect","contentType":"directory"},{"name":"dlib_face_identify","path":"homeassistant/components/dlib_face_identify","contentType":"directory"},{"name":"dlink","path":"homeassistant/components/dlink","contentType":"directory"},{"name":"dlna_dmr","path":"homeassistant/components/dlna_dmr","contentType":"directory"},{"name":"dlna_dms","path":"homeassistant/components/dlna_dms","contentType":"directory"},{"name":"dnsip","path":"homeassistant/components/dnsip","contentType":"directory"},{"name":"dominos","path":"homeassistant/components/dominos","contentType":"directory"},{"name":"doods","path":"homeassistant/components/doods","contentType":"directory"},{"name":"doorbird","path":"homeassistant/components/doorbird","contentType":"directory"},{"name":"dooya","path":"homeassistant/components/dooya","contentType":"directory"},{"name":"dormakaba_dkey","path":"homeassistant/components/dormakaba_dkey","contentType":"directory"},{"name":"dovado","path":"homeassistant/components/dovado","contentType":"directory"},{"name":"downloader","path":"homeassistant/components/downloader","contentType":"directory"},{"name":"dremel_3d_printer","path":"homeassistant/components/dremel_3d_printer","contentType":"directory"},{"name":"dsmr","path":"homeassistant/components/dsmr","contentType":"directory"},{"name":"dsmr_reader","path":"homeassistant/components/dsmr_reader","contentType":"directory"},{"name":"dte_energy_bridge","path":"homeassistant/components/dte_energy_bridge","contentType":"directory"},{"name":"dublin_bus_transport","path":"homeassistant/components/dublin_bus_transport","contentType":"directory"},{"name":"duckdns","path":"homeassistant/components/duckdns","contentType":"directory"},{"name":"dunehd","path":"homeassistant/components/dunehd","contentType":"directory"},{"name":"duotecno","path":"homeassistant/components/duotecno","contentType":"directory"},{"name":"dwd_weather_warnings","path":"homeassistant/components/dwd_weather_warnings","contentType":"directory"},{"name":"dweet","path":"homeassistant/components/dweet","contentType":"directory"},{"name":"dynalite","path":"homeassistant/components/dynalite","contentType":"directory"},{"name":"eafm","path":"homeassistant/components/eafm","contentType":"directory"},{"name":"easyenergy","path":"homeassistant/components/easyenergy","contentType":"directory"},{"name":"ebox","path":"homeassistant/components/ebox","contentType":"directory"},{"name":"ebusd","path":"homeassistant/components/ebusd","contentType":"directory"},{"name":"ecoal_boiler","path":"homeassistant/components/ecoal_boiler","contentType":"directory"},{"name":"ecobee","path":"homeassistant/components/ecobee","contentType":"directory"},{"name":"ecoforest","path":"homeassistant/components/ecoforest","contentType":"directory"},{"name":"econet","path":"homeassistant/components/econet","contentType":"directory"},{"name":"ecovacs","path":"homeassistant/components/ecovacs","contentType":"directory"},{"name":"ecowitt","path":"homeassistant/components/ecowitt","contentType":"directory"},{"name":"eddystone_temperature","path":"homeassistant/components/eddystone_temperature","contentType":"directory"},{"name":"edimax","path":"homeassistant/components/edimax","contentType":"directory"},{"name":"edl21","path":"homeassistant/components/edl21","contentType":"directory"},{"name":"efergy","path":"homeassistant/components/efergy","contentType":"directory"},{"name":"egardia","path":"homeassistant/components/egardia","contentType":"directory"},{"name":"eight_sleep","path":"homeassistant/components/eight_sleep","contentType":"directory"},{"name":"electrasmart","path":"homeassistant/components/electrasmart","contentType":"directory"},{"name":"electric_kiwi","path":"homeassistant/components/electric_kiwi","contentType":"directory"},{"name":"elgato","path":"homeassistant/components/elgato","contentType":"directory"},{"name":"eliqonline","path":"homeassistant/components/eliqonline","contentType":"directory"},{"name":"elkm1","path":"homeassistant/components/elkm1","contentType":"directory"},{"name":"elmax","path":"homeassistant/components/elmax","contentType":"directory"},{"name":"elv","path":"homeassistant/components/elv","contentType":"directory"},{"name":"emby","path":"homeassistant/components/emby","contentType":"directory"},{"name":"emoncms","path":"homeassistant/components/emoncms","contentType":"directory"},{"name":"emoncms_history","path":"homeassistant/components/emoncms_history","contentType":"directory"},{"name":"emonitor","path":"homeassistant/components/emonitor","contentType":"directory"},{"name":"emulated_hue","path":"homeassistant/components/emulated_hue","contentType":"directory"},{"name":"emulated_kasa","path":"homeassistant/components/emulated_kasa","contentType":"directory"},{"name":"emulated_roku","path":"homeassistant/components/emulated_roku","contentType":"directory"},{"name":"energie_vanons","path":"homeassistant/components/energie_vanons","contentType":"directory"},{"name":"energy","path":"homeassistant/components/energy","contentType":"directory"},{"name":"energyzero","path":"homeassistant/components/energyzero","contentType":"directory"},{"name":"enigma2","path":"homeassistant/components/enigma2","contentType":"directory"},{"name":"enmax","path":"homeassistant/components/enmax","contentType":"directory"},{"name":"enocean","path":"homeassistant/components/enocean","contentType":"directory"},{"name":"enphase_envoy","path":"homeassistant/components/enphase_envoy","contentType":"directory"},{"name":"entur_public_transport","path":"homeassistant/components/entur_public_transport","contentType":"directory"},{"name":"environment_canada","path":"homeassistant/components/environment_canada","contentType":"directory"},{"name":"envisalink","path":"homeassistant/components/envisalink","contentType":"directory"},{"name":"ephember","path":"homeassistant/components/ephember","contentType":"directory"},{"name":"epson","path":"homeassistant/components/epson","contentType":"directory"},{"name":"epsonworkforce","path":"homeassistant/components/epsonworkforce","contentType":"directory"},{"name":"eq3btsmart","path":"homeassistant/components/eq3btsmart","contentType":"directory"},{"name":"escea","path":"homeassistant/components/escea","contentType":"directory"},{"name":"esera_onewire","path":"homeassistant/components/esera_onewire","contentType":"directory"},{"name":"esphome","path":"homeassistant/components/esphome","contentType":"directory"},{"name":"etherscan","path":"homeassistant/components/etherscan","contentType":"directory"},{"name":"eufy","path":"homeassistant/components/eufy","contentType":"directory"},{"name":"eufylife_ble","path":"homeassistant/components/eufylife_ble","contentType":"directory"},{"name":"event","path":"homeassistant/components/event","contentType":"directory"},{"name":"evergy","path":"homeassistant/components/evergy","contentType":"directory"},{"name":"everlights","path":"homeassistant/components/everlights","contentType":"directory"},{"name":"evil_genius_labs","path":"homeassistant/components/evil_genius_labs","contentType":"directory"},{"name":"evohome","path":"homeassistant/components/evohome","contentType":"directory"},{"name":"ezviz","path":"homeassistant/components/ezviz","contentType":"directory"},{"name":"faa_delays","path":"homeassistant/components/faa_delays","contentType":"directory"},{"name":"facebook","path":"homeassistant/components/facebook","contentType":"directory"},{"name":"facebox","path":"homeassistant/components/facebox","contentType":"directory"},{"name":"fail2ban","path":"homeassistant/components/fail2ban","contentType":"directory"},{"name":"familyhub","path":"homeassistant/components/familyhub","contentType":"directory"},{"name":"fan","path":"homeassistant/components/fan","contentType":"directory"},{"name":"fastdotcom","path":"homeassistant/components/fastdotcom","contentType":"directory"},{"name":"feedreader","path":"homeassistant/components/feedreader","contentType":"directory"},{"name":"ffmpeg","path":"homeassistant/components/ffmpeg","contentType":"directory"},{"name":"ffmpeg_motion","path":"homeassistant/components/ffmpeg_motion","contentType":"directory"},{"name":"ffmpeg_noise","path":"homeassistant/components/ffmpeg_noise","contentType":"directory"},{"name":"fibaro","path":"homeassistant/components/fibaro","contentType":"directory"},{"name":"fido","path":"homeassistant/components/fido","contentType":"directory"},{"name":"file","path":"homeassistant/components/file","contentType":"directory"},{"name":"file_upload","path":"homeassistant/components/file_upload","contentType":"directory"},{"name":"filesize","path":"homeassistant/components/filesize","contentType":"directory"},{"name":"filter","path":"homeassistant/components/filter","contentType":"directory"},{"name":"fints","path":"homeassistant/components/fints","contentType":"directory"},{"name":"fire_tv","path":"homeassistant/components/fire_tv","contentType":"directory"},{"name":"fireservicerota","path":"homeassistant/components/fireservicerota","contentType":"directory"},{"name":"firmata","path":"homeassistant/components/firmata","contentType":"directory"},{"name":"fitbit","path":"homeassistant/components/fitbit","contentType":"directory"},{"name":"fivem","path":"homeassistant/components/fivem","contentType":"directory"},{"name":"fixer","path":"homeassistant/components/fixer","contentType":"directory"},{"name":"fjaraskupan","path":"homeassistant/components/fjaraskupan","contentType":"directory"},{"name":"fleetgo","path":"homeassistant/components/fleetgo","contentType":"directory"},{"name":"flexit","path":"homeassistant/components/flexit","contentType":"directory"},{"name":"flexom","path":"homeassistant/components/flexom","contentType":"directory"},{"name":"flic","path":"homeassistant/components/flic","contentType":"directory"},{"name":"flick_electric","path":"homeassistant/components/flick_electric","contentType":"directory"},{"name":"flipr","path":"homeassistant/components/flipr","contentType":"directory"},{"name":"flo","path":"homeassistant/components/flo","contentType":"directory"},{"name":"flock","path":"homeassistant/components/flock","contentType":"directory"},{"name":"flume","path":"homeassistant/components/flume","contentType":"directory"},{"name":"flux","path":"homeassistant/components/flux","contentType":"directory"},{"name":"flux_led","path":"homeassistant/components/flux_led","contentType":"directory"},{"name":"folder","path":"homeassistant/components/folder","contentType":"directory"},{"name":"folder_watcher","path":"homeassistant/components/folder_watcher","contentType":"directory"},{"name":"foobot","path":"homeassistant/components/foobot","contentType":"directory"},{"name":"forecast_solar","path":"homeassistant/components/forecast_solar","contentType":"directory"},{"name":"forked_daapd","path":"homeassistant/components/forked_daapd","contentType":"directory"},{"name":"fortios","path":"homeassistant/components/fortios","contentType":"directory"},{"name":"foscam","path":"homeassistant/components/foscam","contentType":"directory"},{"name":"foursquare","path":"homeassistant/components/foursquare","contentType":"directory"},{"name":"free_mobile","path":"homeassistant/components/free_mobile","contentType":"directory"},{"name":"freebox","path":"homeassistant/components/freebox","contentType":"directory"},{"name":"freedns","path":"homeassistant/components/freedns","contentType":"directory"},{"name":"freedompro","path":"homeassistant/components/freedompro","contentType":"directory"},{"name":"fritz","path":"homeassistant/components/fritz","contentType":"directory"},{"name":"fritzbox","path":"homeassistant/components/fritzbox","contentType":"directory"},{"name":"fritzbox_callmonitor","path":"homeassistant/components/fritzbox_callmonitor","contentType":"directory"},{"name":"fronius","path":"homeassistant/components/fronius","contentType":"directory"},{"name":"frontend","path":"homeassistant/components/frontend","contentType":"directory"},{"name":"frontier_silicon","path":"homeassistant/components/frontier_silicon","contentType":"directory"},{"name":"fully_kiosk","path":"homeassistant/components/fully_kiosk","contentType":"directory"},{"name":"futurenow","path":"homeassistant/components/futurenow","contentType":"directory"},{"name":"garadget","path":"homeassistant/components/garadget","contentType":"directory"},{"name":"garages_amsterdam","path":"homeassistant/components/garages_amsterdam","contentType":"directory"},{"name":"gardena_bluetooth","path":"homeassistant/components/gardena_bluetooth","contentType":"directory"},{"name":"gaviota","path":"homeassistant/components/gaviota","contentType":"directory"},{"name":"gc100","path":"homeassistant/components/gc100","contentType":"directory"},{"name":"gdacs","path":"homeassistant/components/gdacs","contentType":"directory"},{"name":"generic","path":"homeassistant/components/generic","contentType":"directory"},{"name":"generic_hygrostat","path":"homeassistant/components/generic_hygrostat","contentType":"directory"},{"name":"generic_thermostat","path":"homeassistant/components/generic_thermostat","contentType":"directory"},{"name":"geniushub","path":"homeassistant/components/geniushub","contentType":"directory"},{"name":"geo_json_events","path":"homeassistant/components/geo_json_events","contentType":"directory"},{"name":"geo_location","path":"homeassistant/components/geo_location","contentType":"directory"},{"name":"geo_rss_events","path":"homeassistant/components/geo_rss_events","contentType":"directory"},{"name":"geocaching","path":"homeassistant/components/geocaching","contentType":"directory"},{"name":"geofency","path":"homeassistant/components/geofency","contentType":"directory"},{"name":"geonetnz_quakes","path":"homeassistant/components/geonetnz_quakes","contentType":"directory"},{"name":"geonetnz_volcano","path":"homeassistant/components/geonetnz_volcano","contentType":"directory"},{"name":"gios","path":"homeassistant/components/gios","contentType":"directory"},{"name":"github","path":"homeassistant/components/github","contentType":"directory"},{"name":"gitlab_ci","path":"homeassistant/components/gitlab_ci","contentType":"directory"},{"name":"gitter","path":"homeassistant/components/gitter","contentType":"directory"},{"name":"glances","path":"homeassistant/components/glances","contentType":"directory"},{"name":"goalzero","path":"homeassistant/components/goalzero","contentType":"directory"},{"name":"gogogate2","path":"homeassistant/components/gogogate2","contentType":"directory"},{"name":"goodwe","path":"homeassistant/components/goodwe","contentType":"directory"},{"name":"google","path":"homeassistant/components/google","contentType":"directory"},{"name":"google_assistant","path":"homeassistant/components/google_assistant","contentType":"directory"},{"name":"google_assistant_sdk","path":"homeassistant/components/google_assistant_sdk","contentType":"directory"},{"name":"google_cloud","path":"homeassistant/components/google_cloud","contentType":"directory"},{"name":"google_domains","path":"homeassistant/components/google_domains","contentType":"directory"},{"name":"google_generative_ai_conversation","path":"homeassistant/components/google_generative_ai_conversation","contentType":"directory"},{"name":"google_mail","path":"homeassistant/components/google_mail","contentType":"directory"},{"name":"google_maps","path":"homeassistant/components/google_maps","contentType":"directory"},{"name":"google_pubsub","path":"homeassistant/components/google_pubsub","contentType":"directory"},{"name":"google_sheets","path":"homeassistant/components/google_sheets","contentType":"directory"},{"name":"google_translate","path":"homeassistant/components/google_translate","contentType":"directory"},{"name":"google_travel_time","path":"homeassistant/components/google_travel_time","contentType":"directory"},{"name":"google_wifi","path":"homeassistant/components/google_wifi","contentType":"directory"},{"name":"govee_ble","path":"homeassistant/components/govee_ble","contentType":"directory"},{"name":"gpsd","path":"homeassistant/components/gpsd","contentType":"directory"},{"name":"gpslogger","path":"homeassistant/components/gpslogger","contentType":"directory"},{"name":"graphite","path":"homeassistant/components/graphite","contentType":"directory"},{"name":"gree","path":"homeassistant/components/gree","contentType":"directory"},{"name":"greeneye_monitor","path":"homeassistant/components/greeneye_monitor","contentType":"directory"},{"name":"greenwave","path":"homeassistant/components/greenwave","contentType":"directory"},{"name":"group","path":"homeassistant/components/group","contentType":"directory"},{"name":"growatt_server","path":"homeassistant/components/growatt_server","contentType":"directory"},{"name":"gstreamer","path":"homeassistant/components/gstreamer","contentType":"directory"},{"name":"gtfs","path":"homeassistant/components/gtfs","contentType":"directory"},{"name":"guardian","path":"homeassistant/components/guardian","contentType":"directory"},{"name":"habitica","path":"homeassistant/components/habitica","contentType":"directory"},{"name":"hardkernel","path":"homeassistant/components/hardkernel","contentType":"directory"},{"name":"hardware","path":"homeassistant/components/hardware","contentType":"directory"},{"name":"harman_kardon_avr","path":"homeassistant/components/harman_kardon_avr","contentType":"directory"},{"name":"harmony","path":"homeassistant/components/harmony","contentType":"directory"},{"name":"hassio","path":"homeassistant/components/hassio","contentType":"directory"},{"name":"havana_shade","path":"homeassistant/components/havana_shade","contentType":"directory"},{"name":"haveibeenpwned","path":"homeassistant/components/haveibeenpwned","contentType":"directory"},{"name":"hddtemp","path":"homeassistant/components/hddtemp","contentType":"directory"},{"name":"hdmi_cec","path":"homeassistant/components/hdmi_cec","contentType":"directory"},{"name":"heatmiser","path":"homeassistant/components/heatmiser","contentType":"directory"},{"name":"heiwa","path":"homeassistant/components/heiwa","contentType":"directory"},{"name":"heos","path":"homeassistant/components/heos","contentType":"directory"},{"name":"here_travel_time","path":"homeassistant/components/here_travel_time","contentType":"directory"},{"name":"hexaom","path":"homeassistant/components/hexaom","contentType":"directory"},{"name":"hi_kumo","path":"homeassistant/components/hi_kumo","contentType":"directory"},{"name":"hikvision","path":"homeassistant/components/hikvision","contentType":"directory"},{"name":"hikvisioncam","path":"homeassistant/components/hikvisioncam","contentType":"directory"},{"name":"hisense_aehw4a1","path":"homeassistant/components/hisense_aehw4a1","contentType":"directory"},{"name":"history","path":"homeassistant/components/history","contentType":"directory"},{"name":"history_stats","path":"homeassistant/components/history_stats","contentType":"directory"},{"name":"hitron_coda","path":"homeassistant/components/hitron_coda","contentType":"directory"},{"name":"hive","path":"homeassistant/components/hive","contentType":"directory"},{"name":"hlk_sw16","path":"homeassistant/components/hlk_sw16","contentType":"directory"},{"name":"home_connect","path":"homeassistant/components/home_connect","contentType":"directory"},{"name":"home_plus_control","path":"homeassistant/components/home_plus_control","contentType":"directory"},{"name":"homeassistant","path":"homeassistant/components/homeassistant","contentType":"directory"},{"name":"homeassistant_alerts","path":"homeassistant/components/homeassistant_alerts","contentType":"directory"},{"name":"homeassistant_green","path":"homeassistant/components/homeassistant_green","contentType":"directory"},{"name":"homeassistant_hardware","path":"homeassistant/components/homeassistant_hardware","contentType":"directory"},{"name":"homeassistant_sky_connect","path":"homeassistant/components/homeassistant_sky_connect","contentType":"directory"},{"name":"homeassistant_yellow","path":"homeassistant/components/homeassistant_yellow","contentType":"directory"},{"name":"homekit","path":"homeassistant/components/homekit","contentType":"directory"},{"name":"homekit_controller","path":"homeassistant/components/homekit_controller","contentType":"directory"},{"name":"homematic","path":"homeassistant/components/homematic","contentType":"directory"},{"name":"homematicip_cloud","path":"homeassistant/components/homematicip_cloud","contentType":"directory"},{"name":"homewizard","path":"homeassistant/components/homewizard","contentType":"directory"},{"name":"homeworks","path":"homeassistant/components/homeworks","contentType":"directory"},{"name":"honeywell","path":"homeassistant/components/honeywell","contentType":"directory"},{"name":"horizon","path":"homeassistant/components/horizon","contentType":"directory"},{"name":"hp_ilo","path":"homeassistant/components/hp_ilo","contentType":"directory"},{"name":"html5","path":"homeassistant/components/html5","contentType":"directory"},{"name":"http","path":"homeassistant/components/http","contentType":"directory"},{"name":"huawei_lte","path":"homeassistant/components/huawei_lte","contentType":"directory"},{"name":"hue","path":"homeassistant/components/hue","contentType":"directory"},{"name":"huisbaasje","path":"homeassistant/components/huisbaasje","contentType":"directory"},{"name":"humidifier","path":"homeassistant/components/humidifier","contentType":"directory"},{"name":"hunterdouglas_powerview","path":"homeassistant/components/hunterdouglas_powerview","contentType":"directory"},{"name":"hurrican_shutters_wholesale","path":"homeassistant/components/hurrican_shutters_wholesale","contentType":"directory"},{"name":"hvv_departures","path":"homeassistant/components/hvv_departures","contentType":"directory"},{"name":"hydrawise","path":"homeassistant/components/hydrawise","contentType":"directory"},{"name":"hyperion","path":"homeassistant/components/hyperion","contentType":"directory"},{"name":"ialarm","path":"homeassistant/components/ialarm","contentType":"directory"},{"name":"iammeter","path":"homeassistant/components/iammeter","contentType":"directory"},{"name":"iaqualink","path":"homeassistant/components/iaqualink","contentType":"directory"},{"name":"ibeacon","path":"homeassistant/components/ibeacon","contentType":"directory"},{"name":"icloud","path":"homeassistant/components/icloud","contentType":"directory"},{"name":"idasen_desk","path":"homeassistant/components/idasen_desk","contentType":"directory"},{"name":"idteck_prox","path":"homeassistant/components/idteck_prox","contentType":"directory"},{"name":"ifttt","path":"homeassistant/components/ifttt","contentType":"directory"},{"name":"iglo","path":"homeassistant/components/iglo","contentType":"directory"},{"name":"ign_sismologia","path":"homeassistant/components/ign_sismologia","contentType":"directory"},{"name":"ihc","path":"homeassistant/components/ihc","contentType":"directory"},{"name":"image","path":"homeassistant/components/image","contentType":"directory"},{"name":"image_processing","path":"homeassistant/components/image_processing","contentType":"directory"},{"name":"image_upload","path":"homeassistant/components/image_upload","contentType":"directory"},{"name":"imap","path":"homeassistant/components/imap","contentType":"directory"},{"name":"imap_email_content","path":"homeassistant/components/imap_email_content","contentType":"directory"},{"name":"incomfort","path":"homeassistant/components/incomfort","contentType":"directory"},{"name":"influxdb","path":"homeassistant/components/influxdb","contentType":"directory"},{"name":"inkbird","path":"homeassistant/components/inkbird","contentType":"directory"},{"name":"input_boolean","path":"homeassistant/components/input_boolean","contentType":"directory"},{"name":"input_button","path":"homeassistant/components/input_button","contentType":"directory"},{"name":"input_datetime","path":"homeassistant/components/input_datetime","contentType":"directory"},{"name":"input_number","path":"homeassistant/components/input_number","contentType":"directory"},{"name":"input_select","path":"homeassistant/components/input_select","contentType":"directory"},{"name":"input_text","path":"homeassistant/components/input_text","contentType":"directory"},{"name":"inspired_shades","path":"homeassistant/components/inspired_shades","contentType":"directory"},{"name":"insteon","path":"homeassistant/components/insteon","contentType":"directory"},{"name":"integration","path":"homeassistant/components/integration","contentType":"directory"},{"name":"intellifire","path":"homeassistant/components/intellifire","contentType":"directory"},{"name":"intent","path":"homeassistant/components/intent","contentType":"directory"},{"name":"intent_script","path":"homeassistant/components/intent_script","contentType":"directory"},{"name":"intesishome","path":"homeassistant/components/intesishome","contentType":"directory"},{"name":"ios","path":"homeassistant/components/ios","contentType":"directory"},{"name":"iotawatt","path":"homeassistant/components/iotawatt","contentType":"directory"},{"name":"iperf3","path":"homeassistant/components/iperf3","contentType":"directory"},{"name":"ipma","path":"homeassistant/components/ipma","contentType":"directory"},{"name":"ipp","path":"homeassistant/components/ipp","contentType":"directory"},{"name":"iqvia","path":"homeassistant/components/iqvia","contentType":"directory"},{"name":"irish_rail_transport","path":"homeassistant/components/irish_rail_transport","contentType":"directory"},{"name":"islamic_prayer_times","path":"homeassistant/components/islamic_prayer_times","contentType":"directory"},{"name":"ismartwindow","path":"homeassistant/components/ismartwindow","contentType":"directory"},{"name":"iss","path":"homeassistant/components/iss","contentType":"directory"},{"name":"isy994","path":"homeassistant/components/isy994","contentType":"directory"},{"name":"itach","path":"homeassistant/components/itach","contentType":"directory"},{"name":"itunes","path":"homeassistant/components/itunes","contentType":"directory"},{"name":"izone","path":"homeassistant/components/izone","contentType":"directory"},{"name":"jellyfin","path":"homeassistant/components/jellyfin","contentType":"directory"},{"name":"jewish_calendar","path":"homeassistant/components/jewish_calendar","contentType":"directory"},{"name":"joaoapps_join","path":"homeassistant/components/joaoapps_join","contentType":"directory"},{"name":"juicenet","path":"homeassistant/components/juicenet","contentType":"directory"},{"name":"justnimbus","path":"homeassistant/components/justnimbus","contentType":"directory"},{"name":"jvc_projector","path":"homeassistant/components/jvc_projector","contentType":"directory"},{"name":"kaiterra","path":"homeassistant/components/kaiterra","contentType":"directory"},{"name":"kaleidescape","path":"homeassistant/components/kaleidescape","contentType":"directory"},{"name":"kankun","path":"homeassistant/components/kankun","contentType":"directory"},{"name":"keba","path":"homeassistant/components/keba","contentType":"directory"},{"name":"keenetic_ndms2","path":"homeassistant/components/keenetic_ndms2","contentType":"directory"},{"name":"kef","path":"homeassistant/components/kef","contentType":"directory"},{"name":"kegtron","path":"homeassistant/components/kegtron","contentType":"directory"},{"name":"keyboard","path":"homeassistant/components/keyboard","contentType":"directory"},{"name":"keyboard_remote","path":"homeassistant/components/keyboard_remote","contentType":"directory"},{"name":"keymitt_ble","path":"homeassistant/components/keymitt_ble","contentType":"directory"},{"name":"kira","path":"homeassistant/components/kira","contentType":"directory"},{"name":"kitchen_sink","path":"homeassistant/components/kitchen_sink","contentType":"directory"},{"name":"kiwi","path":"homeassistant/components/kiwi","contentType":"directory"},{"name":"kmtronic","path":"homeassistant/components/kmtronic","contentType":"directory"},{"name":"knx","path":"homeassistant/components/knx","contentType":"directory"},{"name":"kodi","path":"homeassistant/components/kodi","contentType":"directory"},{"name":"konnected","path":"homeassistant/components/konnected","contentType":"directory"},{"name":"kostal_plenticore","path":"homeassistant/components/kostal_plenticore","contentType":"directory"},{"name":"kraken","path":"homeassistant/components/kraken","contentType":"directory"},{"name":"kulersky","path":"homeassistant/components/kulersky","contentType":"directory"},{"name":"kwb","path":"homeassistant/components/kwb","contentType":"directory"},{"name":"lacrosse","path":"homeassistant/components/lacrosse","contentType":"directory"},{"name":"lacrosse_view","path":"homeassistant/components/lacrosse_view","contentType":"directory"},{"name":"lametric","path":"homeassistant/components/lametric","contentType":"directory"},{"name":"landisgyr_heat_meter","path":"homeassistant/components/landisgyr_heat_meter","contentType":"directory"},{"name":"lannouncer","path":"homeassistant/components/lannouncer","contentType":"directory"},{"name":"lastfm","path":"homeassistant/components/lastfm","contentType":"directory"},{"name":"launch_library","path":"homeassistant/components/launch_library","contentType":"directory"},{"name":"laundrify","path":"homeassistant/components/laundrify","contentType":"directory"},{"name":"lawn_mower","path":"homeassistant/components/lawn_mower","contentType":"directory"},{"name":"lcn","path":"homeassistant/components/lcn","contentType":"directory"},{"name":"ld2410_ble","path":"homeassistant/components/ld2410_ble","contentType":"directory"},{"name":"led_ble","path":"homeassistant/components/led_ble","contentType":"directory"},{"name":"legrand","path":"homeassistant/components/legrand","contentType":"directory"},{"name":"lg_netcast","path":"homeassistant/components/lg_netcast","contentType":"directory"},{"name":"lg_soundbar","path":"homeassistant/components/lg_soundbar","contentType":"directory"},{"name":"lidarr","path":"homeassistant/components/lidarr","contentType":"directory"},{"name":"life360","path":"homeassistant/components/life360","contentType":"directory"},{"name":"lifx","path":"homeassistant/components/lifx","contentType":"directory"},{"name":"lifx_cloud","path":"homeassistant/components/lifx_cloud","contentType":"directory"},{"name":"light","path":"homeassistant/components/light","contentType":"directory"},{"name":"lightwave","path":"homeassistant/components/lightwave","contentType":"directory"},{"name":"limitlessled","path":"homeassistant/components/limitlessled","contentType":"directory"},{"name":"linksys_smart","path":"homeassistant/components/linksys_smart","contentType":"directory"},{"name":"linode","path":"homeassistant/components/linode","contentType":"directory"},{"name":"linux_battery","path":"homeassistant/components/linux_battery","contentType":"directory"},{"name":"lirc","path":"homeassistant/components/lirc","contentType":"directory"},{"name":"litejet","path":"homeassistant/components/litejet","contentType":"directory"},{"name":"litterrobot","path":"homeassistant/components/litterrobot","contentType":"directory"},{"name":"livisi","path":"homeassistant/components/livisi","contentType":"directory"},{"name":"llamalab_automate","path":"homeassistant/components/llamalab_automate","contentType":"directory"},{"name":"local_calendar","path":"homeassistant/components/local_calendar","contentType":"directory"},{"name":"local_file","path":"homeassistant/components/local_file","contentType":"directory"},{"name":"local_ip","path":"homeassistant/components/local_ip","contentType":"directory"},{"name":"locative","path":"homeassistant/components/locative","contentType":"directory"},{"name":"lock","path":"homeassistant/components/lock","contentType":"directory"},{"name":"logbook","path":"homeassistant/components/logbook","contentType":"directory"},{"name":"logentries","path":"homeassistant/components/logentries","contentType":"directory"},{"name":"logger","path":"homeassistant/components/logger","contentType":"directory"},{"name":"logi_circle","path":"homeassistant/components/logi_circle","contentType":"directory"},{"name":"london_air","path":"homeassistant/components/london_air","contentType":"directory"},{"name":"london_underground","path":"homeassistant/components/london_underground","contentType":"directory"},{"name":"lookin","path":"homeassistant/components/lookin","contentType":"directory"},{"name":"loqed","path":"homeassistant/components/loqed","contentType":"directory"},{"name":"lovelace","path":"homeassistant/components/lovelace","contentType":"directory"},{"name":"luci","path":"homeassistant/components/luci","contentType":"directory"},{"name":"luftdaten","path":"homeassistant/components/luftdaten","contentType":"directory"},{"name":"lupusec","path":"homeassistant/components/lupusec","contentType":"directory"},{"name":"lutron","path":"homeassistant/components/lutron","contentType":"directory"},{"name":"lutron_caseta","path":"homeassistant/components/lutron_caseta","contentType":"directory"},{"name":"luxaflex","path":"homeassistant/components/luxaflex","contentType":"directory"},{"name":"lw12wifi","path":"homeassistant/components/lw12wifi","contentType":"directory"},{"name":"lyric","path":"homeassistant/components/lyric","contentType":"directory"},{"name":"mailbox","path":"homeassistant/components/mailbox","contentType":"directory"},{"name":"mailgun","path":"homeassistant/components/mailgun","contentType":"directory"},{"name":"manual","path":"homeassistant/components/manual","contentType":"directory"},{"name":"manual_mqtt","path":"homeassistant/components/manual_mqtt","contentType":"directory"},{"name":"map","path":"homeassistant/components/map","contentType":"directory"},{"name":"marantz","path":"homeassistant/components/marantz","contentType":"directory"},{"name":"martec","path":"homeassistant/components/martec","contentType":"directory"},{"name":"marytts","path":"homeassistant/components/marytts","contentType":"directory"},{"name":"mastodon","path":"homeassistant/components/mastodon","contentType":"directory"},{"name":"matrix","path":"homeassistant/components/matrix","contentType":"directory"},{"name":"matter","path":"homeassistant/components/matter","contentType":"directory"},{"name":"maxcube","path":"homeassistant/components/maxcube","contentType":"directory"},{"name":"mazda","path":"homeassistant/components/mazda","contentType":"directory"},{"name":"meater","path":"homeassistant/components/meater","contentType":"directory"},{"name":"medcom_ble","path":"homeassistant/components/medcom_ble","contentType":"directory"},{"name":"media_extractor","path":"homeassistant/components/media_extractor","contentType":"directory"},{"name":"media_player","path":"homeassistant/components/media_player","contentType":"directory"},{"name":"media_source","path":"homeassistant/components/media_source","contentType":"directory"},{"name":"mediaroom","path":"homeassistant/components/mediaroom","contentType":"directory"},{"name":"melcloud","path":"homeassistant/components/melcloud","contentType":"directory"},{"name":"melissa","path":"homeassistant/components/melissa","contentType":"directory"},{"name":"melnor","path":"homeassistant/components/melnor","contentType":"directory"},{"name":"meraki","path":"homeassistant/components/meraki","contentType":"directory"},{"name":"message_bird","path":"homeassistant/components/message_bird","contentType":"directory"},{"name":"met","path":"homeassistant/components/met","contentType":"directory"},{"name":"met_eireann","path":"homeassistant/components/met_eireann","contentType":"directory"},{"name":"meteo_france","path":"homeassistant/components/meteo_france","contentType":"directory"},{"name":"meteoalarm","path":"homeassistant/components/meteoalarm","contentType":"directory"},{"name":"meteoclimatic","path":"homeassistant/components/meteoclimatic","contentType":"directory"},{"name":"metoffice","path":"homeassistant/components/metoffice","contentType":"directory"},{"name":"mfi","path":"homeassistant/components/mfi","contentType":"directory"},{"name":"microsoft","path":"homeassistant/components/microsoft","contentType":"directory"},{"name":"microsoft_face","path":"homeassistant/components/microsoft_face","contentType":"directory"},{"name":"microsoft_face_detect","path":"homeassistant/components/microsoft_face_detect","contentType":"directory"},{"name":"microsoft_face_identify","path":"homeassistant/components/microsoft_face_identify","contentType":"directory"},{"name":"mijndomein_energie","path":"homeassistant/components/mijndomein_energie","contentType":"directory"},{"name":"mikrotik","path":"homeassistant/components/mikrotik","contentType":"directory"},{"name":"mill","path":"homeassistant/components/mill","contentType":"directory"},{"name":"min_max","path":"homeassistant/components/min_max","contentType":"directory"},{"name":"minecraft_server","path":"homeassistant/components/minecraft_server","contentType":"directory"},{"name":"minio","path":"homeassistant/components/minio","contentType":"directory"},{"name":"mjpeg","path":"homeassistant/components/mjpeg","contentType":"directory"},{"name":"moat","path":"homeassistant/components/moat","contentType":"directory"},{"name":"mobile_app","path":"homeassistant/components/mobile_app","contentType":"directory"},{"name":"mochad","path":"homeassistant/components/mochad","contentType":"directory"},{"name":"modbus","path":"homeassistant/components/modbus","contentType":"directory"},{"name":"modem_callerid","path":"homeassistant/components/modem_callerid","contentType":"directory"},{"name":"modern_forms","path":"homeassistant/components/modern_forms","contentType":"directory"},{"name":"moehlenhoff_alpha2","path":"homeassistant/components/moehlenhoff_alpha2","contentType":"directory"},{"name":"mold_indicator","path":"homeassistant/components/mold_indicator","contentType":"directory"},{"name":"monessen","path":"homeassistant/components/monessen","contentType":"directory"},{"name":"monoprice","path":"homeassistant/components/monoprice","contentType":"directory"},{"name":"moon","path":"homeassistant/components/moon","contentType":"directory"},{"name":"mopeka","path":"homeassistant/components/mopeka","contentType":"directory"},{"name":"motion_blinds","path":"homeassistant/components/motion_blinds","contentType":"directory"},{"name":"motioneye","path":"homeassistant/components/motioneye","contentType":"directory"},{"name":"mpd","path":"homeassistant/components/mpd","contentType":"directory"},{"name":"mqtt","path":"homeassistant/components/mqtt","contentType":"directory"},{"name":"mqtt_eventstream","path":"homeassistant/components/mqtt_eventstream","contentType":"directory"},{"name":"mqtt_json","path":"homeassistant/components/mqtt_json","contentType":"directory"},{"name":"mqtt_room","path":"homeassistant/components/mqtt_room","contentType":"directory"},{"name":"mqtt_statestream","path":"homeassistant/components/mqtt_statestream","contentType":"directory"},{"name":"msteams","path":"homeassistant/components/msteams","contentType":"directory"},{"name":"mullvad","path":"homeassistant/components/mullvad","contentType":"directory"},{"name":"mutesync","path":"homeassistant/components/mutesync","contentType":"directory"},{"name":"mvglive","path":"homeassistant/components/mvglive","contentType":"directory"},{"name":"my","path":"homeassistant/components/my","contentType":"directory"},{"name":"mycroft","path":"homeassistant/components/mycroft","contentType":"directory"},{"name":"myq","path":"homeassistant/components/myq","contentType":"directory"},{"name":"mysensors","path":"homeassistant/components/mysensors","contentType":"directory"},{"name":"mystrom","path":"homeassistant/components/mystrom","contentType":"directory"},{"name":"mythicbeastsdns","path":"homeassistant/components/mythicbeastsdns","contentType":"directory"},{"name":"nad","path":"homeassistant/components/nad","contentType":"directory"},{"name":"nam","path":"homeassistant/components/nam","contentType":"directory"},{"name":"namecheapdns","path":"homeassistant/components/namecheapdns","contentType":"directory"},{"name":"nanoleaf","path":"homeassistant/components/nanoleaf","contentType":"directory"},{"name":"neato","path":"homeassistant/components/neato","contentType":"directory"},{"name":"nederlandse_spoorwegen","path":"homeassistant/components/nederlandse_spoorwegen","contentType":"directory"},{"name":"ness_alarm","path":"homeassistant/components/ness_alarm","contentType":"directory"},{"name":"nest","path":"homeassistant/components/nest","contentType":"directory"},{"name":"netatmo","path":"homeassistant/components/netatmo","contentType":"directory"},{"name":"netdata","path":"homeassistant/components/netdata","contentType":"directory"},{"name":"netgear","path":"homeassistant/components/netgear","contentType":"directory"},{"name":"netgear_lte","path":"homeassistant/components/netgear_lte","contentType":"directory"},{"name":"netio","path":"homeassistant/components/netio","contentType":"directory"},{"name":"network","path":"homeassistant/components/network","contentType":"directory"},{"name":"neurio_energy","path":"homeassistant/components/neurio_energy","contentType":"directory"},{"name":"nexia","path":"homeassistant/components/nexia","contentType":"directory"},{"name":"nexity","path":"homeassistant/components/nexity","contentType":"directory"},{"name":"nextbus","path":"homeassistant/components/nextbus","contentType":"directory"},{"name":"nextcloud","path":"homeassistant/components/nextcloud","contentType":"directory"},{"name":"nextdns","path":"homeassistant/components/nextdns","contentType":"directory"},{"name":"nfandroidtv","path":"homeassistant/components/nfandroidtv","contentType":"directory"},{"name":"nibe_heatpump","path":"homeassistant/components/nibe_heatpump","contentType":"directory"},{"name":"nightscout","path":"homeassistant/components/nightscout","contentType":"directory"},{"name":"niko_home_control","path":"homeassistant/components/niko_home_control","contentType":"directory"},{"name":"nilu","path":"homeassistant/components/nilu","contentType":"directory"},{"name":"nina","path":"homeassistant/components/nina","contentType":"directory"},{"name":"nissan_leaf","path":"homeassistant/components/nissan_leaf","contentType":"directory"},{"name":"nmap_tracker","path":"homeassistant/components/nmap_tracker","contentType":"directory"},{"name":"nmbs","path":"homeassistant/components/nmbs","contentType":"directory"},{"name":"no_ip","path":"homeassistant/components/no_ip","contentType":"directory"},{"name":"noaa_tides","path":"homeassistant/components/noaa_tides","contentType":"directory"},{"name":"nobo_hub","path":"homeassistant/components/nobo_hub","contentType":"directory"},{"name":"norway_air","path":"homeassistant/components/norway_air","contentType":"directory"},{"name":"notify","path":"homeassistant/components/notify","contentType":"directory"},{"name":"notify_events","path":"homeassistant/components/notify_events","contentType":"directory"},{"name":"notion","path":"homeassistant/components/notion","contentType":"directory"},{"name":"nsw_fuel_station","path":"homeassistant/components/nsw_fuel_station","contentType":"directory"},{"name":"nsw_rural_fire_service_feed","path":"homeassistant/components/nsw_rural_fire_service_feed","contentType":"directory"},{"name":"nuheat","path":"homeassistant/components/nuheat","contentType":"directory"},{"name":"nuki","path":"homeassistant/components/nuki","contentType":"directory"},{"name":"numato","path":"homeassistant/components/numato","contentType":"directory"},{"name":"number","path":"homeassistant/components/number","contentType":"directory"},{"name":"nut","path":"homeassistant/components/nut","contentType":"directory"},{"name":"nutrichef","path":"homeassistant/components/nutrichef","contentType":"directory"},{"name":"nws","path":"homeassistant/components/nws","contentType":"directory"},{"name":"nx584","path":"homeassistant/components/nx584","contentType":"directory"},{"name":"nzbget","path":"homeassistant/components/nzbget","contentType":"directory"},{"name":"oasa_telematics","path":"homeassistant/components/oasa_telematics","contentType":"directory"},{"name":"obihai","path":"homeassistant/components/obihai","contentType":"directory"},{"name":"octoprint","path":"homeassistant/components/octoprint","contentType":"directory"},{"name":"oem","path":"homeassistant/components/oem","contentType":"directory"},{"name":"ohmconnect","path":"homeassistant/components/ohmconnect","contentType":"directory"},{"name":"ombi","path":"homeassistant/components/ombi","contentType":"directory"},{"name":"omnilogic","path":"homeassistant/components/omnilogic","contentType":"directory"},{"name":"onboarding","path":"homeassistant/components/onboarding","contentType":"directory"},{"name":"oncue","path":"homeassistant/components/oncue","contentType":"directory"},{"name":"ondilo_ico","path":"homeassistant/components/ondilo_ico","contentType":"directory"},{"name":"onewire","path":"homeassistant/components/onewire","contentType":"directory"},{"name":"onkyo","path":"homeassistant/components/onkyo","contentType":"directory"},{"name":"onvif","path":"homeassistant/components/onvif","contentType":"directory"},{"name":"open_meteo","path":"homeassistant/components/open_meteo","contentType":"directory"},{"name":"openai_conversation","path":"homeassistant/components/openai_conversation","contentType":"directory"},{"name":"openalpr_cloud","path":"homeassistant/components/openalpr_cloud","contentType":"directory"},{"name":"opencv","path":"homeassistant/components/opencv","contentType":"directory"},{"name":"openerz","path":"homeassistant/components/openerz","contentType":"directory"},{"name":"openevse","path":"homeassistant/components/openevse","contentType":"directory"},{"name":"openexchangerates","path":"homeassistant/components/openexchangerates","contentType":"directory"},{"name":"opengarage","path":"homeassistant/components/opengarage","contentType":"directory"},{"name":"openhardwaremonitor","path":"homeassistant/components/openhardwaremonitor","contentType":"directory"},{"name":"openhome","path":"homeassistant/components/openhome","contentType":"directory"},{"name":"opensensemap","path":"homeassistant/components/opensensemap","contentType":"directory"},{"name":"opensky","path":"homeassistant/components/opensky","contentType":"directory"},{"name":"opentherm_gw","path":"homeassistant/components/opentherm_gw","contentType":"directory"},{"name":"openuv","path":"homeassistant/components/openuv","contentType":"directory"},{"name":"openweathermap","path":"homeassistant/components/openweathermap","contentType":"directory"},{"name":"opnsense","path":"homeassistant/components/opnsense","contentType":"directory"},{"name":"opower","path":"homeassistant/components/opower","contentType":"directory"},{"name":"opple","path":"homeassistant/components/opple","contentType":"directory"},{"name":"oralb","path":"homeassistant/components/oralb","contentType":"directory"},{"name":"oru","path":"homeassistant/components/oru","contentType":"directory"},{"name":"oru_opower","path":"homeassistant/components/oru_opower","contentType":"directory"},{"name":"orvibo","path":"homeassistant/components/orvibo","contentType":"directory"},{"name":"osramlightify","path":"homeassistant/components/osramlightify","contentType":"directory"},{"name":"otbr","path":"homeassistant/components/otbr","contentType":"directory"},{"name":"otp","path":"homeassistant/components/otp","contentType":"directory"},{"name":"overkiz","path":"homeassistant/components/overkiz","contentType":"directory"},{"name":"ovo_energy","path":"homeassistant/components/ovo_energy","contentType":"directory"},{"name":"owntracks","path":"homeassistant/components/owntracks","contentType":"directory"},{"name":"p1_monitor","path":"homeassistant/components/p1_monitor","contentType":"directory"},{"name":"panasonic_bluray","path":"homeassistant/components/panasonic_bluray","contentType":"directory"},{"name":"panasonic_viera","path":"homeassistant/components/panasonic_viera","contentType":"directory"},{"name":"pandora","path":"homeassistant/components/pandora","contentType":"directory"},{"name":"panel_custom","path":"homeassistant/components/panel_custom","contentType":"directory"},{"name":"panel_iframe","path":"homeassistant/components/panel_iframe","contentType":"directory"},{"name":"pcs_lighting","path":"homeassistant/components/pcs_lighting","contentType":"directory"},{"name":"peco","path":"homeassistant/components/peco","contentType":"directory"},{"name":"peco_opower","path":"homeassistant/components/peco_opower","contentType":"directory"},{"name":"pegel_online","path":"homeassistant/components/pegel_online","contentType":"directory"},{"name":"pencom","path":"homeassistant/components/pencom","contentType":"directory"},{"name":"pepco","path":"homeassistant/components/pepco","contentType":"directory"},{"name":"persistent_notification","path":"homeassistant/components/persistent_notification","contentType":"directory"},{"name":"person","path":"homeassistant/components/person","contentType":"directory"},{"name":"pge","path":"homeassistant/components/pge","contentType":"directory"},{"name":"philips_js","path":"homeassistant/components/philips_js","contentType":"directory"},{"name":"pi_hole","path":"homeassistant/components/pi_hole","contentType":"directory"},{"name":"picnic","path":"homeassistant/components/picnic","contentType":"directory"},{"name":"picotts","path":"homeassistant/components/picotts","contentType":"directory"},{"name":"pilight","path":"homeassistant/components/pilight","contentType":"directory"},{"name":"ping","path":"homeassistant/components/ping","contentType":"directory"},{"name":"pioneer","path":"homeassistant/components/pioneer","contentType":"directory"},{"name":"piper","path":"homeassistant/components/piper","contentType":"directory"},{"name":"pjlink","path":"homeassistant/components/pjlink","contentType":"directory"},{"name":"plaato","path":"homeassistant/components/plaato","contentType":"directory"},{"name":"plant","path":"homeassistant/components/plant","contentType":"directory"},{"name":"plex","path":"homeassistant/components/plex","contentType":"directory"},{"name":"plugwise","path":"homeassistant/components/plugwise","contentType":"directory"},{"name":"plum_lightpad","path":"homeassistant/components/plum_lightpad","contentType":"directory"},{"name":"pocketcasts","path":"homeassistant/components/pocketcasts","contentType":"directory"},{"name":"point","path":"homeassistant/components/point","contentType":"directory"},{"name":"poolsense","path":"homeassistant/components/poolsense","contentType":"directory"},{"name":"powerwall","path":"homeassistant/components/powerwall","contentType":"directory"},{"name":"private_ble_device","path":"homeassistant/components/private_ble_device","contentType":"directory"},{"name":"profiler","path":"homeassistant/components/profiler","contentType":"directory"},{"name":"progettihwsw","path":"homeassistant/components/progettihwsw","contentType":"directory"},{"name":"proliphix","path":"homeassistant/components/proliphix","contentType":"directory"},{"name":"prometheus","path":"homeassistant/components/prometheus","contentType":"directory"},{"name":"prosegur","path":"homeassistant/components/prosegur","contentType":"directory"},{"name":"prowl","path":"homeassistant/components/prowl","contentType":"directory"},{"name":"proximity","path":"homeassistant/components/proximity","contentType":"directory"},{"name":"proxmoxve","path":"homeassistant/components/proxmoxve","contentType":"directory"},{"name":"proxy","path":"homeassistant/components/proxy","contentType":"directory"},{"name":"prusalink","path":"homeassistant/components/prusalink","contentType":"directory"},{"name":"ps4","path":"homeassistant/components/ps4","contentType":"directory"},{"name":"pse","path":"homeassistant/components/pse","contentType":"directory"},{"name":"pulseaudio_loopback","path":"homeassistant/components/pulseaudio_loopback","contentType":"directory"},{"name":"pure_energie","path":"homeassistant/components/pure_energie","contentType":"directory"},{"name":"purpleair","path":"homeassistant/components/purpleair","contentType":"directory"},{"name":"push","path":"homeassistant/components/push","contentType":"directory"},{"name":"pushbullet","path":"homeassistant/components/pushbullet","contentType":"directory"},{"name":"pushover","path":"homeassistant/components/pushover","contentType":"directory"},{"name":"pushsafer","path":"homeassistant/components/pushsafer","contentType":"directory"},{"name":"pvoutput","path":"homeassistant/components/pvoutput","contentType":"directory"},{"name":"pvpc_hourly_pricing","path":"homeassistant/components/pvpc_hourly_pricing","contentType":"directory"},{"name":"pyload","path":"homeassistant/components/pyload","contentType":"directory"},{"name":"python_script","path":"homeassistant/components/python_script","contentType":"directory"},{"name":"qbittorrent","path":"homeassistant/components/qbittorrent","contentType":"directory"},{"name":"qingping","path":"homeassistant/components/qingping","contentType":"directory"},{"name":"qld_bushfire","path":"homeassistant/components/qld_bushfire","contentType":"directory"},{"name":"qnap","path":"homeassistant/components/qnap","contentType":"directory"},{"name":"qnap_qsw","path":"homeassistant/components/qnap_qsw","contentType":"directory"},{"name":"qrcode","path":"homeassistant/components/qrcode","contentType":"directory"},{"name":"quadrafire","path":"homeassistant/components/quadrafire","contentType":"directory"},{"name":"quantum_gateway","path":"homeassistant/components/quantum_gateway","contentType":"directory"},{"name":"qvr_pro","path":"homeassistant/components/qvr_pro","contentType":"directory"},{"name":"qwikswitch","path":"homeassistant/components/qwikswitch","contentType":"directory"},{"name":"rachio","path":"homeassistant/components/rachio","contentType":"directory"},{"name":"radarr","path":"homeassistant/components/radarr","contentType":"directory"},{"name":"radio_browser","path":"homeassistant/components/radio_browser","contentType":"directory"},{"name":"radiotherm","path":"homeassistant/components/radiotherm","contentType":"directory"},{"name":"rainbird","path":"homeassistant/components/rainbird","contentType":"directory"},{"name":"raincloud","path":"homeassistant/components/raincloud","contentType":"directory"},{"name":"rainforest_eagle","path":"homeassistant/components/rainforest_eagle","contentType":"directory"},{"name":"rainmachine","path":"homeassistant/components/rainmachine","contentType":"directory"},{"name":"random","path":"homeassistant/components/random","contentType":"directory"},{"name":"rapt_ble","path":"homeassistant/components/rapt_ble","contentType":"directory"},{"name":"raspberry_pi","path":"homeassistant/components/raspberry_pi","contentType":"directory"},{"name":"raspyrfm","path":"homeassistant/components/raspyrfm","contentType":"directory"},{"name":"raven_rock_mfg","path":"homeassistant/components/raven_rock_mfg","contentType":"directory"},{"name":"rdw","path":"homeassistant/components/rdw","contentType":"directory"},{"name":"recollect_waste","path":"homeassistant/components/recollect_waste","contentType":"directory"},{"name":"recorder","path":"homeassistant/components/recorder","contentType":"directory"},{"name":"recswitch","path":"homeassistant/components/recswitch","contentType":"directory"},{"name":"reddit","path":"homeassistant/components/reddit","contentType":"directory"},{"name":"rejseplanen","path":"homeassistant/components/rejseplanen","contentType":"directory"},{"name":"remember_the_milk","path":"homeassistant/components/remember_the_milk","contentType":"directory"},{"name":"remote","path":"homeassistant/components/remote","contentType":"directory"},{"name":"remote_rpi_gpio","path":"homeassistant/components/remote_rpi_gpio","contentType":"directory"},{"name":"renault","path":"homeassistant/components/renault","contentType":"directory"},{"name":"renson","path":"homeassistant/components/renson","contentType":"directory"},{"name":"reolink","path":"homeassistant/components/reolink","contentType":"directory"},{"name":"repairs","path":"homeassistant/components/repairs","contentType":"directory"},{"name":"repetier","path":"homeassistant/components/repetier","contentType":"directory"},{"name":"rest","path":"homeassistant/components/rest","contentType":"directory"},{"name":"rest_command","path":"homeassistant/components/rest_command","contentType":"directory"},{"name":"rexel","path":"homeassistant/components/rexel","contentType":"directory"},{"name":"rflink","path":"homeassistant/components/rflink","contentType":"directory"},{"name":"rfxtrx","path":"homeassistant/components/rfxtrx","contentType":"directory"},{"name":"rhasspy","path":"homeassistant/components/rhasspy","contentType":"directory"},{"name":"ridwell","path":"homeassistant/components/ridwell","contentType":"directory"},{"name":"ring","path":"homeassistant/components/ring","contentType":"directory"},{"name":"ripple","path":"homeassistant/components/ripple","contentType":"directory"},{"name":"risco","path":"homeassistant/components/risco","contentType":"directory"},{"name":"rituals_perfume_genie","path":"homeassistant/components/rituals_perfume_genie","contentType":"directory"},{"name":"rmvtransport","path":"homeassistant/components/rmvtransport","contentType":"directory"},{"name":"roborock","path":"homeassistant/components/roborock","contentType":"directory"},{"name":"rocketchat","path":"homeassistant/components/rocketchat","contentType":"directory"},{"name":"roku","path":"homeassistant/components/roku","contentType":"directory"},{"name":"roomba","path":"homeassistant/components/roomba","contentType":"directory"},{"name":"roon","path":"homeassistant/components/roon","contentType":"directory"},{"name":"route53","path":"homeassistant/components/route53","contentType":"directory"},{"name":"rova","path":"homeassistant/components/rova","contentType":"directory"},{"name":"rpi_camera","path":"homeassistant/components/rpi_camera","contentType":"directory"},{"name":"rpi_power","path":"homeassistant/components/rpi_power","contentType":"directory"},{"name":"rss_feed_template","path":"homeassistant/components/rss_feed_template","contentType":"directory"},{"name":"rtorrent","path":"homeassistant/components/rtorrent","contentType":"directory"},{"name":"rtsp_to_webrtc","path":"homeassistant/components/rtsp_to_webrtc","contentType":"directory"},{"name":"ruckus_unleashed","path":"homeassistant/components/ruckus_unleashed","contentType":"directory"},{"name":"russound_rio","path":"homeassistant/components/russound_rio","contentType":"directory"},{"name":"russound_rnet","path":"homeassistant/components/russound_rnet","contentType":"directory"},{"name":"ruuvi_gateway","path":"homeassistant/components/ruuvi_gateway","contentType":"directory"},{"name":"ruuvitag_ble","path":"homeassistant/components/ruuvitag_ble","contentType":"directory"},{"name":"rympro","path":"homeassistant/components/rympro","contentType":"directory"},{"name":"sabnzbd","path":"homeassistant/components/sabnzbd","contentType":"directory"},{"name":"safe_mode","path":"homeassistant/components/safe_mode","contentType":"directory"},{"name":"saj","path":"homeassistant/components/saj","contentType":"directory"},{"name":"samsungtv","path":"homeassistant/components/samsungtv","contentType":"directory"},{"name":"satel_integra","path":"homeassistant/components/satel_integra","contentType":"directory"},{"name":"scene","path":"homeassistant/components/scene","contentType":"directory"},{"name":"schedule","path":"homeassistant/components/schedule","contentType":"directory"},{"name":"schlage","path":"homeassistant/components/schlage","contentType":"directory"},{"name":"schluter","path":"homeassistant/components/schluter","contentType":"directory"},{"name":"scrape","path":"homeassistant/components/scrape","contentType":"directory"},{"name":"screenaway","path":"homeassistant/components/screenaway","contentType":"directory"},{"name":"screenlogic","path":"homeassistant/components/screenlogic","contentType":"directory"},{"name":"script","path":"homeassistant/components/script","contentType":"directory"},{"name":"scsgate","path":"homeassistant/components/scsgate","contentType":"directory"},{"name":"search","path":"homeassistant/components/search","contentType":"directory"},{"name":"season","path":"homeassistant/components/season","contentType":"directory"},{"name":"select","path":"homeassistant/components/select","contentType":"directory"},{"name":"sendgrid","path":"homeassistant/components/sendgrid","contentType":"directory"},{"name":"sense","path":"homeassistant/components/sense","contentType":"directory"},{"name":"sensibo","path":"homeassistant/components/sensibo","contentType":"directory"},{"name":"sensirion_ble","path":"homeassistant/components/sensirion_ble","contentType":"directory"},{"name":"sensor","path":"homeassistant/components/sensor","contentType":"directory"},{"name":"sensorblue","path":"homeassistant/components/sensorblue","contentType":"directory"},{"name":"sensorpro","path":"homeassistant/components/sensorpro","contentType":"directory"},{"name":"sensorpush","path":"homeassistant/components/sensorpush","contentType":"directory"},{"name":"sentry","path":"homeassistant/components/sentry","contentType":"directory"},{"name":"senz","path":"homeassistant/components/senz","contentType":"directory"},{"name":"serial","path":"homeassistant/components/serial","contentType":"directory"},{"name":"serial_pm","path":"homeassistant/components/serial_pm","contentType":"directory"},{"name":"sesame","path":"homeassistant/components/sesame","contentType":"directory"},{"name":"seven_segments","path":"homeassistant/components/seven_segments","contentType":"directory"},{"name":"seventeentrack","path":"homeassistant/components/seventeentrack","contentType":"directory"},{"name":"sfr_box","path":"homeassistant/components/sfr_box","contentType":"directory"},{"name":"sharkiq","path":"homeassistant/components/sharkiq","contentType":"directory"},{"name":"shell_command","path":"homeassistant/components/shell_command","contentType":"directory"},{"name":"shelly","path":"homeassistant/components/shelly","contentType":"directory"},{"name":"shiftr","path":"homeassistant/components/shiftr","contentType":"directory"},{"name":"shodan","path":"homeassistant/components/shodan","contentType":"directory"},{"name":"shopping_list","path":"homeassistant/components/shopping_list","contentType":"directory"},{"name":"sia","path":"homeassistant/components/sia","contentType":"directory"},{"name":"sigfox","path":"homeassistant/components/sigfox","contentType":"directory"},{"name":"sighthound","path":"homeassistant/components/sighthound","contentType":"directory"},{"name":"signal_messenger","path":"homeassistant/components/signal_messenger","contentType":"directory"},{"name":"simplepush","path":"homeassistant/components/simplepush","contentType":"directory"},{"name":"simplisafe","path":"homeassistant/components/simplisafe","contentType":"directory"},{"name":"simply_automated","path":"homeassistant/components/simply_automated","contentType":"directory"},{"name":"simu","path":"homeassistant/components/simu","contentType":"directory"},{"name":"simulated","path":"homeassistant/components/simulated","contentType":"directory"},{"name":"sinch","path":"homeassistant/components/sinch","contentType":"directory"},{"name":"siren","path":"homeassistant/components/siren","contentType":"directory"},{"name":"sisyphus","path":"homeassistant/components/sisyphus","contentType":"directory"},{"name":"sky_hub","path":"homeassistant/components/sky_hub","contentType":"directory"},{"name":"skybeacon","path":"homeassistant/components/skybeacon","contentType":"directory"},{"name":"skybell","path":"homeassistant/components/skybell","contentType":"directory"},{"name":"slack","path":"homeassistant/components/slack","contentType":"directory"},{"name":"sleepiq","path":"homeassistant/components/sleepiq","contentType":"directory"},{"name":"slide","path":"homeassistant/components/slide","contentType":"directory"},{"name":"slimproto","path":"homeassistant/components/slimproto","contentType":"directory"},{"name":"sma","path":"homeassistant/components/sma","contentType":"directory"},{"name":"smappee","path":"homeassistant/components/smappee","contentType":"directory"},{"name":"smart_blinds","path":"homeassistant/components/smart_blinds","contentType":"directory"},{"name":"smart_home","path":"homeassistant/components/smart_home","contentType":"directory"},{"name":"smart_meter_texas","path":"homeassistant/components/smart_meter_texas","contentType":"directory"},{"name":"smarther","path":"homeassistant/components/smarther","contentType":"directory"},{"name":"smartthings","path":"homeassistant/components/smartthings","contentType":"directory"},{"name":"smarttub","path":"homeassistant/components/smarttub","contentType":"directory"},{"name":"smarty","path":"homeassistant/components/smarty","contentType":"directory"},{"name":"smhi","path":"homeassistant/components/smhi","contentType":"directory"},{"name":"sms","path":"homeassistant/components/sms","contentType":"directory"},{"name":"smtp","path":"homeassistant/components/smtp","contentType":"directory"},{"name":"snapcast","path":"homeassistant/components/snapcast","contentType":"directory"},{"name":"snips","path":"homeassistant/components/snips","contentType":"directory"},{"name":"snmp","path":"homeassistant/components/snmp","contentType":"directory"},{"name":"snooz","path":"homeassistant/components/snooz","contentType":"directory"},{"name":"solaredge","path":"homeassistant/components/solaredge","contentType":"directory"},{"name":"solaredge_local","path":"homeassistant/components/solaredge_local","contentType":"directory"},{"name":"solarlog","path":"homeassistant/components/solarlog","contentType":"directory"},{"name":"solax","path":"homeassistant/components/solax","contentType":"directory"},{"name":"soma","path":"homeassistant/components/soma","contentType":"directory"},{"name":"somfy","path":"homeassistant/components/somfy","contentType":"directory"},{"name":"somfy_mylink","path":"homeassistant/components/somfy_mylink","contentType":"directory"},{"name":"sonarr","path":"homeassistant/components/sonarr","contentType":"directory"},{"name":"songpal","path":"homeassistant/components/songpal","contentType":"directory"},{"name":"sonos","path":"homeassistant/components/sonos","contentType":"directory"},{"name":"sony_projector","path":"homeassistant/components/sony_projector","contentType":"directory"},{"name":"soundtouch","path":"homeassistant/components/soundtouch","contentType":"directory"},{"name":"spaceapi","path":"homeassistant/components/spaceapi","contentType":"directory"},{"name":"spc","path":"homeassistant/components/spc","contentType":"directory"},{"name":"speedtestdotnet","path":"homeassistant/components/speedtestdotnet","contentType":"directory"},{"name":"spider","path":"homeassistant/components/spider","contentType":"directory"},{"name":"splunk","path":"homeassistant/components/splunk","contentType":"directory"},{"name":"spotify","path":"homeassistant/components/spotify","contentType":"directory"},{"name":"sql","path":"homeassistant/components/sql","contentType":"directory"},{"name":"squeezebox","path":"homeassistant/components/squeezebox","contentType":"directory"},{"name":"srp_energy","path":"homeassistant/components/srp_energy","contentType":"directory"},{"name":"ssdp","path":"homeassistant/components/ssdp","contentType":"directory"},{"name":"starline","path":"homeassistant/components/starline","contentType":"directory"},{"name":"starlingbank","path":"homeassistant/components/starlingbank","contentType":"directory"},{"name":"starlink","path":"homeassistant/components/starlink","contentType":"directory"},{"name":"startca","path":"homeassistant/components/startca","contentType":"directory"},{"name":"statistics","path":"homeassistant/components/statistics","contentType":"directory"},{"name":"statsd","path":"homeassistant/components/statsd","contentType":"directory"},{"name":"steam_online","path":"homeassistant/components/steam_online","contentType":"directory"},{"name":"steamist","path":"homeassistant/components/steamist","contentType":"directory"},{"name":"stiebel_eltron","path":"homeassistant/components/stiebel_eltron","contentType":"directory"},{"name":"stookalert","path":"homeassistant/components/stookalert","contentType":"directory"},{"name":"stookwijzer","path":"homeassistant/components/stookwijzer","contentType":"directory"},{"name":"stream","path":"homeassistant/components/stream","contentType":"directory"},{"name":"streamlabswater","path":"homeassistant/components/streamlabswater","contentType":"directory"},{"name":"stt","path":"homeassistant/components/stt","contentType":"directory"},{"name":"subaru","path":"homeassistant/components/subaru","contentType":"directory"},{"name":"suez_water","path":"homeassistant/components/suez_water","contentType":"directory"},{"name":"sun","path":"homeassistant/components/sun","contentType":"directory"},{"name":"supervisord","path":"homeassistant/components/supervisord","contentType":"directory"},{"name":"supla","path":"homeassistant/components/supla","contentType":"directory"},{"name":"surepetcare","path":"homeassistant/components/surepetcare","contentType":"directory"},{"name":"swiss_hydrological_data","path":"homeassistant/components/swiss_hydrological_data","contentType":"directory"},{"name":"swiss_public_transport","path":"homeassistant/components/swiss_public_transport","contentType":"directory"},{"name":"swisscom","path":"homeassistant/components/swisscom","contentType":"directory"},{"name":"switch","path":"homeassistant/components/switch","contentType":"directory"},{"name":"switch_as_x","path":"homeassistant/components/switch_as_x","contentType":"directory"},{"name":"switchbee","path":"homeassistant/components/switchbee","contentType":"directory"},{"name":"switchbot","path":"homeassistant/components/switchbot","contentType":"directory"},{"name":"switchbot_cloud","path":"homeassistant/components/switchbot_cloud","contentType":"directory"},{"name":"switcher_kis","path":"homeassistant/components/switcher_kis","contentType":"directory"},{"name":"switchmate","path":"homeassistant/components/switchmate","contentType":"directory"},{"name":"symfonisk","path":"homeassistant/components/symfonisk","contentType":"directory"},{"name":"syncthing","path":"homeassistant/components/syncthing","contentType":"directory"},{"name":"syncthru","path":"homeassistant/components/syncthru","contentType":"directory"},{"name":"synology_chat","path":"homeassistant/components/synology_chat","contentType":"directory"},{"name":"synology_dsm","path":"homeassistant/components/synology_dsm","contentType":"directory"},{"name":"synology_srm","path":"homeassistant/components/synology_srm","contentType":"directory"},{"name":"syslog","path":"homeassistant/components/syslog","contentType":"directory"},{"name":"system_bridge","path":"homeassistant/components/system_bridge","contentType":"directory"},{"name":"system_health","path":"homeassistant/components/system_health","contentType":"directory"},{"name":"system_log","path":"homeassistant/components/system_log","contentType":"directory"},{"name":"systemmonitor","path":"homeassistant/components/systemmonitor","contentType":"directory"},{"name":"tado","path":"homeassistant/components/tado","contentType":"directory"},{"name":"tag","path":"homeassistant/components/tag","contentType":"directory"},{"name":"tailscale","path":"homeassistant/components/tailscale","contentType":"directory"},{"name":"tank_utility","path":"homeassistant/components/tank_utility","contentType":"directory"},{"name":"tankerkoenig","path":"homeassistant/components/tankerkoenig","contentType":"directory"},{"name":"tapsaff","path":"homeassistant/components/tapsaff","contentType":"directory"},{"name":"__init__.py","path":"homeassistant/components/__init__.py","contentType":"file"}],"totalCount":1190},"homeassistant":{"items":[{"name":"components","path":"homeassistant/components","contentType":"directory"}]},"":{"items":[{"name":"homeassistant","path":"homeassistant","contentType":"directory"}]}},"fileTreeProcessingTime":209.515536,"foldersToFetch":["homeassistant",""],"reducedMotionEnabled":"system","repo":{"id":12888993,"defaultBranch":"dev","name":"core","ownerLogin":"home-assistant","currentUserCanPush":false,"isFork":false,"isEmpty":false,"createdAt":"2013-09-17T03:29:48.000-04:00","ownerAvatar":"https://avatars.githubusercontent.com/u/13844975?v=4","public":true,"private":false,"isOrgOwned":true},"symbolsExpanded":false,"treeExpanded":true,"refInfo":{"name":"2023.10.1","listCacheKey":"v0:1697131007.0","canEdit":false,"refType":"tag","currentOid":"a6edfa85b188c6b0d8c9f40db0349368a2539169"},"path":"homeassistant/components/mazda/diagnostics.py","currentUser":{"id":106836726,"login":"eufysecurity","userEmail":"eufysecurity@insanemind.com"},"blob":{"rawLines":["\"\"\"Diagnostics support for the Mazda integration.\"\"\"","from __future__ import annotations","","from typing import Any","","from homeassistant.components.diagnostics.util import async_redact_data","from homeassistant.config_entries import ConfigEntry","from homeassistant.const import CONF_EMAIL, CONF_PASSWORD","from homeassistant.core import HomeAssistant","from homeassistant.exceptions import HomeAssistantError","from homeassistant.helpers.device_registry import DeviceEntry","","from .const import DATA_COORDINATOR, DOMAIN","","TO_REDACT_INFO = [CONF_EMAIL, CONF_PASSWORD]","TO_REDACT_DATA = [\"vin\", \"id\", \"latitude\", \"longitude\"]","","","async def async_get_config_entry_diagnostics(","    hass: HomeAssistant, config_entry: ConfigEntry",") -\u003e dict[str, Any]:","    \"\"\"Return diagnostics for a config entry.\"\"\"","    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]","","    diagnostics_data = {","        \"info\": async_redact_data(config_entry.data, TO_REDACT_INFO),","        \"data\": [","            async_redact_data(vehicle, TO_REDACT_DATA) for vehicle in coordinator.data","        ],","    }","","    return diagnostics_data","","","async def async_get_device_diagnostics(","    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry",") -\u003e dict[str, Any]:","    \"\"\"Return diagnostics for a device.\"\"\"","    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]","","    vin = next(iter(device.identifiers))[1]","","    target_vehicle = None","    for vehicle in coordinator.data:","        if vehicle[\"vin\"] == vin:","            target_vehicle = vehicle","            break","","    if target_vehicle is None:","        raise HomeAssistantError(\"Vehicle not found\")","","    diagnostics_data = {","        \"info\": async_redact_data(config_entry.data, TO_REDACT_INFO),","        \"data\": async_redact_data(target_vehicle, TO_REDACT_DATA),","    }","","    return diagnostics_data"],"stylingDirectives":[[{"start":0,"end":52,"cssClass":"pl-s"}],[{"start":0,"end":4,"cssClass":"pl-k"},{"start":16,"end":22,"cssClass":"pl-k"},{"start":23,"end":34,"cssClass":"pl-s1"}],[],[{"start":0,"end":4,"cssClass":"pl-k"},{"start":5,"end":11,"cssClass":"pl-s1"},{"start":12,"end":18,"cssClass":"pl-k"},{"start":19,"end":22,"cssClass":"pl-v"}],[],[{"start":0,"end":4,"cssClass":"pl-k"},{"start":5,"end":18,"cssClass":"pl-s1"},{"start":19,"end":29,"cssClass":"pl-s1"},{"start":30,"end":41,"cssClass":"pl-s1"},{"start":42,"end":46,"cssClass":"pl-s1"},{"start":47,"end":53,"cssClass":"pl-k"},{"start":54,"end":71,"cssClass":"pl-s1"}],[{"start":0,"end":4,"cssClass":"pl-k"},{"start":5,"end":18,"cssClass":"pl-s1"},{"start":19,"end":33,"cssClass":"pl-s1"},{"start":34,"end":40,"cssClass":"pl-k"},{"start":41,"end":52,"cssClass":"pl-v"}],[{"start":0,"end":4,"cssClass":"pl-k"},{"start":5,"end":18,"cssClass":"pl-s1"},{"start":19,"end":24,"cssClass":"pl-s1"},{"start":25,"end":31,"cssClass":"pl-k"},{"start":32,"end":42,"cssClass":"pl-v"},{"start":44,"end":57,"cssClass":"pl-v"}],[{"start":0,"end":4,"cssClass":"pl-k"},{"start":5,"end":18,"cssClass":"pl-s1"},{"start":19,"end":23,"cssClass":"pl-s1"},{"start":24,"end":30,"cssClass":"pl-k"},{"start":31,"end":44,"cssClass":"pl-v"}],[{"start":0,"end":4,"cssClass":"pl-k"},{"start":5,"end":18,"cssClass":"pl-s1"},{"start":19,"end":29,"cssClass":"pl-s1"},{"start":30,"end":36,"cssClass":"pl-k"},{"start":37,"end":55,"cssClass":"pl-v"}],[{"start":0,"end":4,"cssClass":"pl-k"},{"start":5,"end":18,"cssClass":"pl-s1"},{"start":19,"end":26,"cssClass":"pl-s1"},{"start":27,"end":42,"cssClass":"pl-s1"},{"start":43,"end":49,"cssClass":"pl-k"},{"start":50,"end":61,"cssClass":"pl-v"}],[],[{"start":0,"end":4,"cssClass":"pl-k"},{"start":6,"end":11,"cssClass":"pl-s1"},{"start":12,"end":18,"cssClass":"pl-k"},{"start":19,"end":35,"cssClass":"pl-v"},{"start":37,"end":43,"cssClass":"pl-v"}],[],[{"start":0,"end":14,"cssClass":"pl-v"},{"start":15,"end":16,"cssClass":"pl-c1"},{"start":18,"end":28,"cssClass":"pl-v"},{"start":30,"end":43,"cssClass":"pl-v"}],[{"start":0,"end":14,"cssClass":"pl-v"},{"start":15,"end":16,"cssClass":"pl-c1"},{"start":18,"end":23,"cssClass":"pl-s"},{"start":25,"end":29,"cssClass":"pl-s"},{"start":31,"end":41,"cssClass":"pl-s"},{"start":43,"end":54,"cssClass":"pl-s"}],[],[],[{"start":0,"end":5,"cssClass":"pl-k"},{"start":6,"end":9,"cssClass":"pl-k"},{"start":10,"end":44,"cssClass":"pl-en"}],[{"start":4,"end":8,"cssClass":"pl-s1"},{"start":10,"end":23,"cssClass":"pl-v"},{"start":25,"end":37,"cssClass":"pl-s1"},{"start":39,"end":50,"cssClass":"pl-v"}],[{"start":2,"end":4,"cssClass":"pl-c1"},{"start":5,"end":9,"cssClass":"pl-s1"},{"start":10,"end":13,"cssClass":"pl-s1"},{"start":15,"end":18,"cssClass":"pl-v"}],[{"start":4,"end":48,"cssClass":"pl-s"}],[{"start":4,"end":15,"cssClass":"pl-s1"},{"start":16,"end":17,"cssClass":"pl-c1"},{"start":18,"end":22,"cssClass":"pl-s1"},{"start":23,"end":27,"cssClass":"pl-s1"},{"start":28,"end":34,"cssClass":"pl-v"},{"start":36,"end":48,"cssClass":"pl-s1"},{"start":49,"end":57,"cssClass":"pl-s1"},{"start":59,"end":75,"cssClass":"pl-v"}],[],[{"start":4,"end":20,"cssClass":"pl-s1"},{"start":21,"end":22,"cssClass":"pl-c1"}],[{"start":8,"end":14,"cssClass":"pl-s"},{"start":16,"end":33,"cssClass":"pl-en"},{"start":34,"end":46,"cssClass":"pl-s1"},{"start":47,"end":51,"cssClass":"pl-s1"},{"start":53,"end":67,"cssClass":"pl-v"}],[{"start":8,"end":14,"cssClass":"pl-s"}],[{"start":12,"end":29,"cssClass":"pl-en"},{"start":30,"end":37,"cssClass":"pl-s1"},{"start":39,"end":53,"cssClass":"pl-v"},{"start":55,"end":58,"cssClass":"pl-k"},{"start":59,"end":66,"cssClass":"pl-s1"},{"start":67,"end":69,"cssClass":"pl-c1"},{"start":70,"end":81,"cssClass":"pl-s1"},{"start":82,"end":86,"cssClass":"pl-s1"}],[],[],[],[{"start":4,"end":10,"cssClass":"pl-k"},{"start":11,"end":27,"cssClass":"pl-s1"}],[],[],[{"start":0,"end":5,"cssClass":"pl-k"},{"start":6,"end":9,"cssClass":"pl-k"},{"start":10,"end":38,"cssClass":"pl-en"}],[{"start":4,"end":8,"cssClass":"pl-s1"},{"start":10,"end":23,"cssClass":"pl-v"},{"start":25,"end":37,"cssClass":"pl-s1"},{"start":39,"end":50,"cssClass":"pl-v"},{"start":52,"end":58,"cssClass":"pl-s1"},{"start":60,"end":71,"cssClass":"pl-v"}],[{"start":2,"end":4,"cssClass":"pl-c1"},{"start":5,"end":9,"cssClass":"pl-s1"},{"start":10,"end":13,"cssClass":"pl-s1"},{"start":15,"end":18,"cssClass":"pl-v"}],[{"start":4,"end":42,"cssClass":"pl-s"}],[{"start":4,"end":15,"cssClass":"pl-s1"},{"start":16,"end":17,"cssClass":"pl-c1"},{"start":18,"end":22,"cssClass":"pl-s1"},{"start":23,"end":27,"cssClass":"pl-s1"},{"start":28,"end":34,"cssClass":"pl-v"},{"start":36,"end":48,"cssClass":"pl-s1"},{"start":49,"end":57,"cssClass":"pl-s1"},{"start":59,"end":75,"cssClass":"pl-v"}],[],[{"start":4,"end":7,"cssClass":"pl-s1"},{"start":8,"end":9,"cssClass":"pl-c1"},{"start":10,"end":14,"cssClass":"pl-en"},{"start":15,"end":19,"cssClass":"pl-en"},{"start":20,"end":26,"cssClass":"pl-s1"},{"start":27,"end":38,"cssClass":"pl-s1"},{"start":41,"end":42,"cssClass":"pl-c1"}],[],[{"start":4,"end":18,"cssClass":"pl-s1"},{"start":19,"end":20,"cssClass":"pl-c1"},{"start":21,"end":25,"cssClass":"pl-c1"}],[{"start":4,"end":7,"cssClass":"pl-k"},{"start":8,"end":15,"cssClass":"pl-s1"},{"start":16,"end":18,"cssClass":"pl-c1"},{"start":19,"end":30,"cssClass":"pl-s1"},{"start":31,"end":35,"cssClass":"pl-s1"}],[{"start":8,"end":10,"cssClass":"pl-k"},{"start":11,"end":18,"cssClass":"pl-s1"},{"start":19,"end":24,"cssClass":"pl-s"},{"start":26,"end":28,"cssClass":"pl-c1"},{"start":29,"end":32,"cssClass":"pl-s1"}],[{"start":12,"end":26,"cssClass":"pl-s1"},{"start":27,"end":28,"cssClass":"pl-c1"},{"start":29,"end":36,"cssClass":"pl-s1"}],[{"start":12,"end":17,"cssClass":"pl-k"}],[],[{"start":4,"end":6,"cssClass":"pl-k"},{"start":7,"end":21,"cssClass":"pl-s1"},{"start":22,"end":24,"cssClass":"pl-c1"},{"start":25,"end":29,"cssClass":"pl-c1"}],[{"start":8,"end":13,"cssClass":"pl-k"},{"start":14,"end":32,"cssClass":"pl-v"},{"start":33,"end":52,"cssClass":"pl-s"}],[],[{"start":4,"end":20,"cssClass":"pl-s1"},{"start":21,"end":22,"cssClass":"pl-c1"}],[{"start":8,"end":14,"cssClass":"pl-s"},{"start":16,"end":33,"cssClass":"pl-en"},{"start":34,"end":46,"cssClass":"pl-s1"},{"start":47,"end":51,"cssClass":"pl-s1"},{"start":53,"end":67,"cssClass":"pl-v"}],[{"start":8,"end":14,"cssClass":"pl-s"},{"start":16,"end":33,"cssClass":"pl-en"},{"start":34,"end":48,"cssClass":"pl-s1"},{"start":50,"end":64,"cssClass":"pl-v"}],[],[],[{"start":4,"end":10,"cssClass":"pl-k"},{"start":11,"end":27,"cssClass":"pl-s1"}]],"csv":null,"csvError":null,"dependabotInfo":{"showConfigurationBanner":false,"configFilePath":null,"networkDependabotPath":"/home-assistant/core/network/updates","dismissConfigurationNoticePath":"/settings/dismiss-notice/dependabot_configuration_notice","configurationNoticeDismissed":false,"repoAlertsPath":"/home-assistant/core/security/dependabot","repoSecurityAndAnalysisPath":"/home-assistant/core/settings/security_analysis","repoOwnerIsOrg":true,"currentUserCanAdminRepo":false},"displayName":"diagnostics.py","displayUrl":"https://github.com/home-assistant/core/blob/2023.10.1/homeassistant/components/mazda/diagnostics.py?raw=true","headerInfo":{"blobSize":"1.79 KB","deleteInfo":{"deleteTooltip":"You must be on a branch to make or propose changes to this file"},"editInfo":{"editTooltip":"You must be on a branch to make or propose changes to this file"},"ghDesktopPath":null,"gitLfsPath":null,"onBranch":false,"shortPath":"421410f","siteNavLoginPath":"/login?return_to=https%3A%2F%2Fgithub.com%2Fhome-assistant%2Fcore%2Fblob%2F2023.10.1%2Fhomeassistant%2Fcomponents%2Fmazda%2Fdiagnostics.py","isCSV":false,"isRichtext":false,"toc":null,"lineInfo":{"truncatedLoc":"57","truncatedSloc":"42"},"mode":"file"},"image":false,"isCodeownersFile":null,"isPlain":false,"isValidLegacyIssueTemplate":false,"issueTemplateHelpUrl":"https://docs.github.com/articles/about-issue-and-pull-request-templates","issueTemplate":null,"discussionTemplate":null,"language":"Python","languageID":303,"large":false,"loggedIn":true,"newDiscussionPath":"/home-assistant/core/discussions/new","newIssuePath":"/home-assistant/core/issues/new","planSupportInfo":{"repoIsFork":null,"repoOwnedByCurrentUser":null,"requestFullPath":"/home-assistant/core/blob/2023.10.1/homeassistant/components/mazda/diagnostics.py","showFreeOrgGatedFeatureMessage":null,"showPlanSupportBanner":null,"upgradeDataAttributes":null,"upgradePath":null},"publishBannersInfo":{"dismissActionNoticePath":"/settings/dismiss-notice/publish_action_from_dockerfile","dismissStackNoticePath":"/settings/dismiss-notice/publish_stack_from_file","releasePath":"/home-assistant/core/releases/new?marketplace=true","showPublishActionBanner":false,"showPublishStackBanner":false},"rawBlobUrl":"https://github.com/home-assistant/core/raw/2023.10.1/homeassistant/components/mazda/diagnostics.py","renderImageOrRaw":false,"richText":null,"renderedFileInfo":null,"shortPath":null,"tabSize":8,"topBannersInfo":{"overridingGlobalFundingFile":false,"globalPreferredFundingPath":null,"repoOwner":"home-assistant","repoName":"core","showInvalidCitationWarning":false,"citationHelpUrl":"https://docs.github.com/en/github/creating-cloning-and-archiving-repositories/creating-a-repository-on-github/about-citation-files","showDependabotConfigurationBanner":false,"actionsOnboardingTip":null},"truncated":false,"viewable":true,"workflowRedirectUrl":null,"symbols":{"timedOut":false,"notAnalyzed":false,"symbols":[{"name":"TO_REDACT_INFO","kind":"constant","identStart":505,"identEnd":519,"extentStart":505,"extentEnd":549,"fullyQualifiedName":"TO_REDACT_INFO","identUtf16":{"start":{"lineNumber":14,"utf16Col":0},"end":{"lineNumber":14,"utf16Col":14}},"extentUtf16":{"start":{"lineNumber":14,"utf16Col":0},"end":{"lineNumber":14,"utf16Col":44}}},{"name":"TO_REDACT_DATA","kind":"constant","identStart":550,"identEnd":564,"extentStart":550,"extentEnd":605,"fullyQualifiedName":"TO_REDACT_DATA","identUtf16":{"start":{"lineNumber":15,"utf16Col":0},"end":{"lineNumber":15,"utf16Col":14}},"extentUtf16":{"start":{"lineNumber":15,"utf16Col":0},"end":{"lineNumber":15,"utf16Col":55}}},{"name":"async_get_config_entry_diagnostics","kind":"function","identStart":618,"identEnd":652,"extentStart":608,"extentEnd":1098,"fullyQualifiedName":"async_get_config_entry_diagnostics","identUtf16":{"start":{"lineNumber":18,"utf16Col":10},"end":{"lineNumber":18,"utf16Col":44}},"extentUtf16":{"start":{"lineNumber":18,"utf16Col":0},"end":{"lineNumber":31,"utf16Col":27}}},{"name":"async_get_device_diagnostics","kind":"function","identStart":1111,"identEnd":1139,"extentStart":1101,"extentEnd":1835,"fullyQualifiedName":"async_get_device_diagnostics","identUtf16":{"start":{"lineNumber":34,"utf16Col":10},"end":{"lineNumber":34,"utf16Col":38}},"extentUtf16":{"start":{"lineNumber":34,"utf16Col":0},"end":{"lineNumber":56,"utf16Col":27}}}]}},"copilotInfo":null,"csrf_tokens":{"/home-assistant/core/branches":{"post":"Cd1XSiZNaTvmni4GO4WoRLLreQ-YIPs2mQuRclqYAmZoPCr_dzQ1VP5iEbrx0VsL4dqX5VvrSM3NHKvDDk3zgg"},"/repos/preferences":{"post":"_lC2EAPlD8VZDCsreqrIG4LvtBBCEr7xZAryqzv2nR6-_r9uITRRqGoHBHmWa93yUpVDU7v6O4PsgnmTiV5_OA"}}},"title":"core/homeassistant/components/mazda/diagnostics.py at 2023.10.1 · home-assistant/core","appPayload":{"helpUrl":"https://docs.github.com","findFileWorkerPath":"/assets-cdn/worker/find-file-worker-83d4418b406d.js","findInFileWorkerPath":"/assets-cdn/worker/find-in-file-worker-bcc43f789400.js","githubDevUrl":"https://github.dev/","enabled_features":{"code_nav_ui_events":false,"copilot_conversational_ux":false,"copilot_conversational_ux_streaming":false,"copilot_popover_file_editor_header":true,"copilot_smell_icebreaker_ux":false}}}</script>
  <div data-target="react-app.reactRoot"><style data-styled="true" data-styled-version="5.3.6">.fNPcqd{font-weight:600;font-size:32px;margin:0;font-size:14px;}/*!sc*/
.imcwCi{font-weight:600;font-size:32px;margin:0;font-size:16px;margin-left:8px;}/*!sc*/
.cgQnMS{font-weight:600;font-size:32px;margin:0;}/*!sc*/
.diwsLq{font-weight:600;font-size:32px;margin:0;font-weight:600;display:inline-block;max-width:100%;font-size:16px;}/*!sc*/
.jAEDJk{font-weight:600;font-size:32px;margin:0;font-weight:600;display:inline-block;max-width:100%;font-size:14px;}/*!sc*/
data-styled.g1[id="Heading__StyledHeading-sc-1c1dgg0-0"]{content:"fNPcqd,imcwCi,cgQnMS,diwsLq,jAEDJk,"}/*!sc*/
.fSWWem{padding:0;}/*!sc*/
.kPPmzM{max-width:100%;margin-left:auto;margin-right:auto;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex-wrap:wrap;-ms-flex-wrap:wrap;flex-wrap:wrap;}/*!sc*/
.cIAPDV{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex:1 1 100%;-ms-flex:1 1 100%;flex:1 1 100%;-webkit-flex-wrap:wrap;-ms-flex-wrap:wrap;flex-wrap:wrap;max-width:100%;}/*!sc*/
.gvCnwW{width:100%;}/*!sc*/
@media screen and (min-width:544px){.gvCnwW{width:100%;}}/*!sc*/
@media screen and (min-width:768px){.gvCnwW{width:auto;}}/*!sc*/
.ioxSsX{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-order:1;-ms-flex-order:1;order:1;width:100%;margin-left:0;margin-right:0;-webkit-flex-direction:column;-ms-flex-direction:column;flex-direction:column;margin-bottom:0;min-width:0;}/*!sc*/
@media screen and (min-width:544px){.ioxSsX{-webkit-flex-direction:column;-ms-flex-direction:column;flex-direction:column;}}/*!sc*/
@media screen and (min-width:768px){.ioxSsX{width:auto;margin-top:0 !important;margin-bottom:0 !important;position:-webkit-sticky;position:sticky;top:0px;max-height:var(--sticky-pane-height);-webkit-flex-direction:row-reverse;-ms-flex-direction:row-reverse;flex-direction:row-reverse;margin-right:0;}}/*!sc*/
@media screen and (min-width:769px){.ioxSsX{height:100vh;max-height:100vh !important;}}/*!sc*/
@media print,screen and (max-width:1011px) and (min-width:768px){.ioxSsX{display:none;}}/*!sc*/
.eUyHuk{margin-left:0;margin-right:0;display:none;margin-top:0;}/*!sc*/
@media screen and (min-width:768px){.eUyHuk{margin-left:0 !important;margin-right:0 !important;}}/*!sc*/
.hAeDYA{height:100%;position:relative;display:none;margin-left:0;}/*!sc*/
.dZCkhR{position:absolute;inset:0 -2px;cursor:col-resize;background-color:transparent;-webkit-transition-delay:0.1s;transition-delay:0.1s;}/*!sc*/
.dZCkhR:hover{background-color:rgba(110,118,129,0.4);}/*!sc*/
.gNdDUH{--pane-min-width:256px;--pane-max-width-diff:511px;--pane-max-width:calc(100vw - var(--pane-max-width-diff));width:100%;padding:0;}/*!sc*/
@media screen and (min-width:544px){}/*!sc*/
@media screen and (min-width:768px){.gNdDUH{width:clamp(var(--pane-min-width),var(--pane-width),var(--pane-max-width));overflow:auto;}}/*!sc*/
@media screen and (min-width:1280px){.gNdDUH{--pane-max-width-diff:959px;}}/*!sc*/
.jywUSN{max-height:100%;height:100%;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex-direction:column;-ms-flex-direction:column;flex-direction:column;}/*!sc*/
@media screen and (max-width:768px){.jywUSN{display:none;}}/*!sc*/
@media screen and (min-width:768px){.jywUSN{max-height:100vh;height:100vh;}}/*!sc*/
.hBSSUC{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex-direction:column;-ms-flex-direction:column;flex-direction:column;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;padding-left:16px;padding-right:16px;padding-bottom:8px;padding-top:16px;}/*!sc*/
.iPurHz{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;width:100%;margin-bottom:16px;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;}/*!sc*/
.kkrdEu{-webkit-box-pack:center;-webkit-justify-content:center;-ms-flex-pack:center;justify-content:center;}/*!sc*/
.trpoQ{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;pointer-events:none;}/*!sc*/
.hVHHYa{margin-left:24px;margin-right:24px;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;width:100%;}/*!sc*/
.idZfsJ{-webkit-box-flex:1;-webkit-flex-grow:1;-ms-flex-positive:1;flex-grow:1;}/*!sc*/
.bKgizp{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;width:100%;}/*!sc*/
.bwTunw{margin-right:4px;color:#7d8590;}/*!sc*/
.caeYDk{font-size:14px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}/*!sc*/
.jahcnb{margin-left:8px;white-space:nowrap;}/*!sc*/
.jahcnb:hover button:not(:hover){border-left-color:var(--button-default-borderColor-hover,var(--color-btn-hover-border));}/*!sc*/
.ccToMy{margin-left:16px;margin-right:16px;margin-bottom:12px;}/*!sc*/
@media screen and (max-width:768px){.ccToMy{display:none;}}/*!sc*/
.cNvKlH{margin-right:-6px;}/*!sc*/
.cLfAnm{-webkit-box-flex:1;-webkit-flex-grow:1;-ms-flex-positive:1;flex-grow:1;max-height:100% !important;overflow-y:auto;-webkit-scrollbar-gutter:stable;-moz-scrollbar-gutter:stable;-ms-scrollbar-gutter:stable;scrollbar-gutter:stable;}/*!sc*/
@media screen and (max-width:768px){.cLfAnm{display:none;}}/*!sc*/
.erWCJP{padding-left:16px;padding-right:16px;padding-bottom:8px;}/*!sc*/
.fUswPC{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-box-pack:center;-webkit-justify-content:center;-ms-flex-pack:center;justify-content:center;padding:8px;}/*!sc*/
@media (min-height:600px) and (min-width:768px){.hwhShM{display:none;}}/*!sc*/
.cYPxpP{margin-top:8px;margin-left:16px;margin-right:16px;margin-bottom:12px;font-size:12px;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;}/*!sc*/
@media (max-height:599px),(max-width:767px){.fBtiVT{display:none;}}/*!sc*/
.emFMJu{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex-direction:column;-ms-flex-direction:column;flex-direction:column;-webkit-order:2;-ms-flex-order:2;order:2;-webkit-flex-basis:0;-ms-flex-preferred-size:0;flex-basis:0;-webkit-box-flex:1;-webkit-flex-grow:1;-ms-flex-positive:1;flex-grow:1;-webkit-flex-shrink:1;-ms-flex-negative:1;flex-shrink:1;min-width:1px;margin-right:auto;}/*!sc*/
@media print{.emFMJu{display:-webkit-box !important;display:-webkit-flex !important;display:-ms-flexbox !important;display:flex !important;}}/*!sc*/
.hlUAHL{width:100%;max-width:100%;margin-left:auto;margin-right:auto;-webkit-box-flex:1;-webkit-flex-grow:1;-ms-flex-positive:1;flex-grow:1;padding:0;}/*!sc*/
.iStsmI{margin-left:auto;margin-right:auto;-webkit-flex-direction:column;-ms-flex-direction:column;flex-direction:column;padding-bottom:40px;max-width:100%;margin-top:0;}/*!sc*/
.eIgvIk{display:inherit;}/*!sc*/
.eVFfWF{width:100%;}/*!sc*/
.kgXdnT{padding:16px;padding-bottom:0;}/*!sc*/
.kzTa-dF{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex-direction:column;-ms-flex-direction:column;flex-direction:column;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;gap:16px;width:100%;}/*!sc*/
.bbXCl{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex-direction:row;-ms-flex-direction:row;flex-direction:row;-webkit-align-items:start;-webkit-box-align:start;-ms-flex-align:start;align-items:start;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;}/*!sc*/
.hGGMNu{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex-direction:row;-ms-flex-direction:row;flex-direction:row;-webkit-align-items:start;-webkit-box-align:start;-ms-flex-align:start;align-items:start;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;justify-self:flex-end;}/*!sc*/
.eHRrYV{margin-left:8px;margin-right:8px;}/*!sc*/
.dKmYfk{font-size:14px;min-width:0;max-width:125px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}/*!sc*/
.hSNzKh{justify-self:end;max-width:100%;}/*!sc*/
.eTvGbF{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex-direction:row;-ms-flex-direction:row;flex-direction:row;font-size:16px;min-width:0;-webkit-flex-shrink:1;-ms-flex-negative:1;flex-shrink:1;-webkit-flex-wrap:wrap;-ms-flex-wrap:wrap;flex-wrap:wrap;max-width:100%;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;}/*!sc*/
.kzRgrI{max-width:100%;}/*!sc*/
.cmAPIB{max-width:100%;list-style:none;display:inline-block;}/*!sc*/
.jwXCBK{display:inline-block;max-width:100%;}/*!sc*/
.bDwCYs{padding:16px;padding-bottom:0;padding-left:16px;padding-right:16px;}/*!sc*/
.fywjmm{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;gap:8px;-webkit-flex-direction:column;-ms-flex-direction:column;flex-direction:column;width:100%;}/*!sc*/
.dyczTK{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:start;-webkit-box-align:start;-ms-flex-align:start;align-items:start;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;gap:8px;}/*!sc*/
.kszRgZ{-webkit-align-self:center;-ms-flex-item-align:center;align-self:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;padding-right:8px;min-width:0;}/*!sc*/
.gtBUEp{min-height:32px;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:start;-webkit-box-align:start;-ms-flex-align:start;align-items:start;}/*!sc*/
.MERGN{margin-left:16px;margin-right:16px;}/*!sc*/
@media screen and (min-width:1440px){.MERGN{margin-left:16px;}}/*!sc*/
.cMYnca{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex-direction:column;-ms-flex-direction:column;flex-direction:column;}/*!sc*/
.brFBoI{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex-direction:column;-ms-flex-direction:column;flex-direction:column;border:1px solid;border-color:#30363d;border-radius:6px;margin-bottom:16px;}/*!sc*/
.eYedVD{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex-direction:row;-ms-flex-direction:row;flex-direction:row;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;gap:8px;min-width:273px;padding-right:8px;padding-left:16px;padding-top:8px;padding-bottom:8px;}/*!sc*/
.jGfYmh{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;gap:8px;}/*!sc*/
.lhFvfi{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;}/*!sc*/
.bqgLjk{display:inherit;}/*!sc*/
@media screen and (min-width:544px){.bqgLjk{display:none;}}/*!sc*/
@media screen and (min-width:768px){.bqgLjk{display:none;}}/*!sc*/
.iJmJly{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex-direction:row;-ms-flex-direction:row;flex-direction:row;}/*!sc*/
.jACbi{width:100%;height:-webkit-fit-content;height:-moz-fit-content;height:fit-content;min-width:0;margin-right:0;}/*!sc*/
.bSdwWB{padding-left:4px;padding-bottom:16px;}/*!sc*/
.fleZSW{-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;}/*!sc*/
.fOEJrA{font-size:12px;-webkit-flex:auto;-ms-flex:auto;flex:auto;padding-right:16px;color:#7d8590;min-width:0;}/*!sc*/
.gBKNLX{top:0px;z-index:1;background:var(--color-canvas-default);position:-webkit-sticky;position:sticky;}/*!sc*/
.ePiodO{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex-direction:column;-ms-flex-direction:column;flex-direction:column;width:100%;position:absolute;}/*!sc*/
.kQJlnf{display:none;min-width:0;padding-top:8px;padding-bottom:8px;}/*!sc*/
.gJICKO{margin-right:8px;margin-left:16px;text-overflow:ellipsis;overflow:hidden;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex-direction:row;-ms-flex-direction:row;flex-direction:row;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;width:100%;}/*!sc*/
.iZJewz{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex-direction:row;-ms-flex-direction:row;flex-direction:row;font-size:14px;min-width:0;-webkit-flex-shrink:1;-ms-flex-negative:1;flex-shrink:1;-webkit-flex-wrap:wrap;-ms-flex-wrap:wrap;flex-wrap:wrap;max-width:100%;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;}/*!sc*/
.bESQXL{padding-left:8px;padding-top:8px;padding-bottom:8px;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex:1;-ms-flex:1;flex:1;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;background-color:#161b22;border:1px solid var(--borderColor-default,var(--color-border-default));border-radius:6px 6px 0px 0px;}/*!sc*/
.bfkNRF{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;gap:8px;min-width:0;}/*!sc*/
.fXBLEV{display:block;position:relative;-webkit-box-flex:1;-webkit-flex-grow:1;-ms-flex-positive:1;flex-grow:1;margin-top:-1px;margin-bottom:-1px;--separator-color:transparent;}/*!sc*/
.fXBLEV:not(:last-child){margin-right:1px;}/*!sc*/
.fXBLEV:not(:last-child):after{background-color:var(--separator-color);content:"";position:absolute;right:-2px;top:8px;bottom:8px;width:1px;}/*!sc*/
.fXBLEV:focus-within:has(:focus-visible){--separator-color:transparent;}/*!sc*/
.fXBLEV:first-child{margin-left:-1px;}/*!sc*/
.fXBLEV:last-child{margin-right:-1px;}/*!sc*/
.gbKtit{display:block;position:relative;-webkit-box-flex:1;-webkit-flex-grow:1;-ms-flex-positive:1;flex-grow:1;margin-top:-1px;margin-bottom:-1px;--separator-color:#30363d;}/*!sc*/
.gbKtit:not(:last-child){margin-right:1px;}/*!sc*/
.gbKtit:not(:last-child):after{background-color:var(--separator-color);content:"";position:absolute;right:-2px;top:8px;bottom:8px;width:1px;}/*!sc*/
.gbKtit:focus-within:has(:focus-visible){--separator-color:transparent;}/*!sc*/
.gbKtit:first-child{margin-left:-1px;}/*!sc*/
.gbKtit:last-child{margin-right:-1px;}/*!sc*/
.iBylDf{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;gap:8px;margin-right:8px;}/*!sc*/
.kSGBPx{gap:8px;}/*!sc*/
.etfROT{border:1px solid;border-top:none;border-color:#30363d;border-radius:0px 0px 6px 6px;min-width:273px;}/*!sc*/
.jWnGGx{background-color:var(--bgColor-default,var(--color-canvas-default));border:0px;border-width:0;border-radius:0px 0px 6px 6px;padding:0;min-width:0;margin-top:46px;}/*!sc*/
.TCenl{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-flex:1;-ms-flex:1;flex:1;padding-top:8px;padding-bottom:8px;-webkit-flex-direction:column;-ms-flex-direction:column;flex-direction:column;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;min-width:0;position:relative;}/*!sc*/
.cluMzC{position:relative;}/*!sc*/
.eRkHwF{-webkit-flex:1;-ms-flex:1;flex:1;position:relative;min-width:0;}/*!sc*/
.knCTAx{tab-size:8;isolation:isolate;position:relative;overflow:auto;max-width:unset;}/*!sc*/
.hXUKEK{margin:1px 8px;position:absolute;z-index:1;}/*!sc*/
.cXzIIR{position:absolute;}/*!sc*/
.aZrVR{position:fixed;top:0;right:0;height:100%;width:15px;-webkit-transition:-webkit-transform 0.3s;-webkit-transition:transform 0.3s;transition:transform 0.3s;z-index:1;}/*!sc*/
.aZrVR:hover{-webkit-transform:scaleX(1.5);-ms-transform:scaleX(1.5);transform:scaleX(1.5);}/*!sc*/
data-styled.g2[id="Box-sc-g0xbh4-0"]{content:"fSWWem,kPPmzM,cIAPDV,gvCnwW,ioxSsX,eUyHuk,hAeDYA,dZCkhR,gNdDUH,jywUSN,hBSSUC,iPurHz,kkrdEu,trpoQ,hVHHYa,idZfsJ,bKgizp,bwTunw,caeYDk,jahcnb,ccToMy,cNvKlH,cLfAnm,erWCJP,fUswPC,hwhShM,cYPxpP,fBtiVT,emFMJu,hlUAHL,iStsmI,eIgvIk,eVFfWF,kgXdnT,kzTa-dF,bbXCl,hGGMNu,eHRrYV,dKmYfk,hSNzKh,eTvGbF,kzRgrI,cmAPIB,jwXCBK,bDwCYs,fywjmm,dyczTK,kszRgZ,gtBUEp,MERGN,cMYnca,brFBoI,eYedVD,jGfYmh,lhFvfi,bqgLjk,iJmJly,jACbi,bSdwWB,fleZSW,fOEJrA,gBKNLX,ePiodO,kQJlnf,gJICKO,iZJewz,bESQXL,bfkNRF,fXBLEV,gbKtit,iBylDf,kSGBPx,etfROT,jWnGGx,TCenl,cluMzC,eRkHwF,knCTAx,hXUKEK,cXzIIR,aZrVR,"}/*!sc*/
.rTZSs{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;-webkit-clip:rect(0,0,0,0);clip:rect(0,0,0,0);white-space:nowrap;border-width:0;}/*!sc*/
data-styled.g3[id="_VisuallyHidden__VisuallyHidden-sc-11jhm7a-0"]{content:"rTZSs,"}/*!sc*/
.fUpWeN{display:inline-block;overflow:hidden;text-overflow:ellipsis;vertical-align:top;white-space:nowrap;max-width:125px;max-width:100%;}/*!sc*/
data-styled.g5[id="Truncate__StyledTruncate-sc-23o1d2-0"]{content:"fUpWeN,"}/*!sc*/
.bJBoUI{color:#2f81f7;-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.bJBoUI:hover{-webkit-text-decoration:underline;text-decoration:underline;}/*!sc*/
.bJBoUI:is(button){display:inline-block;padding:0;font-size:inherit;white-space:nowrap;cursor:pointer;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;background-color:transparent;border:0;-webkit-appearance:none;-moz-appearance:none;appearance:none;}/*!sc*/
.iJtJJh{color:#2f81f7;-webkit-text-decoration:none;text-decoration:none;font-weight:600;}/*!sc*/
.iJtJJh:hover{-webkit-text-decoration:underline;text-decoration:underline;}/*!sc*/
.iJtJJh:is(button){display:inline-block;padding:0;font-size:inherit;white-space:nowrap;cursor:pointer;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;background-color:transparent;border:0;-webkit-appearance:none;-moz-appearance:none;appearance:none;}/*!sc*/
.hUWqlv{color:#2f81f7;-webkit-text-decoration:none;text-decoration:none;font-weight:400;}/*!sc*/
.hUWqlv:hover{-webkit-text-decoration:underline;text-decoration:underline;}/*!sc*/
.hUWqlv:is(button){display:inline-block;padding:0;font-size:inherit;white-space:nowrap;cursor:pointer;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;background-color:transparent;border:0;-webkit-appearance:none;-moz-appearance:none;appearance:none;}/*!sc*/
data-styled.g7[id="Link__StyledLink-sc-14289xe-0"]{content:"bJBoUI,iJtJJh,hUWqlv,"}/*!sc*/
.hPEVNM{-webkit-animation:rotate-keyframes 1s linear infinite;animation:rotate-keyframes 1s linear infinite;}/*!sc*/
@-webkit-keyframes rotate-keyframes{100%{-webkit-transform:rotate(360deg);-ms-transform:rotate(360deg);transform:rotate(360deg);}}/*!sc*/
@keyframes rotate-keyframes{100%{-webkit-transform:rotate(360deg);-ms-transform:rotate(360deg);transform:rotate(360deg);}}/*!sc*/
data-styled.g24[id="Spinner__StyledSpinner-sc-1knt686-0"]{content:"hPEVNM,"}/*!sc*/
.hSXtjz{font-size:14px;line-height:20px;color:#e6edf3;vertical-align:middle;background-color:#0d1117;border:1px solid var(--control-borderColor-rest,#30363d);border-radius:6px;outline:none;box-shadow:0 0 transparent;display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;-webkit-align-items:stretch;-webkit-box-align:stretch;-ms-flex-align:stretch;align-items:stretch;min-height:32px;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;min-width:200px;}/*!sc*/
.hSXtjz input,.hSXtjz textarea{cursor:text;}/*!sc*/
.hSXtjz select{cursor:pointer;}/*!sc*/
.hSXtjz::-webkit-input-placeholder{color:#6e7681;}/*!sc*/
.hSXtjz::-moz-placeholder{color:#6e7681;}/*!sc*/
.hSXtjz:-ms-input-placeholder{color:#6e7681;}/*!sc*/
.hSXtjz::placeholder{color:#6e7681;}/*!sc*/
.hSXtjz:focus-within{border-color:#2f81f7;outline:none;box-shadow:inset 0 0 0 1px #2f81f7;}/*!sc*/
.hSXtjz > textarea{padding:12px;}/*!sc*/
@media (min-width:768px){.hSXtjz{font-size:14px;}}/*!sc*/
data-styled.g25[id="TextInputWrapper__TextInputBaseWrapper-sc-1mqhpbi-0"]{content:"hSXtjz,"}/*!sc*/
.hZMmEi{background-repeat:no-repeat;background-position:right 8px center;padding-left:12px;padding-right:12px;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;min-width:200px;}/*!sc*/
.hZMmEi > :not(:last-child){margin-right:8px;}/*!sc*/
.hZMmEi .TextInput-icon,.hZMmEi .TextInput-action{-webkit-align-self:center;-ms-flex-item-align:center;align-self:center;color:#7d8590;-webkit-flex-shrink:0;-ms-flex-negative:0;flex-shrink:0;}/*!sc*/
.hZMmEi > input,.hZMmEi > select{padding-left:0;padding-right:0;}/*!sc*/
data-styled.g26[id="TextInputWrapper-sc-1mqhpbi-1"]{content:"hZMmEi,"}/*!sc*/
.cmNjCr{border-radius:6px;border:1px solid;border-color:transparent;font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#2f81f7;background-color:transparent;box-shadow:none;}/*!sc*/
.cmNjCr:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.cmNjCr:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.cmNjCr:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.cmNjCr[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.cmNjCr[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.cmNjCr:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.cmNjCr:active{-webkit-transition:none;transition:none;}/*!sc*/
.cmNjCr:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.cmNjCr:disabled [data-component=ButtonCounter],.cmNjCr:disabled [data-component="leadingVisual"],.cmNjCr:disabled [data-component="trailingAction"]{color:inherit;}/*!sc*/
@media (forced-colors:active){.cmNjCr:focus{outline:solid 1px transparent;}}/*!sc*/
.cmNjCr [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.cmNjCr[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.cmNjCr[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;}/*!sc*/
.cmNjCr[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.cmNjCr[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.cmNjCr[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.cmNjCr[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.cmNjCr[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.cmNjCr[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.cmNjCr[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.cmNjCr[data-block="block"]{width:100%;}/*!sc*/
.cmNjCr [data-component="leadingVisual"]{grid-area:leadingVisual;color:#7d8590;}/*!sc*/
.cmNjCr [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.cmNjCr [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.cmNjCr [data-component="trailingAction"]{margin-right:-4px;color:#7d8590;}/*!sc*/
.cmNjCr [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.cmNjCr [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.cmNjCr:hover:not([disabled]){background-color:#30363d;}/*!sc*/
.cmNjCr:active:not([disabled]){background-color:#161b22;}/*!sc*/
.cmNjCr[aria-expanded=true]{background-color:#161b22;}/*!sc*/
.cmNjCr[data-component="IconButton"][data-no-visuals]{color:#7d8590;}/*!sc*/
.cmNjCr[data-no-visuals]{color:#2f81f7;}/*!sc*/
.cmNjCr:has([data-component="ButtonCounter"]){color:#2f81f7;}/*!sc*/
.cmNjCr:disabled[data-no-visuals]{color:#484f58;}/*!sc*/
.cmNjCr:disabled[data-no-visuals] [data-component=ButtonCounter]{color:inherit;}/*!sc*/
.cmNjCr{color:#7d8590;padding-left:8px;padding-right:8px;display:none;}/*!sc*/
@media screen and (max-width:768px){.cmNjCr{display:block;}}/*!sc*/
.lhczWi{border-radius:6px;border:1px solid;border-color:transparent;font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#2f81f7;background-color:transparent;box-shadow:none;}/*!sc*/
.lhczWi:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.lhczWi:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.lhczWi:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.lhczWi[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.lhczWi[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.lhczWi:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.lhczWi:active{-webkit-transition:none;transition:none;}/*!sc*/
.lhczWi:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.lhczWi:disabled [data-component=ButtonCounter],.lhczWi:disabled [data-component="leadingVisual"],.lhczWi:disabled [data-component="trailingAction"]{color:inherit;}/*!sc*/
@media (forced-colors:active){.lhczWi:focus{outline:solid 1px transparent;}}/*!sc*/
.lhczWi [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.lhczWi[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.lhczWi[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;}/*!sc*/
.lhczWi[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.lhczWi[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.lhczWi[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.lhczWi[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.lhczWi[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.lhczWi[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.lhczWi[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.lhczWi[data-block="block"]{width:100%;}/*!sc*/
.lhczWi [data-component="leadingVisual"]{grid-area:leadingVisual;color:#7d8590;}/*!sc*/
.lhczWi [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.lhczWi [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.lhczWi [data-component="trailingAction"]{margin-right:-4px;color:#7d8590;}/*!sc*/
.lhczWi [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.lhczWi [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.lhczWi:hover:not([disabled]){background-color:#30363d;}/*!sc*/
.lhczWi:active:not([disabled]){background-color:#161b22;}/*!sc*/
.lhczWi[aria-expanded=true]{background-color:#161b22;}/*!sc*/
.lhczWi[data-component="IconButton"][data-no-visuals]{color:#7d8590;}/*!sc*/
.lhczWi[data-no-visuals]{color:#2f81f7;}/*!sc*/
.lhczWi:has([data-component="ButtonCounter"]){color:#2f81f7;}/*!sc*/
.lhczWi:disabled[data-no-visuals]{color:#484f58;}/*!sc*/
.lhczWi:disabled[data-no-visuals] [data-component=ButtonCounter]{color:inherit;}/*!sc*/
.lhczWi[data-no-visuals="true"]{color:#7d8590;height:32px;position:relative;}/*!sc*/
@media screen and (max-width:768px){.lhczWi[data-no-visuals="true"]{display:none;}}/*!sc*/
.hPfySA{border-radius:6px;border:1px solid;border-color:rgba(240,246,252,0.1);font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#c9d1d9;background-color:#21262d;box-shadow:0 0 transparent,0 0 transparent;}/*!sc*/
.hPfySA:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.hPfySA:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.hPfySA:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.hPfySA[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.hPfySA[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.hPfySA:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.hPfySA:active{-webkit-transition:none;transition:none;}/*!sc*/
.hPfySA:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.hPfySA:disabled [data-component=ButtonCounter]{color:inherit;}/*!sc*/
@media (forced-colors:active){.hPfySA:focus{outline:solid 1px transparent;}}/*!sc*/
.hPfySA [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.hPfySA[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.hPfySA[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;}/*!sc*/
.hPfySA[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.hPfySA[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.hPfySA[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.hPfySA[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.hPfySA[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.hPfySA[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.hPfySA[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.hPfySA[data-block="block"]{width:100%;}/*!sc*/
.hPfySA [data-component="leadingVisual"]{grid-area:leadingVisual;}/*!sc*/
.hPfySA [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.hPfySA [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.hPfySA [data-component="trailingAction"]{margin-right:-4px;}/*!sc*/
.hPfySA [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.hPfySA [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.hPfySA:hover:not([disabled]){background-color:#30363d;border-color:#8b949e;}/*!sc*/
.hPfySA:active:not([disabled]){background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.hPfySA[aria-expanded=true]{background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.hPfySA [data-component="leadingVisual"],.hPfySA [data-component="trailingVisual"],.hPfySA [data-component="trailingAction"]{color:#7d8590;}/*!sc*/
.hPfySA{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;min-width:0;}/*!sc*/
.hPfySA svg{color:#7d8590;}/*!sc*/
.hPfySA > span{width:inherit;}/*!sc*/
.bZkSFv{border-radius:6px;border:1px solid;border-color:rgba(240,246,252,0.1);font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#c9d1d9;background-color:#21262d;box-shadow:0 0 transparent,0 0 transparent;}/*!sc*/
.bZkSFv:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.bZkSFv:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.bZkSFv:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.bZkSFv[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.bZkSFv[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.bZkSFv:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.bZkSFv:active{-webkit-transition:none;transition:none;}/*!sc*/
.bZkSFv:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.bZkSFv:disabled [data-component=ButtonCounter]{color:inherit;}/*!sc*/
@media (forced-colors:active){.bZkSFv:focus{outline:solid 1px transparent;}}/*!sc*/
.bZkSFv [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.bZkSFv[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.bZkSFv[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;}/*!sc*/
.bZkSFv[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.bZkSFv[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.bZkSFv[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.bZkSFv[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.bZkSFv[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.bZkSFv[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.bZkSFv[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.bZkSFv[data-block="block"]{width:100%;}/*!sc*/
.bZkSFv [data-component="leadingVisual"]{grid-area:leadingVisual;}/*!sc*/
.bZkSFv [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.bZkSFv [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.bZkSFv [data-component="trailingAction"]{margin-right:-4px;}/*!sc*/
.bZkSFv [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.bZkSFv [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.bZkSFv:hover:not([disabled]){background-color:#30363d;border-color:#8b949e;}/*!sc*/
.bZkSFv:active:not([disabled]){background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.bZkSFv[aria-expanded=true]{background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.bZkSFv [data-component="leadingVisual"],.bZkSFv [data-component="trailingVisual"],.bZkSFv [data-component="trailingAction"]{color:#7d8590;}/*!sc*/
.bZkSFv[data-no-visuals="true"]{color:#6e7681;font-size:14px;font-weight:400;-webkit-flex-shrink:0;-ms-flex-negative:0;flex-shrink:0;}/*!sc*/
.ePclzw{border-radius:6px;border:1px solid;border-color:rgba(240,246,252,0.1);font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#c9d1d9;background-color:#21262d;box-shadow:0 0 transparent,0 0 transparent;}/*!sc*/
.ePclzw:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.ePclzw:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.ePclzw:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.ePclzw[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.ePclzw[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.ePclzw:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.ePclzw:active{-webkit-transition:none;transition:none;}/*!sc*/
.ePclzw:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.ePclzw:disabled [data-component=ButtonCounter]{color:inherit;}/*!sc*/
@media (forced-colors:active){.ePclzw:focus{outline:solid 1px transparent;}}/*!sc*/
.ePclzw [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.ePclzw[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.ePclzw[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;}/*!sc*/
.ePclzw[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.ePclzw[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.ePclzw[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.ePclzw[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.ePclzw[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.ePclzw[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.ePclzw[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.ePclzw[data-block="block"]{width:100%;}/*!sc*/
.ePclzw [data-component="leadingVisual"]{grid-area:leadingVisual;}/*!sc*/
.ePclzw [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.ePclzw [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.ePclzw [data-component="trailingAction"]{margin-right:-4px;}/*!sc*/
.ePclzw [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.ePclzw [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.ePclzw:hover:not([disabled]){background-color:#30363d;border-color:#8b949e;}/*!sc*/
.ePclzw:active:not([disabled]){background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.ePclzw[aria-expanded=true]{background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.ePclzw [data-component="leadingVisual"],.ePclzw [data-component="trailingVisual"],.ePclzw [data-component="trailingAction"]{color:#7d8590;}/*!sc*/
.ePclzw{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;}/*!sc*/
.ePclzw svg{color:#7d8590;}/*!sc*/
.ePclzw > span{width:inherit;}/*!sc*/
.hPOZTU{border-radius:6px;border:1px solid;border-color:rgba(240,246,252,0.1);font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#c9d1d9;background-color:#21262d;box-shadow:0 0 transparent,0 0 transparent;}/*!sc*/
.hPOZTU:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.hPOZTU:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.hPOZTU:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.hPOZTU[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.hPOZTU[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.hPOZTU:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.hPOZTU:active{-webkit-transition:none;transition:none;}/*!sc*/
.hPOZTU:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.hPOZTU:disabled [data-component=ButtonCounter]{color:inherit;}/*!sc*/
@media (forced-colors:active){.hPOZTU:focus{outline:solid 1px transparent;}}/*!sc*/
.hPOZTU [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.hPOZTU[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.hPOZTU[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;}/*!sc*/
.hPOZTU[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.hPOZTU[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.hPOZTU[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.hPOZTU[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.hPOZTU[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.hPOZTU[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.hPOZTU[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.hPOZTU[data-block="block"]{width:100%;}/*!sc*/
.hPOZTU [data-component="leadingVisual"]{grid-area:leadingVisual;}/*!sc*/
.hPOZTU [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.hPOZTU [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.hPOZTU [data-component="trailingAction"]{margin-right:-4px;}/*!sc*/
.hPOZTU [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.hPOZTU [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.hPOZTU:hover:not([disabled]){background-color:#30363d;border-color:#8b949e;}/*!sc*/
.hPOZTU:active:not([disabled]){background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.hPOZTU[aria-expanded=true]{background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.hPOZTU [data-component="leadingVisual"],.hPOZTU [data-component="trailingVisual"],.hPOZTU [data-component="trailingAction"]{color:#7d8590;}/*!sc*/
.hPOZTU[data-no-visuals="true"]{border-top-left-radius:0;border-bottom-left-radius:0;display:none;}/*!sc*/
.jcILRt{border-radius:6px;border:1px solid;border-color:rgba(240,246,252,0.1);font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#c9d1d9;background-color:#21262d;box-shadow:0 0 transparent,0 0 transparent;}/*!sc*/
.jcILRt:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.jcILRt:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.jcILRt:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.jcILRt[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.jcILRt[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.jcILRt:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.jcILRt:active{-webkit-transition:none;transition:none;}/*!sc*/
.jcILRt:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.jcILRt:disabled [data-component=ButtonCounter]{color:inherit;}/*!sc*/
@media (forced-colors:active){.jcILRt:focus{outline:solid 1px transparent;}}/*!sc*/
.jcILRt [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.jcILRt[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.jcILRt[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;}/*!sc*/
.jcILRt[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.jcILRt[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.jcILRt[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.jcILRt[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.jcILRt[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.jcILRt[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.jcILRt[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.jcILRt[data-block="block"]{width:100%;}/*!sc*/
.jcILRt [data-component="leadingVisual"]{grid-area:leadingVisual;}/*!sc*/
.jcILRt [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.jcILRt [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.jcILRt [data-component="trailingAction"]{margin-right:-4px;}/*!sc*/
.jcILRt [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.jcILRt [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.jcILRt:hover:not([disabled]){background-color:#30363d;border-color:#8b949e;}/*!sc*/
.jcILRt:active:not([disabled]){background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.jcILRt[aria-expanded=true]{background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.jcILRt [data-component="leadingVisual"],.jcILRt [data-component="trailingVisual"],.jcILRt [data-component="trailingAction"]{color:#7d8590;}/*!sc*/
.jcILRt[data-no-visuals="true"]{color:#7d8590;}/*!sc*/
.dzga-dt{border-radius:6px;border:1px solid;border-color:transparent;font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#2f81f7;background-color:transparent;box-shadow:none;}/*!sc*/
.dzga-dt:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.dzga-dt:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.dzga-dt:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.dzga-dt[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.dzga-dt[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.dzga-dt:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.dzga-dt:active{-webkit-transition:none;transition:none;}/*!sc*/
.dzga-dt:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.dzga-dt:disabled [data-component=ButtonCounter],.dzga-dt:disabled [data-component="leadingVisual"],.dzga-dt:disabled [data-component="trailingAction"]{color:inherit;}/*!sc*/
@media (forced-colors:active){.dzga-dt:focus{outline:solid 1px transparent;}}/*!sc*/
.dzga-dt [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.dzga-dt[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.dzga-dt[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;}/*!sc*/
.dzga-dt[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.dzga-dt[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.dzga-dt[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.dzga-dt[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.dzga-dt[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.dzga-dt[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.dzga-dt[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.dzga-dt[data-block="block"]{width:100%;}/*!sc*/
.dzga-dt [data-component="leadingVisual"]{grid-area:leadingVisual;color:#7d8590;}/*!sc*/
.dzga-dt [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.dzga-dt [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.dzga-dt [data-component="trailingAction"]{margin-right:-4px;color:#7d8590;}/*!sc*/
.dzga-dt [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.dzga-dt [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.dzga-dt:hover:not([disabled]){background-color:#30363d;}/*!sc*/
.dzga-dt:active:not([disabled]){background-color:#161b22;}/*!sc*/
.dzga-dt[aria-expanded=true]{background-color:#161b22;}/*!sc*/
.dzga-dt[data-component="IconButton"][data-no-visuals]{color:#7d8590;}/*!sc*/
.dzga-dt[data-no-visuals]{color:#2f81f7;}/*!sc*/
.dzga-dt:has([data-component="ButtonCounter"]){color:#2f81f7;}/*!sc*/
.dzga-dt:disabled[data-no-visuals]{color:#484f58;}/*!sc*/
.dzga-dt:disabled[data-no-visuals] [data-component=ButtonCounter]{color:inherit;}/*!sc*/
.dzga-dt[data-size="small"][data-no-visuals="true"]{margin-left:8px;}/*!sc*/
.dWukOn{border-radius:6px;border:1px solid;border-color:transparent;font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#e6edf3;background-color:transparent;box-shadow:none;}/*!sc*/
.dWukOn:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.dWukOn:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.dWukOn:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.dWukOn[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.dWukOn[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.dWukOn:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.dWukOn:active{-webkit-transition:none;transition:none;}/*!sc*/
.dWukOn:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.dWukOn:disabled [data-component=ButtonCounter],.dWukOn:disabled [data-component="leadingVisual"],.dWukOn:disabled [data-component="trailingAction"]{color:inherit;}/*!sc*/
@media (forced-colors:active){.dWukOn:focus{outline:solid 1px transparent;}}/*!sc*/
.dWukOn [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.dWukOn[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.dWukOn[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;}/*!sc*/
.dWukOn[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.dWukOn[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.dWukOn[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.dWukOn[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.dWukOn[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.dWukOn[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.dWukOn[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.dWukOn[data-block="block"]{width:100%;}/*!sc*/
.dWukOn [data-component="leadingVisual"]{grid-area:leadingVisual;color:#7d8590;}/*!sc*/
.dWukOn [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.dWukOn [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.dWukOn [data-component="trailingAction"]{margin-right:-4px;color:#7d8590;}/*!sc*/
.dWukOn [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.dWukOn [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.dWukOn:hover:not([disabled]){background-color:#30363d;-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.dWukOn:active:not([disabled]){background-color:#161b22;-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.dWukOn[aria-expanded=true]{background-color:#161b22;}/*!sc*/
.dWukOn[data-component="IconButton"][data-no-visuals]{color:#7d8590;}/*!sc*/
.dWukOn[data-no-visuals]{color:#2f81f7;}/*!sc*/
.dWukOn:has([data-component="ButtonCounter"]){color:#2f81f7;}/*!sc*/
.dWukOn:disabled[data-no-visuals]{color:#484f58;}/*!sc*/
.dWukOn:disabled[data-no-visuals] [data-component=ButtonCounter]{color:inherit;}/*!sc*/
.dWukOn:focus:not([disabled]){-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.kGDoCG{border-radius:6px;border:1px solid;border-color:transparent;font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#2f81f7;background-color:transparent;box-shadow:none;}/*!sc*/
.kGDoCG:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.kGDoCG:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.kGDoCG:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.kGDoCG[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.kGDoCG[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.kGDoCG:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.kGDoCG:active{-webkit-transition:none;transition:none;}/*!sc*/
.kGDoCG:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.kGDoCG:disabled [data-component=ButtonCounter],.kGDoCG:disabled [data-component="leadingVisual"],.kGDoCG:disabled [data-component="trailingAction"]{color:inherit;}/*!sc*/
@media (forced-colors:active){.kGDoCG:focus{outline:solid 1px transparent;}}/*!sc*/
.kGDoCG [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.kGDoCG[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.kGDoCG[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;color:#e6edf3;margin-left:8px;}/*!sc*/
.kGDoCG[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.kGDoCG[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.kGDoCG[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.kGDoCG[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.kGDoCG[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.kGDoCG[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.kGDoCG[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.kGDoCG[data-block="block"]{width:100%;}/*!sc*/
.kGDoCG [data-component="leadingVisual"]{grid-area:leadingVisual;color:#7d8590;}/*!sc*/
.kGDoCG [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.kGDoCG [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.kGDoCG [data-component="trailingAction"]{margin-right:-4px;color:#7d8590;}/*!sc*/
.kGDoCG [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.kGDoCG [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.kGDoCG:hover:not([disabled]){background-color:#30363d;}/*!sc*/
.kGDoCG:active:not([disabled]){background-color:#161b22;}/*!sc*/
.kGDoCG[aria-expanded=true]{background-color:#161b22;}/*!sc*/
.kGDoCG[data-component="IconButton"][data-no-visuals]{color:#7d8590;}/*!sc*/
.kGDoCG[data-no-visuals]{color:#2f81f7;}/*!sc*/
.kGDoCG:has([data-component="ButtonCounter"]){color:#2f81f7;}/*!sc*/
.kGDoCG:disabled[data-no-visuals]{color:#484f58;}/*!sc*/
.kGDoCG:disabled[data-no-visuals] [data-component=ButtonCounter]{color:inherit;}/*!sc*/
.hHvcfT{border-radius:6px;border:1px solid;border-color:rgba(240,246,252,0.1);font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#c9d1d9;background-color:#21262d;box-shadow:0 0 transparent,0 0 transparent;padding-left:8px;padding-right:8px;}/*!sc*/
.hHvcfT:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.hHvcfT:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.hHvcfT:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.hHvcfT[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.hHvcfT[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.hHvcfT:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.hHvcfT:active{-webkit-transition:none;transition:none;}/*!sc*/
.hHvcfT:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.hHvcfT:disabled [data-component=ButtonCounter]{color:inherit;}/*!sc*/
@media (forced-colors:active){.hHvcfT:focus{outline:solid 1px transparent;}}/*!sc*/
.hHvcfT [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.hHvcfT[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.hHvcfT[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;}/*!sc*/
.hHvcfT[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.hHvcfT[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.hHvcfT[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.hHvcfT[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.hHvcfT[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.hHvcfT[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.hHvcfT[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.hHvcfT[data-block="block"]{width:100%;}/*!sc*/
.hHvcfT [data-component="leadingVisual"]{grid-area:leadingVisual;}/*!sc*/
.hHvcfT [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.hHvcfT [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.hHvcfT [data-component="trailingAction"]{margin-right:-4px;}/*!sc*/
.hHvcfT [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.hHvcfT [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.hHvcfT:hover:not([disabled]){background-color:#30363d;border-color:#8b949e;}/*!sc*/
.hHvcfT:active:not([disabled]){background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.hHvcfT[aria-expanded=true]{background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.hHvcfT [data-component="leadingVisual"],.hHvcfT [data-component="trailingVisual"],.hHvcfT [data-component="trailingAction"]{color:#7d8590;}/*!sc*/
.hHvcfT linkButtonSx:hover:not([disabled]){-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.hHvcfT linkButtonSx:focus:not([disabled]){-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.hHvcfT linkButtonSx:active:not([disabled]){-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.kCdBku{border-radius:6px;border:1px solid;border-color:rgba(240,246,252,0.1);font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#c9d1d9;background-color:#21262d;box-shadow:0 0 transparent,0 0 transparent;}/*!sc*/
.kCdBku:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.kCdBku:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.kCdBku:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.kCdBku[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.kCdBku[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.kCdBku:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.kCdBku:active{-webkit-transition:none;transition:none;}/*!sc*/
.kCdBku:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.kCdBku:disabled [data-component=ButtonCounter]{color:inherit;}/*!sc*/
@media (forced-colors:active){.kCdBku:focus{outline:solid 1px transparent;}}/*!sc*/
.kCdBku [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.kCdBku[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.kCdBku[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;}/*!sc*/
.kCdBku[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.kCdBku[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.kCdBku[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.kCdBku[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.kCdBku[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.kCdBku[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.kCdBku[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.kCdBku[data-block="block"]{width:100%;}/*!sc*/
.kCdBku [data-component="leadingVisual"]{grid-area:leadingVisual;}/*!sc*/
.kCdBku [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.kCdBku [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.kCdBku [data-component="trailingAction"]{margin-right:-4px;}/*!sc*/
.kCdBku [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.kCdBku [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.kCdBku:hover:not([disabled]){background-color:#30363d;border-color:#8b949e;}/*!sc*/
.kCdBku:active:not([disabled]){background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.kCdBku[aria-expanded=true]{background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.kCdBku [data-component="leadingVisual"],.kCdBku [data-component="trailingVisual"],.kCdBku [data-component="trailingAction"]{color:#7d8590;}/*!sc*/
.jcdBXR{border-radius:6px;border:1px solid;border-color:rgba(240,246,252,0.1);font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#c9d1d9;background-color:#21262d;box-shadow:0 0 transparent,0 0 transparent;}/*!sc*/
.jcdBXR:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.jcdBXR:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.jcdBXR:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.jcdBXR[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.jcdBXR[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.jcdBXR:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.jcdBXR:active{-webkit-transition:none;transition:none;}/*!sc*/
.jcdBXR:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.jcdBXR:disabled [data-component=ButtonCounter]{color:inherit;}/*!sc*/
@media (forced-colors:active){.jcdBXR:focus{outline:solid 1px transparent;}}/*!sc*/
.jcdBXR [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.jcdBXR[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.jcdBXR[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;}/*!sc*/
.jcdBXR[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.jcdBXR[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.jcdBXR[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.jcdBXR[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.jcdBXR[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.jcdBXR[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.jcdBXR[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.jcdBXR[data-block="block"]{width:100%;}/*!sc*/
.jcdBXR [data-component="leadingVisual"]{grid-area:leadingVisual;}/*!sc*/
.jcdBXR [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.jcdBXR [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.jcdBXR [data-component="trailingAction"]{margin-right:-4px;}/*!sc*/
.jcdBXR [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.jcdBXR [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.jcdBXR:hover:not([disabled]){background-color:#30363d;border-color:#8b949e;}/*!sc*/
.jcdBXR:active:not([disabled]){background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.jcdBXR[aria-expanded=true]{background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.jcdBXR [data-component="leadingVisual"],.jcdBXR [data-component="trailingVisual"],.jcdBXR [data-component="trailingAction"]{color:#7d8590;}/*!sc*/
.jcdBXR[data-size="small"][data-no-visuals="true"]{border-top-left-radius:0;border-bottom-left-radius:0;}/*!sc*/
.bwYDFy{border-radius:6px;border:1px solid;border-color:rgba(240,246,252,0.1);font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#c9d1d9;background-color:#21262d;box-shadow:0 0 transparent,0 0 transparent;}/*!sc*/
.bwYDFy:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.bwYDFy:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.bwYDFy:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.bwYDFy[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.bwYDFy[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.bwYDFy:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.bwYDFy:active{-webkit-transition:none;transition:none;}/*!sc*/
.bwYDFy:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.bwYDFy:disabled [data-component=ButtonCounter]{color:inherit;}/*!sc*/
@media (forced-colors:active){.bwYDFy:focus{outline:solid 1px transparent;}}/*!sc*/
.bwYDFy [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.bwYDFy[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.bwYDFy[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;}/*!sc*/
.bwYDFy[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.bwYDFy[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.bwYDFy[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.bwYDFy[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.bwYDFy[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.bwYDFy[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.bwYDFy[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.bwYDFy[data-block="block"]{width:100%;}/*!sc*/
.bwYDFy [data-component="leadingVisual"]{grid-area:leadingVisual;}/*!sc*/
.bwYDFy [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.bwYDFy [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.bwYDFy [data-component="trailingAction"]{margin-right:-4px;}/*!sc*/
.bwYDFy [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.bwYDFy [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.bwYDFy:hover:not([disabled]){background-color:#30363d;border-color:#8b949e;}/*!sc*/
.bwYDFy:active:not([disabled]){background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.bwYDFy[aria-expanded=true]{background-color:hsla(212,12%,18%,1);border-color:#6e7681;}/*!sc*/
.bwYDFy [data-component="leadingVisual"],.bwYDFy [data-component="trailingVisual"],.bwYDFy [data-component="trailingAction"]{color:#7d8590;}/*!sc*/
.bwYDFy[data-size="small"][data-no-visuals="true"]{border-top-right-radius:0;border-bottom-right-radius:0;border-right-width:0;}/*!sc*/
.bhUFcA{border-radius:6px;border:1px solid;border-color:transparent;font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#2f81f7;background-color:transparent;box-shadow:none;}/*!sc*/
.bhUFcA:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.bhUFcA:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.bhUFcA:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.bhUFcA[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.bhUFcA[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.bhUFcA:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.bhUFcA:active{-webkit-transition:none;transition:none;}/*!sc*/
.bhUFcA:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.bhUFcA:disabled [data-component=ButtonCounter],.bhUFcA:disabled [data-component="leadingVisual"],.bhUFcA:disabled [data-component="trailingAction"]{color:inherit;}/*!sc*/
@media (forced-colors:active){.bhUFcA:focus{outline:solid 1px transparent;}}/*!sc*/
.bhUFcA [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.bhUFcA[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.bhUFcA[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;}/*!sc*/
.bhUFcA[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.bhUFcA[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.bhUFcA[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.bhUFcA[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.bhUFcA[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.bhUFcA[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.bhUFcA[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.bhUFcA[data-block="block"]{width:100%;}/*!sc*/
.bhUFcA [data-component="leadingVisual"]{grid-area:leadingVisual;color:#7d8590;}/*!sc*/
.bhUFcA [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.bhUFcA [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.bhUFcA [data-component="trailingAction"]{margin-right:-4px;color:#7d8590;}/*!sc*/
.bhUFcA [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.bhUFcA [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.bhUFcA:hover:not([disabled]){background-color:#30363d;}/*!sc*/
.bhUFcA:active:not([disabled]){background-color:#161b22;}/*!sc*/
.bhUFcA[aria-expanded=true]{background-color:#161b22;}/*!sc*/
.bhUFcA[data-component="IconButton"][data-no-visuals]{color:#7d8590;}/*!sc*/
.bhUFcA[data-no-visuals]{color:#2f81f7;}/*!sc*/
.bhUFcA:has([data-component="ButtonCounter"]){color:#2f81f7;}/*!sc*/
.bhUFcA:disabled[data-no-visuals]{color:#484f58;}/*!sc*/
.bhUFcA:disabled[data-no-visuals] [data-component=ButtonCounter]{color:inherit;}/*!sc*/
.bhUFcA[data-size="small"][data-no-visuals="true"]{color:#7d8590;position:relative;}/*!sc*/
.jYfgHQ{border-radius:6px;border:1px solid;border-color:transparent;font-family:inherit;font-weight:500;font-size:14px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;-webkit-text-decoration:none;text-decoration:none;text-align:center;display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-box-pack:justify;-webkit-justify-content:space-between;-ms-flex-pack:justify;justify-content:space-between;height:32px;padding:0 12px;gap:8px;min-width:-webkit-max-content;min-width:-moz-max-content;min-width:max-content;-webkit-transition:80ms cubic-bezier(0.65,0,0.35,1);transition:80ms cubic-bezier(0.65,0,0.35,1);-webkit-transition-property:color,fill,background-color,border-color;transition-property:color,fill,background-color,border-color;color:#2f81f7;background-color:transparent;box-shadow:none;}/*!sc*/
.jYfgHQ:focus:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.jYfgHQ:focus:not(:disabled):not(:focus-visible){outline:solid 1px transparent;}/*!sc*/
.jYfgHQ:focus-visible:not(:disabled){box-shadow:none;outline:2px solid #2f81f7;outline-offset:-2px;}/*!sc*/
.jYfgHQ[href]{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;}/*!sc*/
.jYfgHQ[href]:hover{-webkit-text-decoration:none;text-decoration:none;}/*!sc*/
.jYfgHQ:hover{-webkit-transition-duration:80ms;transition-duration:80ms;}/*!sc*/
.jYfgHQ:active{-webkit-transition:none;transition:none;}/*!sc*/
.jYfgHQ:disabled{cursor:not-allowed;box-shadow:none;color:#484f58;}/*!sc*/
.jYfgHQ:disabled [data-component=ButtonCounter],.jYfgHQ:disabled [data-component="leadingVisual"],.jYfgHQ:disabled [data-component="trailingAction"]{color:inherit;}/*!sc*/
@media (forced-colors:active){.jYfgHQ:focus{outline:solid 1px transparent;}}/*!sc*/
.jYfgHQ [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.jYfgHQ[data-component=IconButton]{display:inline-grid;padding:unset;place-content:center;width:32px;min-width:unset;}/*!sc*/
.jYfgHQ[data-size="small"]{padding:0 8px;height:28px;gap:4px;font-size:12px;}/*!sc*/
.jYfgHQ[data-size="small"] [data-component="text"]{line-height:calc(20 / 12);}/*!sc*/
.jYfgHQ[data-size="small"] [data-component=ButtonCounter]{font-size:12px;}/*!sc*/
.jYfgHQ[data-size="small"] [data-component="buttonContent"] > :not(:last-child){margin-right:4px;}/*!sc*/
.jYfgHQ[data-size="small"][data-component=IconButton]{width:28px;padding:unset;}/*!sc*/
.jYfgHQ[data-size="large"]{padding:0 16px;height:40px;gap:8px;}/*!sc*/
.jYfgHQ[data-size="large"] [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.jYfgHQ[data-size="large"][data-component=IconButton]{width:40px;padding:unset;}/*!sc*/
.jYfgHQ[data-block="block"]{width:100%;}/*!sc*/
.jYfgHQ [data-component="leadingVisual"]{grid-area:leadingVisual;color:#7d8590;}/*!sc*/
.jYfgHQ [data-component="text"]{grid-area:text;line-height:calc(20/14);white-space:nowrap;}/*!sc*/
.jYfgHQ [data-component="trailingVisual"]{grid-area:trailingVisual;}/*!sc*/
.jYfgHQ [data-component="trailingAction"]{margin-right:-4px;color:#7d8590;}/*!sc*/
.jYfgHQ [data-component="buttonContent"]{-webkit-flex:1 0 auto;-ms-flex:1 0 auto;flex:1 0 auto;display:grid;grid-template-areas:"leadingVisual text trailingVisual";grid-template-columns:min-content minmax(0,auto) min-content;-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;-webkit-align-content:center;-ms-flex-line-pack:center;align-content:center;}/*!sc*/
.jYfgHQ [data-component="buttonContent"] > :not(:last-child){margin-right:8px;}/*!sc*/
.jYfgHQ:hover:not([disabled]){background-color:#30363d;}/*!sc*/
.jYfgHQ:active:not([disabled]){background-color:#161b22;}/*!sc*/
.jYfgHQ[aria-expanded=true]{background-color:#161b22;}/*!sc*/
.jYfgHQ[data-component="IconButton"][data-no-visuals]{color:#7d8590;}/*!sc*/
.jYfgHQ[data-no-visuals]{color:#2f81f7;}/*!sc*/
.jYfgHQ:has([data-component="ButtonCounter"]){color:#2f81f7;}/*!sc*/
.jYfgHQ:disabled[data-no-visuals]{color:#484f58;}/*!sc*/
.jYfgHQ:disabled[data-no-visuals] [data-component=ButtonCounter]{color:inherit;}/*!sc*/
.jYfgHQ[data-size="small"][data-no-visuals="true"]{color:#7d8590;}/*!sc*/
data-styled.g27[id="types__StyledButton-sc-ws60qy-0"]{content:"cmNjCr,lhczWi,hPfySA,bZkSFv,ePclzw,hPOZTU,jcILRt,dzga-dt,dWukOn,kGDoCG,hHvcfT,kCdBku,jcdBXR,bwYDFy,bhUFcA,jYfgHQ,"}/*!sc*/
.fCnxTL{position:relative;display:inline-block;}/*!sc*/
.fCnxTL::before{position:absolute;z-index:1000001;display:none;width:0px;height:0px;color:#6e7681;pointer-events:none;content:'';border:6px solid transparent;opacity:0;}/*!sc*/
.fCnxTL::after{position:absolute;z-index:1000000;display:none;padding:0.5em 0.75em;font:normal normal 11px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",Helvetica,Arial,sans-serif,"Apple Color Emoji","Segoe UI Emoji";-webkit-font-smoothing:subpixel-antialiased;color:#ffffff;text-align:center;-webkit-text-decoration:none;text-decoration:none;text-shadow:none;text-transform:none;-webkit-letter-spacing:normal;-moz-letter-spacing:normal;-ms-letter-spacing:normal;letter-spacing:normal;word-wrap:break-word;white-space:pre;pointer-events:none;content:attr(aria-label);background:#6e7681;border-radius:3px;opacity:0;}/*!sc*/
@-webkit-keyframes tooltip-appear{from{opacity:0;}to{opacity:1;}}/*!sc*/
@keyframes tooltip-appear{from{opacity:0;}to{opacity:1;}}/*!sc*/
.fCnxTL:hover::before,.fCnxTL:active::before,.fCnxTL:focus::before,.fCnxTL:focus-within::before,.fCnxTL:hover::after,.fCnxTL:active::after,.fCnxTL:focus::after,.fCnxTL:focus-within::after{display:inline-block;-webkit-text-decoration:none;text-decoration:none;-webkit-animation-name:tooltip-appear;animation-name:tooltip-appear;-webkit-animation-duration:0.1s;animation-duration:0.1s;-webkit-animation-fill-mode:forwards;animation-fill-mode:forwards;-webkit-animation-timing-function:ease-in;animation-timing-function:ease-in;-webkit-animation-delay:0.4s;animation-delay:0.4s;}/*!sc*/
.fCnxTL.tooltipped-no-delay:hover::before,.fCnxTL.tooltipped-no-delay:active::before,.fCnxTL.tooltipped-no-delay:focus::before,.fCnxTL.tooltipped-no-delay:focus-within::before,.fCnxTL.tooltipped-no-delay:hover::after,.fCnxTL.tooltipped-no-delay:active::after,.fCnxTL.tooltipped-no-delay:focus::after,.fCnxTL.tooltipped-no-delay:focus-within::after{-webkit-animation-delay:0s;animation-delay:0s;}/*!sc*/
.fCnxTL.tooltipped-multiline:hover::after,.fCnxTL.tooltipped-multiline:active::after,.fCnxTL.tooltipped-multiline:focus::after,.fCnxTL.tooltipped-multiline:focus-within::after{display:table-cell;}/*!sc*/
.fCnxTL.tooltipped-s::after,.fCnxTL.tooltipped-se::after,.fCnxTL.tooltipped-sw::after{top:100%;right:50%;margin-top:6px;}/*!sc*/
.fCnxTL.tooltipped-s::before,.fCnxTL.tooltipped-se::before,.fCnxTL.tooltipped-sw::before{top:auto;right:50%;bottom:-7px;margin-right:-6px;border-bottom-color:#6e7681;}/*!sc*/
.fCnxTL.tooltipped-se::after{right:auto;left:50%;margin-left:-16px;}/*!sc*/
.fCnxTL.tooltipped-sw::after{margin-right:-16px;}/*!sc*/
.fCnxTL.tooltipped-n::after,.fCnxTL.tooltipped-ne::after,.fCnxTL.tooltipped-nw::after{right:50%;bottom:100%;margin-bottom:6px;}/*!sc*/
.fCnxTL.tooltipped-n::before,.fCnxTL.tooltipped-ne::before,.fCnxTL.tooltipped-nw::before{top:-7px;right:50%;bottom:auto;margin-right:-6px;border-top-color:#6e7681;}/*!sc*/
.fCnxTL.tooltipped-ne::after{right:auto;left:50%;margin-left:-16px;}/*!sc*/
.fCnxTL.tooltipped-nw::after{margin-right:-16px;}/*!sc*/
.fCnxTL.tooltipped-s::after,.fCnxTL.tooltipped-n::after{-webkit-transform:translateX(50%);-ms-transform:translateX(50%);transform:translateX(50%);}/*!sc*/
.fCnxTL.tooltipped-w::after{right:100%;bottom:50%;margin-right:6px;-webkit-transform:translateY(50%);-ms-transform:translateY(50%);transform:translateY(50%);}/*!sc*/
.fCnxTL.tooltipped-w::before{top:50%;bottom:50%;left:-7px;margin-top:-6px;border-left-color:#6e7681;}/*!sc*/
.fCnxTL.tooltipped-e::after{bottom:50%;left:100%;margin-left:6px;-webkit-transform:translateY(50%);-ms-transform:translateY(50%);transform:translateY(50%);}/*!sc*/
.fCnxTL.tooltipped-e::before{top:50%;right:-7px;bottom:50%;margin-top:-6px;border-right-color:#6e7681;}/*!sc*/
.fCnxTL.tooltipped-multiline::after{width:-webkit-max-content;width:-moz-max-content;width:max-content;max-width:250px;word-wrap:break-word;white-space:pre-line;border-collapse:separate;}/*!sc*/
.fCnxTL.tooltipped-multiline.tooltipped-s::after,.fCnxTL.tooltipped-multiline.tooltipped-n::after{right:auto;left:50%;-webkit-transform:translateX(-50%);-ms-transform:translateX(-50%);transform:translateX(-50%);}/*!sc*/
.fCnxTL.tooltipped-multiline.tooltipped-w::after,.fCnxTL.tooltipped-multiline.tooltipped-e::after{right:100%;}/*!sc*/
.fCnxTL.tooltipped-align-right-2::after{right:0;margin-right:0;}/*!sc*/
.fCnxTL.tooltipped-align-right-2::before{right:15px;}/*!sc*/
.fCnxTL.tooltipped-align-left-2::after{left:0;margin-left:0;}/*!sc*/
.fCnxTL.tooltipped-align-left-2::before{left:10px;}/*!sc*/
data-styled.g28[id="Tooltip__TooltipBase-sc-uha8qm-0"]{content:"fCnxTL,"}/*!sc*/
.cDLBls{border:0;font-size:inherit;font-family:inherit;background-color:transparent;-webkit-appearance:none;color:inherit;width:100%;}/*!sc*/
.cDLBls:focus{outline:0;}/*!sc*/
data-styled.g29[id="UnstyledTextInput-sc-14ypya-0"]{content:"cDLBls,"}/*!sc*/
.bOMzPg{min-width:0;}/*!sc*/
.fWVgeN{padding-left:4px;padding-right:4px;font-weight:400;color:#7d8590;font-size:16px;}/*!sc*/
.hfRvxg{color:#e6edf3;}/*!sc*/
.iqTHmv{padding-left:4px;padding-right:4px;font-weight:400;color:#7d8590;font-size:14px;}/*!sc*/
data-styled.g35[id="Text-sc-17v1xeu-0"]{content:"bOMzPg,fWVgeN,hfRvxg,gPDEWA,iqTHmv,"}/*!sc*/
.cjbBGq{display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;vertical-align:middle;isolation:isolate;}/*!sc*/
.cjbBGq.cjbBGq > *{margin-inline-end:-1px;position:relative;border-radius:0;}/*!sc*/
.cjbBGq.cjbBGq > *:first-child{border-top-left-radius:6px;border-bottom-left-radius:6px;}/*!sc*/
.cjbBGq.cjbBGq > *:last-child{border-top-right-radius:6px;border-bottom-right-radius:6px;}/*!sc*/
.cjbBGq.cjbBGq > *:focus,.cjbBGq.cjbBGq > *:active,.cjbBGq.cjbBGq > *:hover{z-index:1;}/*!sc*/
data-styled.g84[id="ButtonGroup-sc-1gxhls1-0"]{content:"cjbBGq,"}/*!sc*/
.bFrOJy{--segmented-control-button-inner-padding:12px;--segmented-control-button-bg-inset:4px;--segmented-control-outer-radius:6px;background-color:transparent;border-color:transparent;border-radius:var(--segmented-control-outer-radius);border-width:0;color:currentColor;cursor:pointer;font-family:inherit;font-size:inherit;font-weight:600;padding:0;height:100%;width:100%;}/*!sc*/
.bFrOJy .segmentedControl-content{-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;background-color:#0d1117;border-color:#6e7681;border-style:solid;border-width:1px;border-radius:var(--segmented-control-outer-radius);display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;height:100%;-webkit-box-pack:center;-webkit-justify-content:center;-ms-flex-pack:center;justify-content:center;padding-left:var(--segmented-control-button-inner-padding);padding-right:var(--segmented-control-button-inner-padding);}/*!sc*/
.bFrOJy svg{fill:#7d8590;}/*!sc*/
.bFrOJy:focus:focus-visible:not(:last-child):after{width:0;}/*!sc*/
.bFrOJy .segmentedControl-text:after{content:"Code";display:block;font-weight:600;height:0;overflow:hidden;pointer-events:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;visibility:hidden;}/*!sc*/
@media (pointer:coarse){.bFrOJy:before{content:"";position:absolute;left:0;right:0;-webkit-transform:translateY(-50%);-ms-transform:translateY(-50%);transform:translateY(-50%);top:50%;min-height:44px;}}/*!sc*/
.dAXkSP{--segmented-control-button-inner-padding:12px;--segmented-control-button-bg-inset:4px;--segmented-control-outer-radius:6px;background-color:transparent;border-color:transparent;border-radius:var(--segmented-control-outer-radius);border-width:0;color:currentColor;cursor:pointer;font-family:inherit;font-size:inherit;font-weight:400;padding:var(--segmented-control-button-bg-inset);height:100%;width:100%;}/*!sc*/
.dAXkSP .segmentedControl-content{-webkit-align-items:center;-webkit-box-align:center;-ms-flex-align:center;align-items:center;background-color:transparent;border-color:transparent;border-style:solid;border-width:1px;border-radius:calc(var(--segmented-control-outer-radius) - var(--segmented-control-button-bg-inset) / 2);display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;height:100%;-webkit-box-pack:center;-webkit-justify-content:center;-ms-flex-pack:center;justify-content:center;padding-left:calc(var(--segmented-control-button-inner-padding) - var(--segmented-control-button-bg-inset));padding-right:calc(var(--segmented-control-button-inner-padding) - var(--segmented-control-button-bg-inset));}/*!sc*/
.dAXkSP svg{fill:#7d8590;}/*!sc*/
.dAXkSP:hover .segmentedControl-content{background-color:#30363d;}/*!sc*/
.dAXkSP:active .segmentedControl-content{background-color:#21262d;}/*!sc*/
.dAXkSP:focus:focus-visible:not(:last-child):after{width:0;}/*!sc*/
.dAXkSP .segmentedControl-text:after{content:"Blame";display:block;font-weight:600;height:0;overflow:hidden;pointer-events:none;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;visibility:hidden;}/*!sc*/
@media (pointer:coarse){.dAXkSP:before{content:"";position:absolute;left:0;right:0;-webkit-transform:translateY(-50%);-ms-transform:translateY(-50%);transform:translateY(-50%);top:50%;min-height:44px;}}/*!sc*/
data-styled.g91[id="SegmentedControlButton__SegmentedControlButtonStyled-sc-8lkgxl-0"]{content:"bFrOJy,dAXkSP,"}/*!sc*/
.ivYJSK{background-color:rgba(110,118,129,0.1);border-radius:6px;display:-webkit-inline-box;display:-webkit-inline-flex;display:-ms-inline-flexbox;display:inline-flex;font-size:14px;height:28px;margin:0;padding:0;}/*!sc*/
data-styled.g93[id="SegmentedControl__SegmentedControlList-sc-1rzig82-0"]{content:"ivYJSK,"}/*!sc*/
body[data-page-layout-dragging="true"]{cursor:col-resize;}/*!sc*/
body[data-page-layout-dragging="true"] *{-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;}/*!sc*/
data-styled.g97[id="sc-global-gbKrvU1"]{content:"sc-global-gbKrvU1,"}/*!sc*/
</style><meta data-hydrostats="publish"/> <!-- --> <!-- --> <!-- --> <button hidden="" data-testid="header-permalink-button" data-hotkey-scope="read-only-cursor-text-area"></button><button hidden=""></button><div class="Box-sc-g0xbh4-0"><div style="--sticky-pane-height:100vh" class="Box-sc-g0xbh4-0 fSWWem"><div class="Box-sc-g0xbh4-0 kPPmzM"><div class="Box-sc-g0xbh4-0 cIAPDV"><div tabindex="0" class="Box-sc-g0xbh4-0 gvCnwW"><div class="Box-sc-g0xbh4-0 ioxSsX"><div class="Box-sc-g0xbh4-0 eUyHuk"></div><div class="Box-sc-g0xbh4-0 hAeDYA"><div role="separator" class="Box-sc-g0xbh4-0 dZCkhR"></div></div><div style="--pane-width:320px" class="Box-sc-g0xbh4-0 gNdDUH"><span class="_VisuallyHidden__VisuallyHidden-sc-11jhm7a-0 rTZSs"><form><label for=":Rdjal5:-width-input">Pane width</label><p id=":Rdjal5:-input-hint">Use a value between <!-- -->0<!-- -->% and <!-- -->0<!-- -->%</p><input id=":Rdjal5:-width-input" aria-describedby=":Rdjal5:-input-hint" name="pane-width" inputMode="numeric" pattern="[0-9]*" autoCorrect="off" autoComplete="off" type="text" value=""/><button type="submit">Change width</button></form></span><div class="Box-sc-g0xbh4-0 react-tree-pane-contents"><div id="repos-file-tree" class="Box-sc-g0xbh4-0 jywUSN"><div class="Box-sc-g0xbh4-0 hBSSUC"><div class="Box-sc-g0xbh4-0 iPurHz"><h2 class="Heading__StyledHeading-sc-1c1dgg0-0 fNPcqd"><button type="button" aria-label="Expand side panel" data-testid="expand-file-tree-button-mobile" class="types__StyledButton-sc-ws60qy-0 cmNjCr"><span data-component="buttonContent" class="Box-sc-g0xbh4-0 kkrdEu"><span data-component="leadingVisual" class="Box-sc-g0xbh4-0 trpoQ"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-arrow-left" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M7.78 12.53a.75.75 0 0 1-1.06 0L2.47 8.28a.75.75 0 0 1 0-1.06l4.25-4.25a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042L4.81 7h7.44a.75.75 0 0 1 0 1.5H4.81l2.97 2.97a.75.75 0 0 1 0 1.06Z"></path></svg></span><span data-component="text">Files</span></span></button><button data-component="IconButton" type="button" data-testid="collapse-file-tree-button" aria-label="Side panel" aria-expanded="true" aria-controls="repos-file-tree" class="types__StyledButton-sc-ws60qy-0 lhczWi" data-no-visuals="true"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-sidebar-expand" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="m4.177 7.823 2.396-2.396A.25.25 0 0 1 7 5.604v4.792a.25.25 0 0 1-.427.177L4.177 8.177a.25.25 0 0 1 0-.354Z"></path><path d="M0 1.75C0 .784.784 0 1.75 0h12.5C15.216 0 16 .784 16 1.75v12.5A1.75 1.75 0 0 1 14.25 16H1.75A1.75 1.75 0 0 1 0 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25H9.5v-13Zm12.5 13a.25.25 0 0 0 .25-.25V1.75a.25.25 0 0 0-.25-.25H11v13Z"></path></svg></button><button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button></h2><h2 class="Heading__StyledHeading-sc-1c1dgg0-0 imcwCi">Files</h2></div><div class="Box-sc-g0xbh4-0 hVHHYa"><div class="Box-sc-g0xbh4-0 idZfsJ"><button type="button" id="branch-picker-repos-header-ref-selector" aria-haspopup="true" tabindex="0" aria-label="2023.10.1 tag" data-testid="anchor-button" class="types__StyledButton-sc-ws60qy-0 hPfySA react-repos-tree-pane-ref-selector width-full ref-selector-class"><span data-component="buttonContent" class="Box-sc-g0xbh4-0 kkrdEu"><span data-component="text"><div class="Box-sc-g0xbh4-0 bKgizp"><div class="Box-sc-g0xbh4-0 bwTunw"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-tag" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M1 7.775V2.75C1 1.784 1.784 1 2.75 1h5.025c.464 0 .91.184 1.238.513l6.25 6.25a1.75 1.75 0 0 1 0 2.474l-5.026 5.026a1.75 1.75 0 0 1-2.474 0l-6.25-6.25A1.752 1.752 0 0 1 1 7.775Zm1.5 0c0 .066.026.13.073.177l6.25 6.25a.25.25 0 0 0 .354 0l5.025-5.025a.25.25 0 0 0 0-.354l-6.25-6.25a.25.25 0 0 0-.177-.073H2.75a.25.25 0 0 0-.25.25ZM6 5a1 1 0 1 1 0 2 1 1 0 0 1 0-2Z"></path></svg></div><div class="Box-sc-g0xbh4-0 caeYDk"><span class="Text-sc-17v1xeu-0 bOMzPg"> <!-- -->2023.10.1</span></div></div></span><span data-component="trailingVisual" class="Box-sc-g0xbh4-0 trpoQ"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-triangle-down" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="m4.427 7.427 3.396 3.396a.25.25 0 0 0 .354 0l3.396-3.396A.25.25 0 0 0 11.396 7H4.604a.25.25 0 0 0-.177.427Z"></path></svg></span></span></button><button hidden="" data-hotkey-scope="read-only-cursor-text-area"></button></div><div class="Box-sc-g0xbh4-0 jahcnb"><button data-component="IconButton" type="button" aria-label="Search this repository" data-no-visuals="true" class="types__StyledButton-sc-ws60qy-0 bZkSFv"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-search" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M10.68 11.74a6 6 0 0 1-7.922-8.982 6 6 0 0 1 8.982 7.922l3.04 3.04a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215ZM11.5 7a4.499 4.499 0 1 0-8.997 0A4.499 4.499 0 0 0 11.5 7Z"></path></svg></button><button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button></div></div></div><div class="Box-sc-g0xbh4-0 ccToMy"><button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button><button hidden=""></button><span class="TextInputWrapper__TextInputBaseWrapper-sc-1mqhpbi-0 TextInputWrapper-sc-1mqhpbi-1 hSXtjz hZMmEi TextInput-wrapper" aria-busy="false"><span class="TextInput-icon"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-search" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M10.68 11.74a6 6 0 0 1-7.922-8.982 6 6 0 0 1 8.982 7.922l3.04 3.04a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215ZM11.5 7a4.499 4.499 0 1 0-8.997 0A4.499 4.499 0 0 0 11.5 7Z"></path></svg></span><input type="text" aria-label="Go to file" role="combobox" aria-controls="file-results-list" aria-expanded="false" aria-haspopup="dialog" autoCorrect="off" spellcheck="false" placeholder="Go to file" data-component="input" class="UnstyledTextInput-sc-14ypya-0 cDLBls" value=""/><span class="TextInput-icon"><div class="Box-sc-g0xbh4-0 cNvKlH"><kbd>t</kbd></div></span></span></div><div class="Box-sc-g0xbh4-0 cLfAnm"><div class="react-tree-show-tree-items"><div data-testid="repos-file-tree-container" class="Box-sc-g0xbh4-0 erWCJP"><div class="Box-sc-g0xbh4-0 fUswPC"><svg height="32px" width="32px" viewBox="0 0 16 16" fill="none" aria-label="Loading file tree" class="Spinner__StyledSpinner-sc-1knt686-0 hPEVNM"><circle cx="8" cy="8" r="7" stroke="currentColor" stroke-opacity="0.25" stroke-width="2" vector-effect="non-scaling-stroke"></circle><path d="M15 8a7.002 7.002 0 00-7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" vector-effect="non-scaling-stroke"></path></svg></div></div></div><div class="Box-sc-g0xbh4-0 hwhShM"><div class="Box-sc-g0xbh4-0 cYPxpP"><a href="https://docs.github.com/repositories/working-with-files/using-files/navigating-code-on-github" target="_blank" class="Link__StyledLink-sc-14289xe-0 bJBoUI">Documentation</a> • <a href="https://github.com/orgs/community/discussions/54546" target="_blank" class="Link__StyledLink-sc-14289xe-0 bJBoUI">Share feedback</a></div></div></div><div class="Box-sc-g0xbh4-0 fBtiVT"><div class="Box-sc-g0xbh4-0 cYPxpP"><a href="https://docs.github.com/repositories/working-with-files/using-files/navigating-code-on-github" target="_blank" class="Link__StyledLink-sc-14289xe-0 bJBoUI">Documentation</a> • <a href="https://github.com/orgs/community/discussions/54546" target="_blank" class="Link__StyledLink-sc-14289xe-0 bJBoUI">Share feedback</a></div></div></div></div></div></div></div><main class="Box-sc-g0xbh4-0 emFMJu"><div class="Box-sc-g0xbh4-0"></div><div class="Box-sc-g0xbh4-0 hlUAHL"><div data-selector="repos-split-pane-content" tabindex="0" class="Box-sc-g0xbh4-0 iStsmI"><div class="Box-sc-g0xbh4-0 eIgvIk"><div class="Box-sc-g0xbh4-0 eVFfWF container"><div class="Box-sc-g0xbh4-0 kgXdnT react-code-view-header--narrow"><div class="Box-sc-g0xbh4-0 kzTa-dF"><div class="Box-sc-g0xbh4-0 bbXCl"><h2 class="Heading__StyledHeading-sc-1c1dgg0-0 fNPcqd"><button type="button" aria-label="Expand side panel" data-testid="expand-file-tree-button-mobile" class="types__StyledButton-sc-ws60qy-0 cmNjCr"><span data-component="buttonContent" class="Box-sc-g0xbh4-0 kkrdEu"><span data-component="leadingVisual" class="Box-sc-g0xbh4-0 trpoQ"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-arrow-left" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M7.78 12.53a.75.75 0 0 1-1.06 0L2.47 8.28a.75.75 0 0 1 0-1.06l4.25-4.25a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042L4.81 7h7.44a.75.75 0 0 1 0 1.5H4.81l2.97 2.97a.75.75 0 0 1 0 1.06Z"></path></svg></span><span data-component="text">Files</span></span></button><button data-component="IconButton" type="button" data-testid="collapse-file-tree-button" aria-label="Side panel" aria-expanded="true" aria-controls="repos-file-tree" class="types__StyledButton-sc-ws60qy-0 lhczWi" data-no-visuals="true"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-sidebar-expand" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="m4.177 7.823 2.396-2.396A.25.25 0 0 1 7 5.604v4.792a.25.25 0 0 1-.427.177L4.177 8.177a.25.25 0 0 1 0-.354Z"></path><path d="M0 1.75C0 .784.784 0 1.75 0h12.5C15.216 0 16 .784 16 1.75v12.5A1.75 1.75 0 0 1 14.25 16H1.75A1.75 1.75 0 0 1 0 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25H9.5v-13Zm12.5 13a.25.25 0 0 0 .25-.25V1.75a.25.25 0 0 0-.25-.25H11v13Z"></path></svg></button><button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button></h2><div class="Box-sc-g0xbh4-0 hGGMNu"><div class="Box-sc-g0xbh4-0 eHRrYV"><button type="button" id="branch-picker-repos-header-ref-selector-narrow" aria-haspopup="true" tabindex="0" aria-label="2023.10.1 tag" data-testid="anchor-button" class="types__StyledButton-sc-ws60qy-0 ePclzw ref-selector-class"><span data-component="buttonContent" class="Box-sc-g0xbh4-0 kkrdEu"><span data-component="text"><div class="Box-sc-g0xbh4-0 bKgizp"><div class="Box-sc-g0xbh4-0 bwTunw"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-tag" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M1 7.775V2.75C1 1.784 1.784 1 2.75 1h5.025c.464 0 .91.184 1.238.513l6.25 6.25a1.75 1.75 0 0 1 0 2.474l-5.026 5.026a1.75 1.75 0 0 1-2.474 0l-6.25-6.25A1.752 1.752 0 0 1 1 7.775Zm1.5 0c0 .066.026.13.073.177l6.25 6.25a.25.25 0 0 0 .354 0l5.025-5.025a.25.25 0 0 0 0-.354l-6.25-6.25a.25.25 0 0 0-.177-.073H2.75a.25.25 0 0 0-.25.25ZM6 5a1 1 0 1 1 0 2 1 1 0 0 1 0-2Z"></path></svg></div><div class="Box-sc-g0xbh4-0 dKmYfk"><span class="Text-sc-17v1xeu-0 bOMzPg"> <!-- -->2023.10.1</span></div></div></span><span data-component="trailingVisual" class="Box-sc-g0xbh4-0 trpoQ"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-triangle-down" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="m4.427 7.427 3.396 3.396a.25.25 0 0 0 .354 0l3.396-3.396A.25.25 0 0 0 11.396 7H4.604a.25.25 0 0 0-.177.427Z"></path></svg></span></span></button><button hidden="" data-hotkey-scope="read-only-cursor-text-area"></button></div> <button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button><button hidden=""></button><button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button><button hidden=""></button><button type="button" data-no-visuals="true" class="types__StyledButton-sc-ws60qy-0 hPOZTU"><span data-component="buttonContent" class="Box-sc-g0xbh4-0 kkrdEu"><span data-component="text">Blame</span></span></button><button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button><button data-component="IconButton" type="button" aria-label="More file actions" class="types__StyledButton-sc-ws60qy-0 jcILRt js-blob-dropdown-click" title="More file actions" data-testid="more-file-actions-button" id=":R9aaqjal5:" aria-haspopup="true" tabindex="0" data-no-visuals="true"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-kebab-horizontal" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M8 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM1.5 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Zm13 0a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path></svg></button> </div></div><div class="Box-sc-g0xbh4-0 hSNzKh"><div class="Box-sc-g0xbh4-0 eTvGbF"><nav data-testid="breadcrumbs" aria-labelledby="repos-header-breadcrumb-mobile-heading" id="repos-header-breadcrumb-mobile" class="Box-sc-g0xbh4-0 kzRgrI"><h2 class="Heading__StyledHeading-sc-1c1dgg0-0 cgQnMS sr-only" data-testid="screen-reader-heading" id="repos-header-breadcrumb-mobile-heading">Breadcrumbs</h2><ol class="Box-sc-g0xbh4-0 cmAPIB"><li class="Box-sc-g0xbh4-0 jwXCBK"><a sx="[object Object]" data-testid="breadcrumbs-repo-link" class="Link__StyledLink-sc-14289xe-0 iJtJJh" href="/home-assistant/core/tree/2023.10.1">core</a></li><li class="Box-sc-g0xbh4-0 jwXCBK"><span aria-hidden="true" class="Text-sc-17v1xeu-0 fWVgeN">/</span><a sx="[object Object]" class="Link__StyledLink-sc-14289xe-0 hUWqlv" href="/home-assistant/core/tree/2023.10.1/homeassistant">homeassistant</a></li><li class="Box-sc-g0xbh4-0 jwXCBK"><span aria-hidden="true" class="Text-sc-17v1xeu-0 fWVgeN">/</span><a sx="[object Object]" class="Link__StyledLink-sc-14289xe-0 hUWqlv" href="/home-assistant/core/tree/2023.10.1/homeassistant/components">components</a></li><li class="Box-sc-g0xbh4-0 jwXCBK"><span aria-hidden="true" class="Text-sc-17v1xeu-0 fWVgeN">/</span><a sx="[object Object]" class="Link__StyledLink-sc-14289xe-0 hUWqlv" href="/home-assistant/core/tree/2023.10.1/homeassistant/components/mazda">mazda</a></li></ol></nav><div data-testid="breadcrumbs-filename" class="Box-sc-g0xbh4-0 jwXCBK"><span aria-hidden="true" class="Text-sc-17v1xeu-0 fWVgeN">/</span><h1 tabindex="-1" id="file-name-id-mobile" class="Heading__StyledHeading-sc-1c1dgg0-0 diwsLq">diagnostics.py</h1></div><button data-component="IconButton" type="button" aria-label="Copy path" data-testid="breadcrumb-copy-path-button" data-size="small" data-no-visuals="true" class="types__StyledButton-sc-ws60qy-0 dzga-dt"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-copy" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg></button></div></div></div></div><div id="StickyHeader" class="Box-sc-g0xbh4-0 bDwCYs react-code-view-header--wide"><div class="Box-sc-g0xbh4-0 fywjmm"><div class="Box-sc-g0xbh4-0 dyczTK"><div class="Box-sc-g0xbh4-0 kszRgZ"><div class="Box-sc-g0xbh4-0 eTvGbF"><nav data-testid="breadcrumbs" aria-labelledby="repos-header-breadcrumb-wide-heading" id="repos-header-breadcrumb-wide" class="Box-sc-g0xbh4-0 kzRgrI"><h2 class="Heading__StyledHeading-sc-1c1dgg0-0 cgQnMS sr-only" data-testid="screen-reader-heading" id="repos-header-breadcrumb-wide-heading">Breadcrumbs</h2><ol class="Box-sc-g0xbh4-0 cmAPIB"><li class="Box-sc-g0xbh4-0 jwXCBK"><a sx="[object Object]" data-testid="breadcrumbs-repo-link" class="Link__StyledLink-sc-14289xe-0 iJtJJh" href="/home-assistant/core/tree/2023.10.1">core</a></li><li class="Box-sc-g0xbh4-0 jwXCBK"><span aria-hidden="true" class="Text-sc-17v1xeu-0 fWVgeN">/</span><a sx="[object Object]" class="Link__StyledLink-sc-14289xe-0 hUWqlv" href="/home-assistant/core/tree/2023.10.1/homeassistant">homeassistant</a></li><li class="Box-sc-g0xbh4-0 jwXCBK"><span aria-hidden="true" class="Text-sc-17v1xeu-0 fWVgeN">/</span><a sx="[object Object]" class="Link__StyledLink-sc-14289xe-0 hUWqlv" href="/home-assistant/core/tree/2023.10.1/homeassistant/components">components</a></li><li class="Box-sc-g0xbh4-0 jwXCBK"><span aria-hidden="true" class="Text-sc-17v1xeu-0 fWVgeN">/</span><a sx="[object Object]" class="Link__StyledLink-sc-14289xe-0 hUWqlv" href="/home-assistant/core/tree/2023.10.1/homeassistant/components/mazda">mazda</a></li></ol></nav><div data-testid="breadcrumbs-filename" class="Box-sc-g0xbh4-0 jwXCBK"><span aria-hidden="true" class="Text-sc-17v1xeu-0 fWVgeN">/</span><h1 tabindex="-1" id="file-name-id-wide" class="Heading__StyledHeading-sc-1c1dgg0-0 diwsLq">diagnostics.py</h1></div><button data-component="IconButton" type="button" aria-label="Copy path" data-testid="breadcrumb-copy-path-button" data-size="small" data-no-visuals="true" class="types__StyledButton-sc-ws60qy-0 dzga-dt"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-copy" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg></button></div></div><div class="Box-sc-g0xbh4-0 gtBUEp"><div class="d-flex gap-2"> <button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button><button hidden=""></button><button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button><button hidden=""></button><button type="button" data-no-visuals="true" class="types__StyledButton-sc-ws60qy-0 hPOZTU"><span data-component="buttonContent" class="Box-sc-g0xbh4-0 kkrdEu"><span data-component="text">Blame</span></span></button><button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button><button data-component="IconButton" type="button" aria-label="More file actions" class="types__StyledButton-sc-ws60qy-0 jcILRt js-blob-dropdown-click" title="More file actions" data-testid="more-file-actions-button" id=":R9pkqjal5:" aria-haspopup="true" tabindex="0" data-no-visuals="true"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-kebab-horizontal" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M8 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM1.5 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Zm13 0a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path></svg></button> </div></div></div></div></div></div></div><div class="Box-sc-g0xbh4-0 MERGN react-code-view-bottom-padding"> <div class="Box-sc-g0xbh4-0 cMYnca"></div><div class="Box-sc-g0xbh4-0"></div> <!-- --> <!-- --> </div><div class="Box-sc-g0xbh4-0 MERGN"> <!-- --> <!-- --> <button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button><button hidden=""></button><div class="Box-sc-g0xbh4-0 brFBoI"><div class="Box-sc-g0xbh4-0 eYedVD"><h2 class="Heading__StyledHeading-sc-1c1dgg0-0 cgQnMS sr-only" data-testid="screen-reader-heading">Latest commit</h2><div style="width:120px" class="Skeleton Skeleton--text" data-testid="loading"> </div><div class="Box-sc-g0xbh4-0 jGfYmh"><div data-testid="latest-commit-details" class="Box-sc-g0xbh4-0 lhFvfi"></div><h2 class="Heading__StyledHeading-sc-1c1dgg0-0 cgQnMS sr-only" data-testid="screen-reader-heading">History</h2><a aria-label="Commit history" class="types__StyledButton-sc-ws60qy-0 dWukOn react-last-commit-history-group" href="/home-assistant/core/commits/2023.10.1/homeassistant/components/mazda/diagnostics.py" data-size="small"><span data-component="buttonContent" class="Box-sc-g0xbh4-0 kkrdEu"><span data-component="leadingVisual" class="Box-sc-g0xbh4-0 trpoQ"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-history" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="m.427 1.927 1.215 1.215a8.002 8.002 0 1 1-1.6 5.685.75.75 0 1 1 1.493-.154 6.5 6.5 0 1 0 1.18-4.458l1.358 1.358A.25.25 0 0 1 3.896 6H.25A.25.25 0 0 1 0 5.75V2.104a.25.25 0 0 1 .427-.177ZM7.75 4a.75.75 0 0 1 .75.75v2.992l2.028.812a.75.75 0 0 1-.557 1.392l-2.5-1A.751.751 0 0 1 7 8.25v-3.5A.75.75 0 0 1 7.75 4Z"></path></svg></span><span data-component="text"><span class="Text-sc-17v1xeu-0 hfRvxg">History</span></span></span></a><div class="Box-sc-g0xbh4-0 bqgLjk"></div><span role="tooltip" aria-label="Commit history" class="Tooltip__TooltipBase-sc-uha8qm-0 fCnxTL tooltipped-n"><a aria-label="Commit history" class="types__StyledButton-sc-ws60qy-0 dWukOn react-last-commit-history-icon" href="/home-assistant/core/commits/2023.10.1/homeassistant/components/mazda/diagnostics.py"><span data-component="buttonContent" class="Box-sc-g0xbh4-0 kkrdEu"><span data-component="leadingVisual" class="Box-sc-g0xbh4-0 trpoQ"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-history" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="m.427 1.927 1.215 1.215a8.002 8.002 0 1 1-1.6 5.685.75.75 0 1 1 1.493-.154 6.5 6.5 0 1 0 1.18-4.458l1.358 1.358A.25.25 0 0 1 3.896 6H.25A.25.25 0 0 1 0 5.75V2.104a.25.25 0 0 1 .427-.177ZM7.75 4a.75.75 0 0 1 .75.75v2.992l2.028.812a.75.75 0 0 1-.557 1.392l-2.5-1A.751.751 0 0 1 7 8.25v-3.5A.75.75 0 0 1 7.75 4Z"></path></svg></span></span></a></span></div></div></div><div class="Box-sc-g0xbh4-0 iJmJly"><div class="Box-sc-g0xbh4-0 jACbi container"><div class="Box-sc-g0xbh4-0 bSdwWB react-code-size-details-banner"><div class="Box-sc-g0xbh4-0 fleZSW react-code-size-details-banner"><div class="Box-sc-g0xbh4-0 fOEJrA text-mono"><div title="1.79 KB" data-testid="blob-size" class="Truncate__StyledTruncate-sc-23o1d2-0 fUpWeN"><span class="Text-sc-17v1xeu-0 gPDEWA">57 lines (42 loc) · 1.79 KB</span></div></div></div></div><div class="Box-sc-g0xbh4-0 gBKNLX react-blob-view-header-sticky" id="repos-sticky-header"><div class="Box-sc-g0xbh4-0 ePiodO"><div class="Box-sc-g0xbh4-0 react-blob-sticky-header"><div class="Box-sc-g0xbh4-0 kQJlnf"><div class="Box-sc-g0xbh4-0 gJICKO"><div class="Box-sc-g0xbh4-0 iZJewz"><nav data-testid="breadcrumbs" aria-labelledby="sticky-breadcrumb-heading" id="sticky-breadcrumb" class="Box-sc-g0xbh4-0 kzRgrI"><h2 class="Heading__StyledHeading-sc-1c1dgg0-0 cgQnMS sr-only" data-testid="screen-reader-heading" id="sticky-breadcrumb-heading">Breadcrumbs</h2><ol class="Box-sc-g0xbh4-0 cmAPIB"><li class="Box-sc-g0xbh4-0 jwXCBK"><a sx="[object Object]" data-testid="breadcrumbs-repo-link" class="Link__StyledLink-sc-14289xe-0 iJtJJh" href="/home-assistant/core/tree/2023.10.1">core</a></li><li class="Box-sc-g0xbh4-0 jwXCBK"><span aria-hidden="true" class="Text-sc-17v1xeu-0 iqTHmv">/</span><a sx="[object Object]" class="Link__StyledLink-sc-14289xe-0 hUWqlv" href="/home-assistant/core/tree/2023.10.1/homeassistant">homeassistant</a></li><li class="Box-sc-g0xbh4-0 jwXCBK"><span aria-hidden="true" class="Text-sc-17v1xeu-0 iqTHmv">/</span><a sx="[object Object]" class="Link__StyledLink-sc-14289xe-0 hUWqlv" href="/home-assistant/core/tree/2023.10.1/homeassistant/components">components</a></li><li class="Box-sc-g0xbh4-0 jwXCBK"><span aria-hidden="true" class="Text-sc-17v1xeu-0 iqTHmv">/</span><a sx="[object Object]" class="Link__StyledLink-sc-14289xe-0 hUWqlv" href="/home-assistant/core/tree/2023.10.1/homeassistant/components/mazda">mazda</a></li></ol></nav><div data-testid="breadcrumbs-filename" class="Box-sc-g0xbh4-0 jwXCBK"><span aria-hidden="true" class="Text-sc-17v1xeu-0 iqTHmv">/</span><h1 tabindex="-1" id="sticky-file-name-id" class="Heading__StyledHeading-sc-1c1dgg0-0 jAEDJk">diagnostics.py</h1></div></div><button type="button" data-size="small" class="types__StyledButton-sc-ws60qy-0 kGDoCG"><span data-component="buttonContent" class="Box-sc-g0xbh4-0 kkrdEu"><span data-component="leadingVisual" class="Box-sc-g0xbh4-0 trpoQ"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-arrow-up" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M3.47 7.78a.75.75 0 0 1 0-1.06l4.25-4.25a.75.75 0 0 1 1.06 0l4.25 4.25a.751.751 0 0 1-.018 1.042.751.751 0 0 1-1.042.018L9 4.81v7.44a.75.75 0 0 1-1.5 0V4.81L4.53 7.78a.75.75 0 0 1-1.06 0Z"></path></svg></span><span data-component="text">Top</span></span></button></div></div></div><div class="Box-sc-g0xbh4-0 bESQXL"><h2 class="Heading__StyledHeading-sc-1c1dgg0-0 cgQnMS sr-only" data-testid="screen-reader-heading">File metadata and controls</h2><div class="Box-sc-g0xbh4-0 bfkNRF"><ul aria-label="File view" class="SegmentedControl__SegmentedControlList-sc-1rzig82-0 ivYJSK"><li class="Box-sc-g0xbh4-0 fXBLEV"><button aria-current="true" class="SegmentedControlButton__SegmentedControlButtonStyled-sc-8lkgxl-0 bFrOJy"><span class="segmentedControl-content"><div class="Box-sc-g0xbh4-0 segmentedControl-text">Code</div></span></button></li><li class="Box-sc-g0xbh4-0 gbKtit"><button aria-current="false" class="SegmentedControlButton__SegmentedControlButtonStyled-sc-8lkgxl-0 dAXkSP"><span class="segmentedControl-content"><div class="Box-sc-g0xbh4-0 segmentedControl-text">Blame</div></span></button></li></ul><button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button><button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button><div class="Box-sc-g0xbh4-0 fleZSW react-code-size-details-in-header"><div class="Box-sc-g0xbh4-0 fOEJrA text-mono"><div title="1.79 KB" data-testid="blob-size" class="Truncate__StyledTruncate-sc-23o1d2-0 fUpWeN"><span class="Text-sc-17v1xeu-0 gPDEWA">57 lines (42 loc) · 1.79 KB</span></div></div></div></div><div class="Box-sc-g0xbh4-0 iBylDf"><div class="Box-sc-g0xbh4-0 kSGBPx react-blob-header-edit-and-raw-actions"><div class="ButtonGroup-sc-1gxhls1-0 cjbBGq"><a href="https://github.com/home-assistant/core/raw/2023.10.1/homeassistant/components/mazda/diagnostics.py" data-testid="raw-button" data-size="small" data-no-visuals="true" class="types__StyledButton-sc-ws60qy-0 hHvcfT"><span data-component="buttonContent" class="Box-sc-g0xbh4-0 kkrdEu"><span data-component="text">Raw</span></span></a><button data-component="IconButton" type="button" aria-label="Copy raw content" data-testid="copy-raw-button" data-size="small" data-no-visuals="true" class="types__StyledButton-sc-ws60qy-0 kCdBku"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-copy" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg></button><span role="tooltip" aria-label="Download raw file" class="Tooltip__TooltipBase-sc-uha8qm-0 fCnxTL tooltipped-n"><button data-component="IconButton" type="button" aria-label="Download raw content" data-testid="download-raw-button" data-size="small" data-no-visuals="true" class="types__StyledButton-sc-ws60qy-0 jcdBXR"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-download" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M2.75 14A1.75 1.75 0 0 1 1 12.25v-2.5a.75.75 0 0 1 1.5 0v2.5c0 .138.112.25.25.25h10.5a.25.25 0 0 0 .25-.25v-2.5a.75.75 0 0 1 1.5 0v2.5A1.75 1.75 0 0 1 13.25 14Z"></path><path d="M7.25 7.689V2a.75.75 0 0 1 1.5 0v5.689l1.97-1.969a.749.749 0 1 1 1.06 1.06l-3.25 3.25a.749.749 0 0 1-1.06 0L4.22 6.78a.749.749 0 1 1 1.06-1.06l1.97 1.969Z"></path></svg></button></span></div><button hidden="" data-testid="raw-button-shortcut" data-hotkey-scope="read-only-cursor-text-area"></button><button hidden="" data-testid="copy-raw-button-shortcut" data-hotkey-scope="read-only-cursor-text-area"></button><button hidden="" data-testid="download-raw-button-shortcut" data-hotkey-scope="read-only-cursor-text-area"></button><a class="Link__StyledLink-sc-14289xe-0 bJBoUI js-github-dev-shortcut d-none" href="https://github.dev/"></a><button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button><a class="Link__StyledLink-sc-14289xe-0 bJBoUI js-github-dev-new-tab-shortcut d-none" href="https://github.dev/" target="_blank"></a><button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button><div class="ButtonGroup-sc-1gxhls1-0 cjbBGq"><span role="tooltip" aria-label="You must be on a branch to make or propose changes to this file" class="Tooltip__TooltipBase-sc-uha8qm-0 fCnxTL tooltipped-nw"><button data-component="IconButton" type="button" aria-label="Edit file" class="types__StyledButton-sc-ws60qy-0 bwYDFy btn" aria-disabled="true" data-size="small" data-no-visuals="true"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-pencil" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M11.013 1.427a1.75 1.75 0 0 1 2.474 0l1.086 1.086a1.75 1.75 0 0 1 0 2.474l-8.61 8.61c-.21.21-.47.364-.756.445l-3.251.93a.75.75 0 0 1-.927-.928l.929-3.25c.081-.286.235-.547.445-.758l8.61-8.61Zm.176 4.823L9.75 4.81l-6.286 6.287a.253.253 0 0 0-.064.108l-.558 1.953 1.953-.558a.253.253 0 0 0 .108-.064Zm1.238-3.763a.25.25 0 0 0-.354 0L10.811 3.75l1.439 1.44 1.263-1.263a.25.25 0 0 0 0-.354Z"></path></svg></button></span><button data-component="IconButton" type="button" aria-label="More edit options" data-testid="more-edit-button" id=":Rl7pjqlajal5:" aria-haspopup="true" tabindex="0" data-size="small" data-no-visuals="true" class="types__StyledButton-sc-ws60qy-0 kCdBku"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-triangle-down" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="m4.427 7.427 3.396 3.396a.25.25 0 0 0 .354 0l3.396-3.396A.25.25 0 0 0 11.396 7H4.604a.25.25 0 0 0-.177.427Z"></path></svg></button></div></div><span role="tooltip" aria-label="Open symbols panel" class="Tooltip__TooltipBase-sc-uha8qm-0 fCnxTL tooltipped-nw"><button data-component="IconButton" type="button" aria-label="Symbols" aria-pressed="false" aria-expanded="false" aria-controls="symbols-pane" class="types__StyledButton-sc-ws60qy-0 bhUFcA" data-testid="symbols-button" id="symbols-button" data-size="small" data-no-visuals="true"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-code-square" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M0 1.75C0 .784.784 0 1.75 0h12.5C15.216 0 16 .784 16 1.75v12.5A1.75 1.75 0 0 1 14.25 16H1.75A1.75 1.75 0 0 1 0 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25V1.75a.25.25 0 0 0-.25-.25Zm7.47 3.97a.75.75 0 0 1 1.06 0l2 2a.75.75 0 0 1 0 1.06l-2 2a.749.749 0 0 1-1.275-.326.749.749 0 0 1 .215-.734L10.69 8 9.22 6.53a.75.75 0 0 1 0-1.06ZM6.78 6.53 5.31 8l1.47 1.47a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215l-2-2a.75.75 0 0 1 0-1.06l2-2a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042Z"></path></svg></button></span><div class="Box-sc-g0xbh4-0 react-blob-header-edit-and-raw-actions-combined"><button data-component="IconButton" type="button" aria-label="Edit and raw actions" class="types__StyledButton-sc-ws60qy-0 jYfgHQ js-blob-dropdown-click" title="More file actions" data-testid="more-file-actions-button" id=":R1dpjqlajal5:" aria-haspopup="true" tabindex="0" data-size="small" data-no-visuals="true"><svg aria-hidden="true" focusable="false" role="img" class="octicon octicon-kebab-horizontal" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M8 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM1.5 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Zm13 0a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path></svg></button></div></div></div></div><div class="Box-sc-g0xbh4-0"></div></div><div class="Box-sc-g0xbh4-0 etfROT"><section aria-labelledby="file-name-id-wide file-name-id-mobile" class="Box-sc-g0xbh4-0 jWnGGx"><div class="Box-sc-g0xbh4-0 TCenl"><div id="highlighted-line-menu-positioner" class="Box-sc-g0xbh4-0 cluMzC"><div id="copilot-button-positioner" class="Box-sc-g0xbh4-0 cluMzC"><div class="Box-sc-g0xbh4-0 eRkHwF"><div class="Box-sc-g0xbh4-0 knCTAx react-code-file-contents" role="presentation" aria-hidden="true" data-tab-size="8" data-paste-markdown-skip="true" data-hpc="true"><div class="react-line-numbers" style="pointer-events:auto"><div data-line-number="1" class="react-line-number react-code-text" style="padding-right:16px">1</div><div data-line-number="2" class="react-line-number react-code-text" style="padding-right:16px">2</div><div data-line-number="3" class="react-line-number react-code-text" style="padding-right:16px">3</div><div data-line-number="4" class="react-line-number react-code-text" style="padding-right:16px">4</div><div data-line-number="5" class="react-line-number react-code-text" style="padding-right:16px">5</div><div data-line-number="6" class="react-line-number react-code-text" style="padding-right:16px">6</div><div data-line-number="7" class="react-line-number react-code-text" style="padding-right:16px">7</div><div data-line-number="8" class="react-line-number react-code-text" style="padding-right:16px">8</div><div data-line-number="9" class="react-line-number react-code-text" style="padding-right:16px">9</div><div data-line-number="10" class="react-line-number react-code-text" style="padding-right:16px">10</div><div data-line-number="11" class="react-line-number react-code-text" style="padding-right:16px">11</div><div data-line-number="12" class="react-line-number react-code-text" style="padding-right:16px">12</div><div data-line-number="13" class="react-line-number react-code-text" style="padding-right:16px">13</div><div data-line-number="14" class="react-line-number react-code-text" style="padding-right:16px">14</div><div data-line-number="15" class="react-line-number react-code-text" style="padding-right:16px">15</div><div data-line-number="16" class="react-line-number react-code-text" style="padding-right:16px">16</div><div data-line-number="17" class="react-line-number react-code-text" style="padding-right:16px">17</div><div data-line-number="18" class="react-line-number react-code-text" style="padding-right:16px">18</div><div data-line-number="19" class="react-line-number react-code-text" style="padding-right:16px">19<span class="Box-sc-g0xbh4-0 hXUKEK"><div aria-label="Collapse code section" role="button" class="Box-sc-g0xbh4-0 cXzIIR"><svg aria-hidden="true" focusable="false" role="img" class="Octicon-sc-9kayk9-0" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M12.78 5.22a.749.749 0 0 1 0 1.06l-4.25 4.25a.749.749 0 0 1-1.06 0L3.22 6.28a.749.749 0 1 1 1.06-1.06L8 8.939l3.72-3.719a.749.749 0 0 1 1.06 0Z"></path></svg></div></span></div><div data-line-number="20" class="child-of-line-19  react-line-number react-code-text" style="padding-right:16px">20</div><div data-line-number="21" class="child-of-line-19  react-line-number react-code-text" style="padding-right:16px">21</div><div data-line-number="22" class="child-of-line-19  react-line-number react-code-text" style="padding-right:16px">22</div><div data-line-number="23" class="child-of-line-19  react-line-number react-code-text" style="padding-right:16px">23</div><div data-line-number="24" class="child-of-line-19  react-line-number react-code-text" style="padding-right:16px">24</div><div data-line-number="25" class="child-of-line-19  react-line-number react-code-text" style="padding-right:16px">25</div><div data-line-number="26" class="child-of-line-19  react-line-number react-code-text" style="padding-right:16px">26</div><div data-line-number="27" class="child-of-line-19  react-line-number react-code-text" style="padding-right:16px">27</div><div data-line-number="28" class="child-of-line-19  react-line-number react-code-text" style="padding-right:16px">28</div><div data-line-number="29" class="child-of-line-19  react-line-number react-code-text" style="padding-right:16px">29</div><div data-line-number="30" class="child-of-line-19  react-line-number react-code-text" style="padding-right:16px">30</div><div data-line-number="31" class="child-of-line-19  react-line-number react-code-text" style="padding-right:16px">31</div><div data-line-number="32" class="react-line-number react-code-text" style="padding-right:16px">32</div><div data-line-number="33" class="react-line-number react-code-text" style="padding-right:16px">33</div><div data-line-number="34" class="react-line-number react-code-text" style="padding-right:16px">34</div><div data-line-number="35" class="react-line-number react-code-text" style="padding-right:16px">35<span class="Box-sc-g0xbh4-0 hXUKEK"><div aria-label="Collapse code section" role="button" class="Box-sc-g0xbh4-0 cXzIIR"><svg aria-hidden="true" focusable="false" role="img" class="Octicon-sc-9kayk9-0" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="display:inline-block;user-select:none;vertical-align:text-bottom;overflow:visible"><path d="M12.78 5.22a.749.749 0 0 1 0 1.06l-4.25 4.25a.749.749 0 0 1-1.06 0L3.22 6.28a.749.749 0 1 1 1.06-1.06L8 8.939l3.72-3.719a.749.749 0 0 1 1.06 0Z"></path></svg></div></span></div><div data-line-number="36" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">36</div><div data-line-number="37" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">37</div><div data-line-number="38" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">38</div><div data-line-number="39" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">39</div><div data-line-number="40" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">40</div><div data-line-number="41" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">41</div><div data-line-number="42" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">42</div><div data-line-number="43" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">43</div><div data-line-number="44" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">44</div><div data-line-number="45" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">45</div><div data-line-number="46" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">46</div><div data-line-number="47" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">47</div><div data-line-number="48" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">48</div><div data-line-number="49" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">49</div><div data-line-number="50" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">50</div><div data-line-number="51" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">51</div><div data-line-number="52" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">52</div><div data-line-number="53" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">53</div><div data-line-number="54" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">54</div><div data-line-number="55" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">55</div><div data-line-number="56" class="child-of-line-35  react-line-number react-code-text" style="padding-right:16px">56</div><div data-line-number="57" class="react-line-number react-code-text" style="padding-right:16px">57</div></div><div class="react-code-lines"><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC1" class="react-file-line html-div" data-testid="code-cell" data-line-number="1" style="position:relative"><span class="pl-s">&quot;&quot;&quot;Diagnostics support for the Mazda integration.&quot;&quot;&quot;</span></div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC2" class="react-file-line html-div" data-testid="code-cell" data-line-number="2" style="position:relative"><span class="pl-k">from</span> __future__ <span class="pl-k">import</span> <span class="pl-s1">annotations</span></div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC3" class="react-file-line html-div" data-testid="code-cell" data-line-number="3" style="position:relative">
</div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC4" class="react-file-line html-div" data-testid="code-cell" data-line-number="4" style="position:relative"><span class="pl-k">from</span> <span class="pl-s1">typing</span> <span class="pl-k">import</span> <span class="pl-v">Any</span></div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC5" class="react-file-line html-div" data-testid="code-cell" data-line-number="5" style="position:relative">
</div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC6" class="react-file-line html-div" data-testid="code-cell" data-line-number="6" style="position:relative"><span class="pl-k">from</span> <span class="pl-s1">homeassistant</span>.<span class="pl-s1">components</span>.<span class="pl-s1">diagnostics</span>.<span class="pl-s1">util</span> <span class="pl-k">import</span> <span class="pl-s1">async_redact_data</span></div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC7" class="react-file-line html-div" data-testid="code-cell" data-line-number="7" style="position:relative"><span class="pl-k">from</span> <span class="pl-s1">homeassistant</span>.<span class="pl-s1">config_entries</span> <span class="pl-k">import</span> <span class="pl-v">ConfigEntry</span></div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC8" class="react-file-line html-div" data-testid="code-cell" data-line-number="8" style="position:relative"><span class="pl-k">from</span> <span class="pl-s1">homeassistant</span>.<span class="pl-s1">const</span> <span class="pl-k">import</span> <span class="pl-v">CONF_EMAIL</span>, <span class="pl-v">CONF_PASSWORD</span></div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC9" class="react-file-line html-div" data-testid="code-cell" data-line-number="9" style="position:relative"><span class="pl-k">from</span> <span class="pl-s1">homeassistant</span>.<span class="pl-s1">core</span> <span class="pl-k">import</span> <span class="pl-v">HomeAssistant</span></div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC10" class="react-file-line html-div" data-testid="code-cell" data-line-number="10" style="position:relative"><span class="pl-k">from</span> <span class="pl-s1">homeassistant</span>.<span class="pl-s1">exceptions</span> <span class="pl-k">import</span> <span class="pl-v">HomeAssistantError</span></div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC11" class="react-file-line html-div" data-testid="code-cell" data-line-number="11" style="position:relative"><span class="pl-k">from</span> <span class="pl-s1">homeassistant</span>.<span class="pl-s1">helpers</span>.<span class="pl-s1">device_registry</span> <span class="pl-k">import</span> <span class="pl-v">DeviceEntry</span></div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC12" class="react-file-line html-div" data-testid="code-cell" data-line-number="12" style="position:relative">
</div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC13" class="react-file-line html-div" data-testid="code-cell" data-line-number="13" style="position:relative"><span class="pl-k">from</span> .<span class="pl-s1">const</span> <span class="pl-k">import</span> <span class="pl-v">DATA_COORDINATOR</span>, <span class="pl-v">DOMAIN</span></div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC14" class="react-file-line html-div" data-testid="code-cell" data-line-number="14" style="position:relative">
</div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC15" class="react-file-line html-div" data-testid="code-cell" data-line-number="15" style="position:relative"><span class="pl-v">TO_REDACT_INFO</span> <span class="pl-c1">=</span> [<span class="pl-v">CONF_EMAIL</span>, <span class="pl-v">CONF_PASSWORD</span>]</div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC16" class="react-file-line html-div" data-testid="code-cell" data-line-number="16" style="position:relative"><span class="pl-v">TO_REDACT_DATA</span> <span class="pl-c1">=</span> [<span class="pl-s">&quot;vin&quot;</span>, <span class="pl-s">&quot;id&quot;</span>, <span class="pl-s">&quot;latitude&quot;</span>, <span class="pl-s">&quot;longitude&quot;</span>]</div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC17" class="react-file-line html-div" data-testid="code-cell" data-line-number="17" style="position:relative">
</div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC18" class="react-file-line html-div" data-testid="code-cell" data-line-number="18" style="position:relative">
</div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC19" class="react-file-line html-div" data-testid="code-cell" data-line-number="19" style="position:relative"><span class="pl-k">async</span> <span class="pl-k">def</span> <span class="pl-en">async_get_config_entry_diagnostics</span>(</div></div></div><div class="child-of-line-19  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC20" class="react-file-line html-div" data-testid="code-cell" data-line-number="20" style="position:relative">    <span class="pl-s1">hass</span>: <span class="pl-v">HomeAssistant</span>, <span class="pl-s1">config_entry</span>: <span class="pl-v">ConfigEntry</span></div></div></div><div class="child-of-line-19  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC21" class="react-file-line html-div" data-testid="code-cell" data-line-number="21" style="position:relative">) <span class="pl-c1">-&gt;</span> <span class="pl-s1">dict</span>[<span class="pl-s1">str</span>, <span class="pl-v">Any</span>]:</div></div></div><div class="child-of-line-19  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC22" class="react-file-line html-div" data-testid="code-cell" data-line-number="22" style="position:relative">    <span class="pl-s">&quot;&quot;&quot;Return diagnostics for a config entry.&quot;&quot;&quot;</span></div></div></div><div class="child-of-line-19  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC23" class="react-file-line html-div" data-testid="code-cell" data-line-number="23" style="position:relative">    <span class="pl-s1">coordinator</span> <span class="pl-c1">=</span> <span class="pl-s1">hass</span>.<span class="pl-s1">data</span>[<span class="pl-v">DOMAIN</span>][<span class="pl-s1">config_entry</span>.<span class="pl-s1">entry_id</span>][<span class="pl-v">DATA_COORDINATOR</span>]</div></div></div><div class="child-of-line-19  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC24" class="react-file-line html-div" data-testid="code-cell" data-line-number="24" style="position:relative">
</div></div></div><div class="child-of-line-19  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC25" class="react-file-line html-div" data-testid="code-cell" data-line-number="25" style="position:relative">    <span class="pl-s1">diagnostics_data</span> <span class="pl-c1">=</span> {</div></div></div><div class="child-of-line-19  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC26" class="react-file-line html-div" data-testid="code-cell" data-line-number="26" style="position:relative">        <span class="pl-s">&quot;info&quot;</span>: <span class="pl-en">async_redact_data</span>(<span class="pl-s1">config_entry</span>.<span class="pl-s1">data</span>, <span class="pl-v">TO_REDACT_INFO</span>),</div></div></div><div class="child-of-line-19  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC27" class="react-file-line html-div" data-testid="code-cell" data-line-number="27" style="position:relative">        <span class="pl-s">&quot;data&quot;</span>: [</div></div></div><div class="child-of-line-19  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC28" class="react-file-line html-div" data-testid="code-cell" data-line-number="28" style="position:relative">            <span class="pl-en">async_redact_data</span>(<span class="pl-s1">vehicle</span>, <span class="pl-v">TO_REDACT_DATA</span>) <span class="pl-k">for</span> <span class="pl-s1">vehicle</span> <span class="pl-c1">in</span> <span class="pl-s1">coordinator</span>.<span class="pl-s1">data</span></div></div></div><div class="child-of-line-19  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC29" class="react-file-line html-div" data-testid="code-cell" data-line-number="29" style="position:relative">        ],</div></div></div><div class="child-of-line-19  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC30" class="react-file-line html-div" data-testid="code-cell" data-line-number="30" style="position:relative">    }</div></div></div><div class="child-of-line-19  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC31" class="react-file-line html-div" data-testid="code-cell" data-line-number="31" style="position:relative">
</div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC32" class="react-file-line html-div" data-testid="code-cell" data-line-number="32" style="position:relative">    <span class="pl-k">return</span> <span class="pl-s1">diagnostics_data</span></div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC33" class="react-file-line html-div" data-testid="code-cell" data-line-number="33" style="position:relative">
</div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC34" class="react-file-line html-div" data-testid="code-cell" data-line-number="34" style="position:relative">
</div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC35" class="react-file-line html-div" data-testid="code-cell" data-line-number="35" style="position:relative"><span class="pl-k">async</span> <span class="pl-k">def</span> <span class="pl-en">async_get_device_diagnostics</span>(</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC36" class="react-file-line html-div" data-testid="code-cell" data-line-number="36" style="position:relative">    <span class="pl-s1">hass</span>: <span class="pl-v">HomeAssistant</span>, <span class="pl-s1">config_entry</span>: <span class="pl-v">ConfigEntry</span>, <span class="pl-s1">device</span>: <span class="pl-v">DeviceEntry</span></div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC37" class="react-file-line html-div" data-testid="code-cell" data-line-number="37" style="position:relative">) <span class="pl-c1">-&gt;</span> <span class="pl-s1">dict</span>[<span class="pl-s1">str</span>, <span class="pl-v">Any</span>]:</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC38" class="react-file-line html-div" data-testid="code-cell" data-line-number="38" style="position:relative">    <span class="pl-s">&quot;&quot;&quot;Return diagnostics for a device.&quot;&quot;&quot;</span></div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC39" class="react-file-line html-div" data-testid="code-cell" data-line-number="39" style="position:relative">    <span class="pl-s1">coordinator</span> <span class="pl-c1">=</span> <span class="pl-s1">hass</span>.<span class="pl-s1">data</span>[<span class="pl-v">DOMAIN</span>][<span class="pl-s1">config_entry</span>.<span class="pl-s1">entry_id</span>][<span class="pl-v">DATA_COORDINATOR</span>]</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC40" class="react-file-line html-div" data-testid="code-cell" data-line-number="40" style="position:relative">
</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC41" class="react-file-line html-div" data-testid="code-cell" data-line-number="41" style="position:relative">    <span class="pl-s1">vin</span> <span class="pl-c1">=</span> <span class="pl-en">next</span>(<span class="pl-en">iter</span>(<span class="pl-s1">device</span>.<span class="pl-s1">identifiers</span>))[<span class="pl-c1">1</span>]</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC42" class="react-file-line html-div" data-testid="code-cell" data-line-number="42" style="position:relative">
</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC43" class="react-file-line html-div" data-testid="code-cell" data-line-number="43" style="position:relative">    <span class="pl-s1">target_vehicle</span> <span class="pl-c1">=</span> <span class="pl-c1">None</span></div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC44" class="react-file-line html-div" data-testid="code-cell" data-line-number="44" style="position:relative">    <span class="pl-k">for</span> <span class="pl-s1">vehicle</span> <span class="pl-c1">in</span> <span class="pl-s1">coordinator</span>.<span class="pl-s1">data</span>:</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC45" class="react-file-line html-div" data-testid="code-cell" data-line-number="45" style="position:relative">        <span class="pl-k">if</span> <span class="pl-s1">vehicle</span>[<span class="pl-s">&quot;vin&quot;</span>] <span class="pl-c1">==</span> <span class="pl-s1">vin</span>:</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC46" class="react-file-line html-div" data-testid="code-cell" data-line-number="46" style="position:relative">            <span class="pl-s1">target_vehicle</span> <span class="pl-c1">=</span> <span class="pl-s1">vehicle</span></div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC47" class="react-file-line html-div" data-testid="code-cell" data-line-number="47" style="position:relative">            <span class="pl-k">break</span></div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC48" class="react-file-line html-div" data-testid="code-cell" data-line-number="48" style="position:relative">
</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC49" class="react-file-line html-div" data-testid="code-cell" data-line-number="49" style="position:relative">    <span class="pl-k">if</span> <span class="pl-s1">target_vehicle</span> <span class="pl-c1">is</span> <span class="pl-c1">None</span>:</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC50" class="react-file-line html-div" data-testid="code-cell" data-line-number="50" style="position:relative">        <span class="pl-k">raise</span> <span class="pl-v">HomeAssistantError</span>(<span class="pl-s">&quot;Vehicle not found&quot;</span>)</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC51" class="react-file-line html-div" data-testid="code-cell" data-line-number="51" style="position:relative">
</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC52" class="react-file-line html-div" data-testid="code-cell" data-line-number="52" style="position:relative">    <span class="pl-s1">diagnostics_data</span> <span class="pl-c1">=</span> {</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC53" class="react-file-line html-div" data-testid="code-cell" data-line-number="53" style="position:relative">        <span class="pl-s">&quot;info&quot;</span>: <span class="pl-en">async_redact_data</span>(<span class="pl-s1">config_entry</span>.<span class="pl-s1">data</span>, <span class="pl-v">TO_REDACT_INFO</span>),</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC54" class="react-file-line html-div" data-testid="code-cell" data-line-number="54" style="position:relative">        <span class="pl-s">&quot;data&quot;</span>: <span class="pl-en">async_redact_data</span>(<span class="pl-s1">target_vehicle</span>, <span class="pl-v">TO_REDACT_DATA</span>),</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC55" class="react-file-line html-div" data-testid="code-cell" data-line-number="55" style="position:relative">    }</div></div></div><div class="child-of-line-35  react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC56" class="react-file-line html-div" data-testid="code-cell" data-line-number="56" style="position:relative">
</div></div></div><div class="react-code-text react-code-line-contents" style="min-height:auto"><div><div id="LC57" class="react-file-line html-div" data-testid="code-cell" data-line-number="57" style="position:relative">    <span class="pl-k">return</span> <span class="pl-s1">diagnostics_data</span></div></div></div></div></div></div><div id="copilot-button-container"></div></div><div id="highlighted-line-menu-container"></div></div></div><button hidden="" data-testid="hotkey-button" data-hotkey-scope="read-only-cursor-text-area"></button><button hidden=""></button></section></div></div></div> <!-- --> <!-- --> </div></div></div><div class="Box-sc-g0xbh4-0"></div></main></div></div></div><div id="find-result-marks-container" class="Box-sc-g0xbh4-0 aZrVR"></div><button hidden="" data-testid="" data-hotkey-scope="read-only-cursor-text-area"></button><button hidden=""></button></div> <!-- --> <!-- --> <!-- --> <script type="application/json" id="__PRIMER_DATA__">{"resolvedServerColorMode":"night"}</script></div>
</react-app>
</turbo-frame>



  </div>

</turbo-frame>

    </main>
  </div>

  </div>

          <footer class="footer width-full container-xl p-responsive" role="contentinfo">
  <h2 class='sr-only'>Footer</h2>

  <div class="position-relative d-flex flex-items-center pb-2 f6 color-fg-muted border-top color-border-muted flex-column-reverse flex-lg-row flex-wrap flex-lg-nowrap mt-6 pt-6">
    <div class="list-style-none d-flex flex-wrap col-0 col-lg-2 flex-justify-start flex-lg-justify-between mb-2 mb-lg-0">
      <div class="mt-2 mt-lg-0 d-flex flex-items-center">
        <a aria-label="Homepage" title="GitHub" class="footer-octicon mr-2" href="https://github.com">
          <svg aria-hidden="true" height="24" viewBox="0 0 16 16" version="1.1" width="24" data-view-component="true" class="octicon octicon-mark-github">
    <path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"></path>
</svg>
</a>        <span>
        &copy; 2023 GitHub, Inc.
        </span>
      </div>
    </div>

    <nav aria-label='Footer' class="col-12 col-lg-8">
      <h3 class='sr-only' id='sr-footer-heading'>Footer navigation</h3>
      <ul class="list-style-none d-flex flex-wrap col-12 flex-justify-center flex-lg-justify-between mb-2 mb-lg-0" aria-labelledby='sr-footer-heading'>
          <li class="mr-3 mr-lg-0"><a href="https://docs.github.com/site-policy/github-terms/github-terms-of-service" data-analytics-event="{&quot;category&quot;:&quot;Footer&quot;,&quot;action&quot;:&quot;go to terms&quot;,&quot;label&quot;:&quot;text:terms&quot;}">Terms</a></li>
          <li class="mr-3 mr-lg-0"><a href="https://docs.github.com/site-policy/privacy-policies/github-privacy-statement" data-analytics-event="{&quot;category&quot;:&quot;Footer&quot;,&quot;action&quot;:&quot;go to privacy&quot;,&quot;label&quot;:&quot;text:privacy&quot;}">Privacy</a></li>
          <li class="mr-3 mr-lg-0"><a data-analytics-event="{&quot;category&quot;:&quot;Footer&quot;,&quot;action&quot;:&quot;go to security&quot;,&quot;label&quot;:&quot;text:security&quot;}" href="https://github.com/security">Security</a></li>
          <li class="mr-3 mr-lg-0"><a href="https://www.githubstatus.com/" data-analytics-event="{&quot;category&quot;:&quot;Footer&quot;,&quot;action&quot;:&quot;go to status&quot;,&quot;label&quot;:&quot;text:status&quot;}">Status</a></li>
          <li class="mr-3 mr-lg-0"><a data-ga-click="Footer, go to help, text:Docs" href="https://docs.github.com">Docs</a></li>
          <li class="mr-3 mr-lg-0"><a href="https://support.github.com?tags=dotcom-footer" data-analytics-event="{&quot;category&quot;:&quot;Footer&quot;,&quot;action&quot;:&quot;go to contact&quot;,&quot;label&quot;:&quot;text:contact&quot;}">Contact GitHub</a></li>
          <li class="mr-3 mr-lg-0"><a href="https://github.com/pricing" data-analytics-event="{&quot;category&quot;:&quot;Footer&quot;,&quot;action&quot;:&quot;go to Pricing&quot;,&quot;label&quot;:&quot;text:Pricing&quot;}">Pricing</a></li>
        <li class="mr-3 mr-lg-0"><a href="https://docs.github.com" data-analytics-event="{&quot;category&quot;:&quot;Footer&quot;,&quot;action&quot;:&quot;go to api&quot;,&quot;label&quot;:&quot;text:api&quot;}">API</a></li>
        <li class="mr-3 mr-lg-0"><a href="https://services.github.com" data-analytics-event="{&quot;category&quot;:&quot;Footer&quot;,&quot;action&quot;:&quot;go to training&quot;,&quot;label&quot;:&quot;text:training&quot;}">Training</a></li>
          <li class="mr-3 mr-lg-0"><a href="https://github.blog" data-analytics-event="{&quot;category&quot;:&quot;Footer&quot;,&quot;action&quot;:&quot;go to blog&quot;,&quot;label&quot;:&quot;text:blog&quot;}">Blog</a></li>
          <li><a data-ga-click="Footer, go to about, text:about" href="https://github.com/about">About</a></li>
      </ul>
    </nav>
  </div>

  <div class="d-flex flex-justify-center pb-6">
    <span class="f6 color-fg-muted"></span>
  </div>
</footer>




  <div id="ajax-error-message" class="ajax-error-message flash flash-error" hidden>
    <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-alert">
    <path d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575Zm1.763.707a.25.25 0 0 0-.44 0L1.698 13.132a.25.25 0 0 0 .22.368h12.164a.25.25 0 0 0 .22-.368Zm.53 3.996v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"></path>
</svg>
    <button type="button" class="flash-close js-ajax-error-dismiss" aria-label="Dismiss error">
      <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-x">
    <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.749.749 0 0 1 1.275.326.749.749 0 0 1-.215.734L9.06 8l3.22 3.22a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L8 9.06l-3.22 3.22a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"></path>
</svg>
    </button>
    You can’t perform that action at this time.
  </div>

    <template id="site-details-dialog">
  <details class="details-reset details-overlay details-overlay-dark lh-default color-fg-default hx_rsm" open>
    <summary role="button" aria-label="Close dialog"></summary>
    <details-dialog class="Box Box--overlay d-flex flex-column anim-fade-in fast hx_rsm-dialog hx_rsm-modal">
      <button class="Box-btn-octicon m-0 btn-octicon position-absolute right-0 top-0" type="button" aria-label="Close dialog" data-close-dialog>
        <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-x">
    <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.749.749 0 0 1 1.275.326.749.749 0 0 1-.215.734L9.06 8l3.22 3.22a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L8 9.06l-3.22 3.22a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"></path>
</svg>
      </button>
      <div class="octocat-spinner my-6 js-details-dialog-spinner"></div>
    </details-dialog>
  </details>
</template>

    <div class="Popover js-hovercard-content position-absolute" style="display: none; outline: none;" tabindex="0">
  <div class="Popover-message Popover-message--bottom-left Popover-message--large Box color-shadow-large" style="width:360px;">
  </div>
</div>

    <template id="snippet-clipboard-copy-button">
  <div class="zeroclipboard-container position-absolute right-0 top-0">
    <clipboard-copy aria-label="Copy" class="ClipboardButton btn js-clipboard-copy m-2 p-0 tooltipped-no-delay" data-copy-feedback="Copied!" data-tooltip-direction="w">
      <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-copy js-clipboard-copy-icon m-2">
    <path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path>
</svg>
      <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-check js-clipboard-check-icon color-fg-success d-none m-2">
    <path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path>
</svg>
    </clipboard-copy>
  </div>
</template>
<template id="snippet-clipboard-copy-button-unpositioned">
  <div class="zeroclipboard-container">
    <clipboard-copy aria-label="Copy" class="ClipboardButton btn btn-invisible js-clipboard-copy m-2 p-0 tooltipped-no-delay d-flex flex-justify-center flex-items-center" data-copy-feedback="Copied!" data-tooltip-direction="w">
      <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-copy js-clipboard-copy-icon">
    <path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path>
</svg>
      <svg aria-hidden="true" height="16" viewBox="0 0 16 16" version="1.1" width="16" data-view-component="true" class="octicon octicon-check js-clipboard-check-icon color-fg-success d-none">
    <path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path>
</svg>
    </clipboard-copy>
  </div>
</template>


    <style>
      .user-mention[href$="/eufysecurity"] {
        color: var(--color-user-mention-fg);
        background-color: var(--color-user-mention-bg);
        border-radius: 2px;
        margin-left: -2px;
        margin-right: -2px;
        padding: 0 2px;
      }
    </style>


    </div>

    <div id="js-global-screen-reader-notice" class="sr-only" aria-live="polite" ></div>
  </body>
</html>

