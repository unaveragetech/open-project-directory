// Interstitial countdown.
// COMPLIANCE: the Continue button is enabled purely by the countdown timer.
// It does NOT depend on any advertisement click, impression, or load event.
// The ad link and the Continue button are separate elements.
(function () {
  var countdownEl = document.getElementById("countdown");
  var btn = document.getElementById("continue-btn");
  if (!countdownEl || !btn) return;
  var seconds = parseInt(countdownEl.getAttribute("data-countdown-seconds"), 10) || 5;
  var remaining = seconds;
  function tick() {
    if (remaining <= 0) {
      countdownEl.textContent = "You can continue now.";
      btn.removeAttribute("aria-disabled");
      return;
    }
    countdownEl.textContent = "Please wait " + remaining + " second" + (remaining === 1 ? "" : "s") + "…";
    remaining -= 1;
    setTimeout(tick, 1000);
  }
  tick();
})();
