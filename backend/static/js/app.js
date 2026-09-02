/* NEXA — interações do app (web, tablet, PWA, desktop). API via fetch same-origin
 * (cookie HTTP-only) ou Authorization Bearer. WebSocket realtime para mensagens. */
(function () {
  "use strict";

  var NEXA = window.NEXA || { wsUrl: "", token: "", me: null };

  function el(sel, root) { return (root || document).querySelector(sel); }
  function els(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function api(path, opts) {
    opts = opts || {};
    opts.headers = opts.headers || {};
    if (NEXA.token) opts.headers["Authorization"] = "Bearer " + NEXA.token;
    if (opts.json && !opts.headers["Content-Type"]) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.json);
    }
    opts.credentials = "same-origin";
    return fetch(path, opts).then(function (r) {
      if (r.status === 401 && !path.startsWith("/api/auth/login") && !path.startsWith("/api/auth/register")) {
        if (confirm("Sessão expirada. Entrar novamente?")) location.href = "/login";
        throw new Error("unauthorized");
      }
      return r.json().catch(function () { return null; }).then(function (data) {
        if (!r.ok) { var e = new Error((data && data.detail) || "erro"); e.status = r.status; throw e; }
        return data;
      });
    });
  }

  function toast(msg, ok) {
    console.log((ok ? "✓ " : "⚠ ") + msg);
  }

  function uploadFile(file, statusEl) {
    var fd = new FormData();
    fd.append("file", file);
    if (statusEl) statusEl.textContent = "Enviando...";
    return fetch("/api/upload", { method: "POST", body: fd, credentials: "same-origin",
      headers: NEXA.token ? { Authorization: "Bearer " + NEXA.token } : {} })
      .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.detail || "upload"); return d; }); })
      .then(function (d) { if (statusEl) statusEl.textContent = "✓ enviado"; return d; })
      .catch(function (e) { if (statusEl) statusEl.textContent = "✗ falhou"; throw e; });
  }

  function uploadAll(files, statusEl) {
    return Promise.all(files.map(function (f) { return uploadFile(f, statusEl); }));
  }

  function showError(form, e) {
    var box = el("[data-error]", form);
    if (box) box.textContent = e.message || "Erro inesperado";
  }

  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-act]");
    if (!t) return;

    var act = t.dataset.act;
    if (act === "like") like(t);
    else if (act === "follow") follow(t);
    else if (act === "join") joinSpace(t, false);
    else if (act === "leave") joinSpace(t, true);
    else if (act === "rsvp") rsvp(t);
    else if (act === "read-all") readAll();
    else if (act === "logout") logout();
  });

  function like(btn) {
    var slug = btn.dataset.slug;
    var on = btn.classList.contains("on");
    var method = on ? "DELETE" : "POST";
    api("/api/posts/" + slug + "/like", { method: method }).then(function (d) {
      btn.classList.toggle("on", !on);
      el(".cnt", btn).textContent = d.like_count;
    }).catch(function () { location.href = "/login"; });
  }

  function follow(btn) {
    var u = btn.dataset.username;
    api("/api/users/" + u + "/follow", { method: "POST" }).then(function (d) {
      btn.textContent = "Seguindo ✓";
      btn.dataset.following = "1";
    }).catch(function () { location.href = "/login"; });
  }

  function joinSpace(btn, leave) {
    var kind = btn.dataset.space, slug = btn.dataset.slug;
    var url = "/api/" + kind + "s/" + slug + (leave ? "/leave" : "/join");
    api(url, { method: leave ? "DELETE" : "POST" }).then(function () { location.reload(); })
      .catch(function () { location.href = "/login"; });
  }

  function rsvp(btn) {
    var slug = btn.dataset.slug, st = btn.dataset.status;
    api("/api/events/" + slug + "/rsvp", { method: "POST", json: { status: st } }).catch(function (e) {
      if (e.status === 401) location.href = "/login";
      else alert(e.message);
    });
  }

  function readAll() {
    api("/api/notifications/read-all", { method: "POST" }).then(function () { location.reload(); });
  }

  function logout() {
    api("/api/auth/logout", { method: "POST" }).then(function () { location.href = "/"; });
  }

  /* ------------------------- formulários de autenticação */
  function bindAuth() {
    var forms = [
      ["#login-form", "/api/auth/login"],
      ["#register-form", "/api/auth/register"]
    ];
    forms.forEach(function (pair) {
      var f = el(pair[0]);
      if (!f) return;
      f.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var payload = Object.fromEntries(new FormData(f).entries());
        api(pair[1], { method: "POST", json: payload }).then(function () {
          location.href = "/app";
        }).catch(function (e) { showError(f, e); });
      });
    });
  }
  bindAuth();

  /* ------------------------- composer de posts (feed do app) */
  var composer = el("#composer");
  if (composer) {
    el("form", composer).addEventListener("submit", function (ev) {
      ev.preventDefault();
      var form = ev.target;
      var fd = new FormData(form);
      var files = els('input[type="file"]', form)[0].files || [];
      var chain = Promise.resolve([]);
      if (files.length) chain = uploadAll(files, el("[data-upload-status]", composer));
      chain.then(function (media) {
        var keys = media.map(function (m) { return m.key; });
        fd.set("media_keys", JSON.stringify(keys));
        return api("/api/posts", { method: "POST", json: {
          title: fd.get("title") || "", content: fd.get("content"),
          visibility: fd.get("visibility") || "public", media_keys: keys
        } });
      }).then(function () { location.reload(); }).catch(function (e) { showError(composer, e); });
    });
  }

  /* ------------------------- like/comentário em post público */
  var commentForm = el("#comment-form");
  if (commentForm) {
    commentForm.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var slug = commentForm.dataset.slug;
      var content = el("input[name=content]", commentForm).value;
      api("/api/posts/" + slug + "/comments", { method: "POST", json: { content: content } })
        .then(function () { location.reload(); }).catch(function (e) { alert(e.message); });
    });
  }

  /* ------------------------- post em espaço (grupo/círculo) */
  var spaceComposer = el("#space-composer");
  if (spaceComposer) {
    el("form", spaceComposer).addEventListener("submit", function (ev) {
      ev.preventDefault();
      var form = ev.target;
      var kind = spaceComposer.dataset.space, slug = spaceComposer.dataset.slug;
      api("/api/" + kind + "s/" + slug + "/posts", { method: "POST", json: {
        title: el("[name=title]", form).value, content: el("[name=content]", form).value,
        visibility: "public", media_keys: [] } })
        .then(function () { location.reload(); }).catch(function (e) { showError(spaceComposer, e); });
    });
  }

  /* ------------------------- formulários: grupo/círculo/evento/story/settings */
  var builders = {
    "create-group": { url: "/api/groups", hasImage: true },
    "create-circle": { url: "/api/circles", hasImage: true },
    "create-event": { url: "/api/events", hasImage: true }
  };
  Object.keys(builders).forEach(function (act) {
    var f = el('form[data-act="' + act + '"]');
    if (!f) return;
    f.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var cfg = builders[act];
      var fd = new FormData(f);
      chain().then(function () { return submitBuilder(f, cfg, fd); });
      function chain() {
        var files = els('input[type="file"]', f)[0].files || [];
        var status = el("[data-upload-image]", f);
        if (!files.length) return Promise.resolve();
        return uploadAll(files, status).then(function (media) {
          if (media.length) { el("[name=image_key]", f).value = media[0].key; fd = new FormData(f); }
        });
      }
    });
  });

  function submitBuilder(f, cfg, fd) {
    var payload = Object.fromEntries(new FormData(f).entries());
    if (cfg.hasImage) { payload.image_key = el("[name=image_key]", f).value || null; }
    if (payload.ends_at === "") payload.ends_at = null;
    if (payload.visibility === "private" && !payload.image_key) delete payload.image_key;
    return api(cfg.url, { method: "POST", json: payload }).then(function () { location.href = "/app"; })
      .catch(function (e) { showError(f, e); });
  }

  /* story */
  var storyForm = el('form[data-act="create-story"]');
  if (storyForm) {
    storyForm.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var f = ev.target;
      var files = els('input[type="file"]', f)[0].files || [];
      var then = function (m) {
        var fd = new FormData(f);
        if (m && m.length) fd.set("media_key", m[0].key);
        return api("/api/stories", { method: "POST", json: {
          caption: fd.get("caption") || "", media_key: fd.get("media_key") || null,
          hours: parseInt(fd.get("hours") || "24", 10) } });
      };
      var p = files.length ? uploadAll(files, el("[data-upload-media]", f)) : Promise.resolve([]);
      p.then(then).then(function () { location.href = "/app"; }).catch(function (e) { showError(f, e); });
    });
  }

  /* settings / perfil */
  var settingsForm = el('form[data-act="update-profile"]');
  if (settingsForm) {
    els('input[type="file"]', settingsForm).forEach(function (input) {
      input.addEventListener("change", function () {
        var f = input.files[0];
        if (!f) return;
        var status = el("[data-upload-avatar]", settingsForm);
        uploadFile(f, status).then(function (m) {
          input.name === "avatar" ? el("[name=avatar_key]", settingsForm).value = m.key
                                  : el("[name=cover_key]", settingsForm).value = m.key;
        });
      });
    });
    settingsForm.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var f = ev.target;
      var payload = {
        display_name: el("[name=display_name]", f).value || NEXA.me.username,
        bio: el("[name=bio]", f).value || "",
        is_private: el("[name=is_private]", f).checked,
        avatar_key: el("[name=avatar_key]", f).value || null,
        cover_key: el("[name=cover_key]", f).value || null
      };
      api("/api/auth/me", { method: "PATCH", json: payload })
        .then(function () { location.reload(); }).catch(function (e) { showError(f, e); });
    });
  }

  /* ------------------------- busca */
  var searchForm = el("#search-form");
  if (searchForm) {
    searchForm.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var q = el("[name=q]", searchForm).value.trim();
      if (!q) return;
      api("/api/search?q=" + encodeURIComponent(q)).then(function (d) { renderSearch(d); })
        .catch(function (e) { alert(e.message); });
    });
  }
  function renderSearch(d) {
    var box = el("#search-results");
    box.innerHTML = "";
    var html = "";
    if (d.users && d.users.length) {
      html += '<h3 class="section-title">Pessoas</h3>';
      d.users.forEach(function (u) {
        html += '<a class="card list-item" href="/profile/' + u.username + '"><span class="ico">👤</span><div class="card-body"><strong>' + u.display_name + '</strong><span class="muted small">@' + u.username + '</span></div></a>';
      });
    }
    if (d.groups && d.groups.length) {
      html += '<h3 class="section-title">Grupos</h3>';
      d.groups.forEach(function (g) { html += '<a class="card list-item" href="/groups/' + g.slug + '"><span class="ico">👥</span><div class="card-body"><strong>' + g.name + '</strong><span class="muted small">' + g.member_count + ' membros</span></div></a>'; });
    }
    if (d.circles && d.circles.length) {
      html += '<h3 class="section-title">Círculos</h3>';
      d.circles.forEach(function (c) { html += '<a class="card list-item" href="/circles/' + c.slug + '"><span class="ico">🔄</span><div class="card-body"><strong>' + c.name + '</strong></div></a>'; });
    }
    if (d.events && d.events.length) {
      html += '<h3 class="section-title">Eventos</h3>';
      d.events.forEach(function (e) { html += '<a class="card list-item" href="/events/' + e.slug + '"><span class="ico">📅</span><div class="card-body"><strong>' + e.name + '</strong><span class="muted small">' + (e.location || "Online") + '</span></div></a>'; });
    }
    if (d.posts && d.posts.length) {
      html += '<h3 class="section-title">Posts</h3>';
      d.posts.forEach(function (p) {
        html += '<a class="card list-item" href="/post/' + p.slug + '"><span class="ico">📄</span><div class="card-body"><strong>' + (p.title || "Post de " + p.author.display_name) + '</strong><span class="muted small">por ' + p.author.display_name + '</span></div></a>';
      });
    }
    if (!html) html = '<p class="empty">Nada encontrado para essa busca.</p>';
    box.innerHTML = html;
  }

  /* ------------------------- mensagens realtime */
  var messagesPage = document.body.classList && document.querySelector(".messages-page");
  if (messagesPage) initMessages(messagesPage);

  function initMessages(root) {
    var list = el("#convos-list"), msgs = el("#thread-messages"),
        header = el("#thread-header"), form = el("#thread-form"), cur = null;
    var ws = null;

    function mime(u) {
      return (u && u.avatar) ? '<img class="avatar sm" src="' + u.avatar + '" alt="">' : '<span class="avatar-fallback sm">' + (u.display_name || "?").charAt(0) + "</span>";
    }

    function showConv(conv) {
      cur = conv;
      header.innerHTML = '<span>🟢 ' + (conv.other.online ? "online" : "offline") + '</span> ' + conv.other.display_name;
      msgs.innerHTML = "<p class='muted'>carregando...</p>";
      form.hidden = false;
      api("/api/messages/conversations/" + conv.id).then(function (items) {
        msgs.innerHTML = items.map(function (m) {
          var c = m.media ? '<a class="attachment" href="' + m.media.url + '" target="_blank" rel="noopener">📎 anexo</a>' : "";
          return '<div class="msg' + (m.sender_id === conv.other.id ? "" : " me") + '">' + esc(m.content) + c + '<span class="t">' + (m.created_at || "").slice(0, 16).replace("T", " ") + '</span></div>';
        }).join("");
        msgs.scrollTop = msgs.scrollHeight;
        api("/api/messages/conversations/" + conv.id + "/read", { method: "POST" });
        refreshConvos();
      }).catch(function () {});
    }

    function refreshConvos() {
      api("/api/messages/conversations").then(function (convs) {
        if (!convs.length) { list.innerHTML = '<p class="muted">Sem conversas ainda. Busque pessoas para começar.</p>'; return; }
        list.innerHTML = convs.map(function (c) {
          return '<a href="#" data-id="' + c.id + '">' + mime(c.other) +
            '<div class="card-body"><strong>' + c.other.display_name + '</strong><span class="muted small">' + esc(c.last_message || "") + '</span><span class="un">' + (c.unread ? c.unread : "") + '</span></div></a>';
        }).join("");
        els("a", list).forEach(function (a) {
          a.addEventListener("click", function (ev) {
            ev.preventDefault();
            var cid = parseInt(a.dataset.id, 10);
            var conv = convs.find(function (c) { return c.id === cid; });
            if (conv) showConv(conv);
          });
        });
      }).catch(function () {});
    }
    refreshConvos();

    function send(payload) {
      if (ws && ws.readyState === WebSocket.OPEN) { ws.send(JSON.stringify(payload)); return; }
      api("/api/messages", { method: "POST", json: payload });
    }

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var input = el("[name=content]", form);
      var text = input.value.trim();
      if (!text || !cur) return;
      input.value = "";
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "message", csrfFree: true, conversation_id: cur.id,
          recipient: cur.other.username, content: text }));
        var isme = true;
      } else {
        api("/api/messages", { method: "POST", json: { conversation_id: cur.id, content: text } })
          .then(function (m) { appendMsg(m, true); refreshConvos(); }).catch(function () {});
      }
    });

    function appendMsg(m, mine) {
      var c = m.media ? '<a class="attachment" href="' + m.media.url + '">📎</a>' : "";
      var div = document.createElement("div");
      div.className = "msg" + (mine ? " me" : "");
      div.innerHTML = esc(m.content) + c + '<span class="t">' + (m.created_at || "").slice(0, 16).replace("T", " ") + "</span>";
      msgs.appendChild(div);
      msgs.scrollTop = msgs.scrollHeight;
    }

    function connect() {
      var url = NEXA.wsUrl + "?token=" + encodeURIComponent(NEXA.token || "");
      ws = new WebSocket(url);
      ws.onmessage = function (ev) {
        var d = JSON.parse(ev.data);
        if (d.type === "message") {
          var m = d.message;
          if (m.conversation_id === (cur ? cur.id : null)) appendMsg(m, false);
          refreshConvos();
          var n = m.content || "nova mensagem";
          if (Notification && Notification.permission === "granted" && document.visibilityState === "hidden") {
            new Notification("NEXA — mensagem", { body: n.slice(0, 60) });
          }
        }
        if (d.type === "notification") {
          if (Notification && Notification.permission === "granted" && document.visibilityState === "hidden") {
            new Notification("NEXA — " + d.notification.message.slice(0, 40));
          }
        }
      };
      ws.onclose = function () { setTimeout(connect, 4000); };
      setInterval(function () { if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" })); }, 30000);
    }
    connect();

    if (Notification && Notification.permission === "default") Notification.requestPermission();
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  window.NEXA = NEXA;
})();