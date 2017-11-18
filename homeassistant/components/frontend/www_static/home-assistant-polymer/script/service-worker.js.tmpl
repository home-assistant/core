self.addEventListener("push", function(event) {
  var data;
  if (event.data) {
    data = event.data.json();
    event.waitUntil(
      self.registration.showNotification(data.title, data)
      .then(function(notification){
        firePushCallback({
          type: "received",
          tag: data.tag,
          data: data.data
        }, data.data.jwt);
      })
    );
  }
});
self.addEventListener('notificationclick', function(event) {
  var url;

  notificationEventCallback('clicked', event);

  event.notification.close();

  if (!event.notification.data || !event.notification.data.url) {
    return;
  }

  url = event.notification.data.url;

  if (!url) return;

  event.waitUntil(
    clients.matchAll({
      type: 'window',
    })
    .then(function (windowClients) {
      var i;
      var client;
      for (i = 0; i < windowClients.length; i++) {
        client = windowClients[i];
        if (client.url === url && 'focus' in client) {
            return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
      return undefined;
    })
  );
});
self.addEventListener('notificationclose', function(event) {
  notificationEventCallback('closed', event);
});

function notificationEventCallback(event_type, event){
  firePushCallback({
    action: event.action,
    data: event.notification.data,
    tag: event.notification.tag,
    type: event_type
  }, event.notification.data.jwt);
}
function firePushCallback(payload, jwt){
  // Don't send the JWT in the payload.data
  delete payload.data.jwt;
  // If payload.data is empty then just remove the entire payload.data object.
  if (Object.keys(payload.data).length === 0 && payload.data.constructor === Object) {
    delete payload.data;
  }
  fetch('/api/notify.html5/callback', {
    method: 'POST',
    headers: new Headers({'Content-Type': 'application/json',
                          'Authorization': 'Bearer '+jwt}),
    body: JSON.stringify(payload)
  });
}
