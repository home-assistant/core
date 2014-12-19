function pinboardNS_fetch_script(url) {
  //document.writeln('<s'+'cript type="text/javascript" src="' + url + '"></s'+'cript>');
  (function(){
    var pinboardLinkroll = document.createElement('script');
    pinboardLinkroll.type = 'text/javascript';
    pinboardLinkroll.async = true;
    pinboardLinkroll.src = url;
    document.getElementsByTagName('head')[0].appendChild(pinboardLinkroll);
  })();
}

function pinboardNS_show_bmarks(r) {
  var lr = new Pinboard_Linkroll();
  lr.set_items(r);
  lr.show_bmarks();
}

function Pinboard_Linkroll() {
  var items;

  this.set_items = function(i) {
    this.items = i;
  }
  this.show_bmarks = function() {
    var lines = [];
    for (var i = 0; i < this.items.length; i++) {
      var item = this.items[i];
      var str = this.format_item(item);
      lines.push(str);
    }
    document.getElementById(linkroll).innerHTML = lines.join("\n");
  }
  this.cook = function(v) {
    return v.replace('<', '&lt;').replace('>', '&gt>');
  }

  this.format_item = function(it) {
    var str = "<li class=\"pin-item\">";
    if (!it.d) { return; }
    str += "<p><a class=\"pin-title\" href=\"" + this.cook(it.u) + "\">" + this.cook(it.d) + "</a>";
    if (it.n) {
      str += "<span class=\"pin-description\">" + this.cook(it.n) + "</span>\n";
    }
    if (it.t.length > 0) {
      for (var i = 0; i < it.t.length; i++) {
        var tag = it.t[i];
        str += " <a class=\"pin-tag\" href=\"https://pinboard.in/u:"+ this.cook(it.a) + "/t:" + this.cook(tag) + "\">" + this.cook(tag).replace(/^\s+|\s+$/g, '') + "</a> ";
      }
    }
    str += "</p></li>\n";
    return str;
  }
}
Pinboard_Linkroll.prototype = new Pinboard_Linkroll();
pinboardNS_fetch_script("https://feeds.pinboard.in/json/v1/u:"+pinboard_user+"/?cb=pinboardNS_show_bmarks\&count="+pinboard_count);

