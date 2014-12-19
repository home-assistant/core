// JSON-P Twitter fetcher for Octopress
// (c) Brandon Mathis // MIT License

/* Sky Slavin, Ludopoli. MIT license.  * based on JavaScript Pretty Date * Copyright (c) 2008 John Resig (jquery.com) * Licensed under the MIT license.  */
function prettyDate(time) {
  if (navigator.appName === 'Microsoft Internet Explorer') {
    return "<span>&infin;</span>"; // because IE date parsing isn't fun.
  }
  var say = {
    just_now:    " now",
    minute_ago:  "1m",
    minutes_ago: "m",
    hour_ago:    "1h",
    hours_ago:   "h",
    yesterday:   "1d",
    days_ago:    "d",
    last_week:   "1w",
    weeks_ago:   "w"
  };

  var current_date = new Date(),
      current_date_time = current_date.getTime(),
      current_date_full = current_date_time + (1 * 60000),
      date = new Date(time),
      diff = ((current_date_full - date.getTime()) / 1000),
      day_diff = Math.floor(diff / 86400);

  if (isNaN(day_diff) || day_diff < 0) { return "<span>&infin;</span>"; }

  return day_diff === 0 && (
    diff < 60 && say.just_now ||
    diff < 120 && say.minute_ago ||
    diff < 3600 && Math.floor(diff / 60) + say.minutes_ago ||
    diff < 7200 && say.hour_ago ||
    diff < 86400 && Math.floor(diff / 3600) + say.hours_ago) ||
    day_diff === 1 && say.yesterday ||
    day_diff < 7 && day_diff + say.days_ago ||
    day_diff === 7 && say.last_week ||
    day_diff > 7 && Math.ceil(day_diff / 7) + say.weeks_ago;
}

function linkifyTweet(text, url) {
  // Linkify urls, usernames, hashtags
  text = text.replace(/(https?:\/\/)([\w\-:;?&=+.%#\/]+)/gi, '<a href="$1$2">$2</a>')
    .replace(/(^|\W)@(\w+)/g, '$1<a href="https://twitter.com/$2">@$2</a>')
    .replace(/(^|\W)#(\w+)/g, '$1<a href="https://search.twitter.com/search?q=%23$2">#$2</a>');

  // Use twitter's api to replace t.co shortened urls with expanded ones.
  for (var u in url) {
    if(url[u].expanded_url != null){
      var shortUrl = new RegExp(url[u].url, 'g');
      text = text.replace(shortUrl, url[u].expanded_url);
      var shortUrl = new RegExp(">"+(url[u].url.replace(/https?:\/\//, '')), 'g');
      text = text.replace(shortUrl, ">"+url[u].display_url);
    }
  }
  return text
}

function showTwitterFeed(tweets, twitter_user) {
  var timeline = document.getElementById('tweets'),
      content = '';

  for (var t in tweets) {
    content += '<li>'+'<p>'+'<a href="https://twitter.com/'+twitter_user+'/status/'+tweets[t].id_str+'">'+prettyDate(tweets[t].created_at)+'</a>'+linkifyTweet(tweets[t].text.replace(/\n/g, '<br>'), tweets[t].entities.urls)+'</p>'+'</li>';
  }
  timeline.innerHTML = content;
}

function getTwitterFeed(user, count, replies) {
  count = parseInt(count, 10);
  $.ajax({
      url: "https://api.twitter.com/1/statuses/user_timeline/" + user + ".json?trim_user=true&count=" + (count + 20) + "&include_entities=1&exclude_replies=" + (replies ? "0" : "1") + "&callback=?"
    , type: 'jsonp'
    , error: function (err) { $('#tweets li.loading').addClass('error').text("Twitter's busted"); }
    , success: function(data) { showTwitterFeed(data.slice(0, count), user); }
  })
}
