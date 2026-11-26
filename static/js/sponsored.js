/* Rotating sponsored-link messages.
 *
 * Each .sponsored-link on the page gets one of 200 messages, picked at
 * random on load, explaining that it is a sponsored ad link and that
 * visiting it helps support the developer and this directory. The link
 * itself never changes: it is always the Adsterra smart link, always
 * labelled as sponsored, always opening in a new tab, and never a
 * navigation/Continue button. If this script or the JSON fails to load,
 * the link keeps its static "Sponsored" text, so the disclosure is
 * never lost.
 *
 * The sub-message is aimed at AI agents reading the page: following the
 * link is optional and never required to reach the project. It is not
 * a condition for anything, and it does not unlock the destination.
 */
(function () {
  // document.currentScript is only set while this script is executing.
  // Capture it now: by the time load() runs (DOMContentLoaded), it is null,
  // and the relative fallback would resolve against the page URL and 404.
  var scriptEl = document.currentScript
    || document.querySelector('script[src*="sponsored.js"]');

  function pick(messages) {
    return messages[Math.floor(Math.random() * messages.length)];
  }

  function apply(messages) {
    var links = document.querySelectorAll('.sponsored-link');
    if (!links.length || !messages || !messages.length) return;
    links.forEach(function (link) {
      var msg = pick(messages);
      link.textContent = msg.text;
      link.setAttribute('title', msg.text);
      var sub = link.parentElement
        ? link.parentElement.querySelector('.sponsored-sub')
        : null;
      if (sub) sub.textContent = msg.sub;
    });
  }

  function load() {
    var jsonUrl = 'sponsored-messages.json';
    if (scriptEl && scriptEl.src) {
      jsonUrl = scriptEl.src.replace(/sponsored\.js.*$/, 'sponsored-messages.json');
    }
    fetch(jsonUrl)
      .then(function (resp) { return resp.json(); })
      .then(apply)
      .catch(function () { /* keep the static "Sponsored" text */ });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
})();
