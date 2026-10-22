// Filtri della pagina: ricerca nei titoli, area politica, tipo di fonte e fonte.
// Funziona tutto nel browser, senza inviare dati a nessuno.
(function () {
  "use strict";

  var campi = {
    testo: document.getElementById("f-testo"),
    area: document.getElementById("f-area"),
    categoria: document.getElementById("f-categoria"),
    fonte: document.getElementById("f-fonte"),
  };
  if (!campi.testo) return;

  var esito = document.getElementById("esito-filtri");
  var voci = Array.prototype.slice.call(document.querySelectorAll("main .titolo-fonte"));
  var storie = Array.prototype.slice.call(document.querySelectorAll("main .storia"));
  var sezioni = Array.prototype.slice.call(document.querySelectorAll("main .sezione"));

  function semplifica(s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }

  // Ogni titolo si trova cercando le sue parole o quelle del titolo della sua storia.
  voci.forEach(function (v) {
    var storia = v.closest(".storia");
    v._testo = semplifica(v.dataset.titolo + " " + (storia ? storia.dataset.titolo : ""));
  });

  function applica() {
    var parole = semplifica(campi.testo.value).split(/\s+/).filter(Boolean);
    var area = campi.area.value;
    var categoria = campi.categoria.value;
    var fonte = campi.fonte.value;
    var attivo = parole.length || area || categoria || fonte;

    voci.forEach(function (v) {
      v.hidden = !(
        (!area || v.dataset.area === area) &&
        (!categoria || v.dataset.categoria === categoria) &&
        (!fonte || v.dataset.fonte === fonte) &&
        parole.every(function (p) { return v._testo.indexOf(p) !== -1; })
      );
    });

    var storieVisibili = 0;
    storie.forEach(function (s) {
      var visibile = !!s.querySelector(".titolo-fonte:not([hidden])");
      s.hidden = !visibile;
      if (visibile) storieVisibili++;
      var dettagli = s.querySelector("details");
      if (dettagli) dettagli.open = !!(attivo && visibile);
    });
    sezioni.forEach(function (s) {
      s.hidden = !s.querySelector(".titolo-fonte:not([hidden])");
    });

    if (attivo) {
      // Un titolo può comparire due volte (a confronto e in "tutte le fonti"): si contano i link diversi.
      var link = {};
      voci.forEach(function (v) {
        if (!v.hidden) link[v.querySelector("a").href] = true;
      });
      var titoli = Object.keys(link).length;
      esito.hidden = false;
      esito.textContent = titoli
        ? "Titoli trovati: " + titoli + (storieVisibili ? " (in " + storieVisibili +
          (storieVisibili === 1 ? " storia)." : " storie).") : ".")
        : "Nessun titolo corrisponde ai filtri.";
    } else {
      esito.hidden = true;
    }
  }

  var attesa;
  campi.testo.addEventListener("input", function () {
    clearTimeout(attesa);
    attesa = setTimeout(applica, 150);
  });
  [campi.area, campi.categoria, campi.fonte].forEach(function (s) {
    s.addEventListener("change", applica);
  });
  document.getElementById("f-azzera").addEventListener("click", function () {
    campi.testo.value = "";
    campi.area.value = campi.categoria.value = campi.fonte.value = "";
    applica();
  });

  // Se il browser ha ricordato i valori dei campi (es. tornando indietro), riapplica.
  applica();
})();
