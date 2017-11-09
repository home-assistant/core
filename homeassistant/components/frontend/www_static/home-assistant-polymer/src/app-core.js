import * as HAWS from 'home-assistant-js-websocket';

window.HAWS = HAWS;
window.HASS_DEMO = __DEMO__;
window.HASS_DEV = __DEV__;

const init = window.createHassConnection = function (password) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${proto}://${window.location.host}/api/websocket`;
  const options = {
    setupRetry: 10,
  };
  if (password !== undefined) {
    options.authToken = password;
  }

  return HAWS.createConnection(url, options)
    .then(function (conn) {
      HAWS.subscribeEntities(conn);
      HAWS.subscribeConfig(conn);
      return conn;
    });
};

if (window.noAuth) {
  window.hassConnection = init();
} else if (window.localStorage.authToken) {
  window.hassConnection = init(window.localStorage.authToken);
} else {
  window.hassConnection = null;
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/service_worker.js');
  });
}
