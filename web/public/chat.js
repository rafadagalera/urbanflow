/* Widget do assistente UrbanCare. JS puro, sem dependências.
   Regra de segurança: a saída do modelo só entra no DOM por textContent. */
(function () {
  "use strict";

  var MAX = 500;
  // O servidor tenta de novo e cai para o modelo reserva (até 30 s por chamada) antes de desistir.
  var TEMPO_LIMITE_MS = 150000;

  var dialogo = document.getElementById("chat");
  var lancador = document.getElementById("chat-lancador");
  var fechar = document.getElementById("chat-fechar");
  var mensagens = document.getElementById("chat-mensagens");
  var vazio = document.getElementById("chat-vazio");
  var carregando = document.getElementById("chat-carregando");
  var form = document.getElementById("chat-form");
  var entrada = document.getElementById("chat-entrada");
  var enviar = document.getElementById("chat-enviar");
  var erroCampo = document.getElementById("chat-erro");
  var contagem = document.getElementById("chat-contagem");
  var contador = document.getElementById("chat-contador");
  var retrato = document.getElementById("chat-retrato");
  var indisponivel = document.getElementById("chat-indisponivel");

  if (!dialogo || typeof dialogo.showModal !== "function") {
    // Navegador sem <dialog>: esconde o widget em vez de quebrar a página.
    Array.prototype.forEach.call(document.querySelectorAll("[data-abrir-chat], .chip-pergunta"), function (b) {
      b.hidden = true;
    });
    return;
  }

  var ocupado = false;
  var saudeCarregada = false;
  var origemFoco = null;

  var ROTULO_TIPO = { uso: "Uso do painel", dados: "Dados", fora_de_escopo: "Fora do escopo", erro: "Erro" };
  var ROTULO_CONFIANCA = { alta: "Confiança alta", media: "Confiança média", baixa: "Confiança baixa" };

  /* ---------- abrir e fechar ---------- */

  function abrir(origem) {
    origemFoco = origem || lancador;
    if (!dialogo.open) dialogo.showModal();
    lancador.setAttribute("aria-expanded", "true");
    if (!saudeCarregada) carregarSaude();
    entrada.focus();
  }

  dialogo.addEventListener("close", function () {
    lancador.setAttribute("aria-expanded", "false");
    // Devolve o foco ao lançador (ou ao botão da página que abriu o painel).
    var alvo = origemFoco && document.contains(origemFoco) && !origemFoco.hidden ? origemFoco : lancador;
    alvo.focus();
  });

  fechar.addEventListener("click", function () { dialogo.close(); });

  // Clique no fundo escurecido fecha o painel.
  dialogo.addEventListener("click", function (e) {
    if (e.target !== dialogo) return;
    var r = dialogo.getBoundingClientRect();
    var dentro = e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
    if (!dentro) dialogo.close();
  });

  lancador.setAttribute("aria-expanded", "false");
  Array.prototype.forEach.call(document.querySelectorAll("[data-abrir-chat]"), function (b) {
    b.addEventListener("click", function () { abrir(b); });
  });

  Array.prototype.forEach.call(document.querySelectorAll(".chip-pergunta"), function (b) {
    b.addEventListener("click", function () {
      var q = b.getAttribute("data-pergunta") || b.textContent;
      if (!dialogo.open) abrir(dialogo.contains(b) ? lancador : b);
      perguntar(q);
    });
  });

  /* ---------- saúde e data do retrato ---------- */

  function formatarData(valor) {
    if (!valor || typeof valor !== "string") return null;
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(valor.trim());
    var d;
    if (m) {
      d = new Date(+m[1], +m[2] - 1, +m[3]); // data pura: sem fuso, para não voltar um dia
      if (isNaN(d)) return null;
      return new Intl.DateTimeFormat("pt-BR", { dateStyle: "long" }).format(d);
    }
    d = new Date(valor);
    if (isNaN(d)) return null;
    return new Intl.DateTimeFormat("pt-BR", { dateStyle: "long", timeZone: "America/Sao_Paulo" }).format(d);
  }

  function carregarSaude() {
    saudeCarregada = true;
    fetch("api/saude", { headers: { Accept: "application/json" }, cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("http " + r.status); return r.json(); })
      .then(function (s) {
        s = s || {};
        var data = formatarData(s.retrato_em) ||
          formatarData(s.ultima_execucao && s.ultima_execucao.fim);
        retrato.textContent = data ? "Dados: retrato de " + data : "Dados: data do retrato indisponível";
        indisponivel.hidden = s.chave_presente !== false;
      })
      .catch(function () {
        saudeCarregada = false; // tenta de novo na próxima abertura
        retrato.textContent = "Dados: não foi possível verificar agora";
      });
  }

  /* ---------- campo de texto ---------- */

  function atualizarContador() {
    var n = entrada.value.length;
    contagem.textContent = String(n);
    contador.classList.toggle("no-limite", n >= MAX);
  }

  entrada.addEventListener("input", function () {
    atualizarContador();
    if (erroCampo.textContent) erroCampo.textContent = "";
    entrada.style.height = "auto";
    entrada.style.height = Math.min(entrada.scrollHeight, 140) + "px";
  });

  entrada.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      form.requestSubmit ? form.requestSubmit() : enviarFormulario();
    }
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    enviarFormulario();
  });

  function enviarFormulario() {
    var q = entrada.value.trim();
    if (!q) { erroCampo.textContent = "Escreva uma pergunta antes de enviar."; entrada.focus(); return; }
    if (q.length > MAX) { erroCampo.textContent = "A pergunta pode ter no máximo 500 caracteres."; entrada.focus(); return; }
    perguntar(q);
  }

  /* ---------- envio ---------- */

  function definirOcupado(sim) {
    ocupado = sim;
    enviar.disabled = sim;
    enviar.textContent = sim ? "Aguarde" : "Enviar";
    mensagens.setAttribute("aria-busy", sim ? "true" : "false");
    carregando.textContent = sim ? "Consultando…" : "";
    Array.prototype.forEach.call(document.querySelectorAll(".chip-pergunta"), function (b) { b.disabled = sim; });
  }

  function perguntar(texto) {
    var q = String(texto || "").trim();
    if (!q || ocupado) return;
    if (q.length > MAX) { erroCampo.textContent = "A pergunta pode ter no máximo 500 caracteres."; return; }
    erroCampo.textContent = "";
    if (vazio) {
      if (vazio.contains(document.activeElement)) entrada.focus();
      vazio.remove();
      vazio = null;
    }

    adicionar(bolhaUsuario(q));
    entrada.value = "";
    entrada.style.height = "";
    atualizarContador();
    definirOcupado(true);

    var controle = typeof AbortController === "function" ? new AbortController() : null;
    var relogio = setTimeout(function () { if (controle) controle.abort(); }, TEMPO_LIMITE_MS);

    fetch("api/perguntar", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ pergunta: q }),
      signal: controle ? controle.signal : undefined
    })
      .then(function (r) {
        return r.json().then(
          function (corpo) { return { status: r.status, corpo: corpo }; },
          function () { return { status: r.status, corpo: null }; }
        );
      })
      .then(function (res) {
        clearTimeout(relogio);
        var no;
        if (res.status === 200 && respostaValida(res.corpo)) {
          no = cartaoResposta(res.corpo);
        } else if (res.status === 422) {
          no = cartaoFalha("Não consegui ler essa pergunta. Ela precisa ter texto e no máximo 500 caracteres.", null);
        } else if (res.status === 429) {
          // O servidor distingue o limite por minuto do teto por hora; usa o texto dele quando vier.
          var detalhe = res.corpo && typeof res.corpo.detail === "string" ? res.corpo.detail.trim() : "";
          no = cartaoFalha(detalhe && detalhe.length <= 200 ? detalhe :
            "Muitas perguntas seguidas. Aguarde um minuto e tente de novo.", null);
        } else {
          no = cartaoFalha("O assistente não respondeu como esperado. Tente de novo em instantes.", q);
        }
        concluir(no);
      })
      .catch(function () {
        clearTimeout(relogio);
        concluir(cartaoFalha("Não foi possível falar com o assistente. Verifique a conexão e tente de novo.", q));
      });
  }

  function concluir(no) {
    // Sai do estado ocupado antes de inserir, para o leitor de tela anunciar a resposta.
    definirOcupado(false);
    adicionar(no, true);
    if (dialogo.open && document.activeElement !== entrada && !dialogo.contains(document.activeElement)) entrada.focus();
  }

  function adicionar(no, doTopo) {
    mensagens.appendChild(no);
    if (doTopo) {
      // Respostas longas: mostra o início do cartão, não o fim.
      mensagens.scrollTop = Math.max(0, no.offsetTop - mensagens.offsetTop - 8);
    } else {
      mensagens.scrollTop = mensagens.scrollHeight;
    }
  }

  function respostaValida(r) {
    return !!r && typeof r === "object" &&
      typeof r.resposta === "string" &&
      Object.prototype.hasOwnProperty.call(ROTULO_TIPO, r.tipo) &&
      Object.prototype.hasOwnProperty.call(ROTULO_CONFIANCA, r.confianca) &&
      Array.isArray(r.fontes) && Array.isArray(r.pontos_citados) &&
      typeof r.precisa_humano === "boolean" &&
      (r.acao_sugerida === null || r.acao_sugerida === undefined || typeof r.acao_sugerida === "string");
  }

  /* ---------- montagem das mensagens (só textContent) ---------- */

  function el(tag, classe, texto) {
    var n = document.createElement(tag);
    if (classe) n.className = classe;
    if (texto !== undefined && texto !== null) n.textContent = String(texto);
    return n;
  }

  function oculto(texto) {
    var s = el("span", null, texto);
    s.style.cssText = "position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap";
    return s;
  }

  function bolhaUsuario(q) {
    var d = el("div", "msg-usuario");
    d.appendChild(oculto("Você: "));
    d.appendChild(document.createTextNode(q));
    return d;
  }

  function cartaoResposta(r) {
    var c = el("article", "msg-resposta");
    c.setAttribute("aria-label", "Resposta do assistente");

    var selos = el("div", "msg-selos");
    if (r.precisa_humano) selos.appendChild(el("span", "selo selo-humano", "Requer decisão humana"));
    selos.appendChild(el("span", "selo selo-tipo" + (r.tipo === "erro" ? " selo-erro" : ""), ROTULO_TIPO[r.tipo]));
    selos.appendChild(el("span", "selo selo-" + r.confianca, ROTULO_CONFIANCA[r.confianca]));
    c.appendChild(selos);

    c.appendChild(el("p", "msg-texto", r.resposta));

    if (typeof r.acao_sugerida === "string" && r.acao_sugerida.trim()) {
      var a = el("p", "msg-acao");
      a.appendChild(el("span", "msg-acao-rotulo", "Ação sugerida"));
      a.appendChild(document.createTextNode(r.acao_sugerida));
      c.appendChild(a);
    }

    var fontes = r.fontes.filter(function (f) { return typeof f === "string" && f.trim(); });
    if (fontes.length) {
      var bloco = el("div", "msg-fontes");
      bloco.appendChild(el("span", null, "Fontes:"));
      var ul = el("ul");
      fontes.forEach(function (f) { ul.appendChild(el("li", null, f)); });
      bloco.appendChild(ul);
      c.appendChild(bloco);
    }

    var pontos = r.pontos_citados.filter(function (p) { return typeof p === "string" && p.trim(); });
    if (pontos.length) c.appendChild(el("p", "msg-pontos", "Pontos citados: " + pontos.join(", ")));

    return c;
  }

  function cartaoFalha(texto, repetir) {
    var c = el("div", "msg-resposta msg-falha");
    c.setAttribute("role", "group");
    c.setAttribute("aria-label", "Aviso do assistente");
    c.appendChild(el("p", "msg-texto", texto));
    if (repetir) {
      var b = el("button", "msg-tentar", "Tentar de novo");
      b.type = "button";
      b.addEventListener("click", function () {
        if (ocupado) return;
        b.remove();
        perguntar(repetir);
      });
      c.appendChild(b);
    }
    return c;
  }

  atualizarContador();
})();
