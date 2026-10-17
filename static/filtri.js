// Filtri della pagina: categoria, orientamento, fonte e ricerca nei titoli.
// Funziona tutto nel browser, senza inviare dati a nessuno.
(function () {
  "use strict";

  var campi = {
    testo: document.getElementById("f-testo"),
    categoria: document.getElementById("f-categoria"),
    orientamento: document.getElementById("f-orientamento"),
    fonte: document.getElementById("f-fonte"),
  };
  if (!campi.testo) return;

  var esito = document.getElementById("esito-filtri");
  var cards = Array.prototype.slice.call(document.querySelectorAll("main .card"));
  var gruppi = Array.prototype.slice.call(document.querySelectorAll("main .gruppo"));

  function semplifica(s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }

  cards.forEach(function (c) { c._titolo = semplifica(c.dataset.titolo); });

  function applica() {
    var parole = semplifica(campi.testo.value).split(/\s+/).filter(Boolean);
    var categoria = campi.categoria.value;
    var orientamento = campi.orientamento.value;
    var fonte = campi.fonte.value;
    var attivo = parole.length || categoria || orientamento || fonte;

    var notizieVisibili = 0;
    cards.forEach(function (c) {
      var ok =
        (!categoria || c.dataset.categoria === categoria) &&
        (!orientamento || c.dataset.orientamento === orientamento) &&
        (!fonte || c.dataset.fonte === fonte) &&
        parole.every(function (p) { return c._titolo.indexOf(p) !== -1; });
      c.hidden = !ok;
      if (ok) notizieVisibili++;
    });

    var gruppiVisibili = 0;
    gruppi.forEach(function (g) {
      var visibile = !!g.querySelector(".card:not([hidden])");
      g.hidden = !visibile;
      if (visibile && !g.classList.contains("singole")) gruppiVisibili++;
      var dettagli = g.querySelector("details");
      if (dettagli && attivo && visibile) dettagli.open = true;
    });

    if (attivo) {
      esito.hidden = false;
      esito.textContent = notizieVisibili
        ? "Notizie trovate: " + notizieVisibili + " (in " + gruppiVisibili + " argomenti)."
        : "Nessuna notizia corrisponde ai filtri.";
    } else {
      esito.hidden = true;
    }
  }

  var attesa;
  campi.testo.addEventListener("input", function () {
    clearTimeout(attesa);
    attesa = setTimeout(applica, 150);
  });
  [campi.categoria, campi.orientamento, campi.fonte].forEach(function (s) {
    s.addEventListener("change", applica);
  });
  document.getElementById("f-azzera").addEventListener("click", function () {
    campi.testo.value = "";
    campi.categoria.value = campi.orientamento.value = campi.fonte.value = "";
    applica();
  });

  // Se il browser ha ricordato i valori dei campi (es. tornando indietro), riapplica.
  applica();
})();
