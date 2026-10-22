// Mostra gli orari come "2 ore fa", "ieri alle 21:30"... calcolati sull'ora
// di chi legge. Se lo script non parte, resta la data scritta nella pagina.
(function () {
  "use strict";

  var MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];

  function dueCifre(n) { return (n < 10 ? "0" : "") + n; }
  function ora(d) { return dueCifre(d.getHours()) + ":" + dueCifre(d.getMinutes()); }
  function giorno(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime(); }

  function relativo(d, adesso) {
    var minuti = Math.round((adesso - d) / 60000);
    if (minuti < 1) return "adesso";
    if (minuti < 60) return minuti + " min fa";
    var ore = Math.floor(minuti / 60);
    if (ore < 12) return ore === 1 ? "1 ora fa" : ore + " ore fa";
    var giorni = Math.round((giorno(adesso) - giorno(d)) / 86400000);
    if (giorni === 0) return "oggi alle " + ora(d);
    if (giorni === 1) return "ieri alle " + ora(d);
    return d.getDate() + " " + MESI[d.getMonth()] + ", " + ora(d);
  }

  function aggiorna() {
    var adesso = new Date();
    var orari = document.querySelectorAll("time.rel[datetime]");
    for (var i = 0; i < orari.length; i++) {
      var t = orari[i];
      var d = new Date(t.getAttribute("datetime"));
      if (isNaN(d)) continue;
      if (!t.title) t.title = t.textContent.trim();
      // Orari "nel futuro" (orologi dei siti un po' avanti): si mostra "adesso".
      t.textContent = relativo(d > adesso ? adesso : d, adesso);
    }
  }

  aggiorna();
  setInterval(aggiorna, 60000);
})();
