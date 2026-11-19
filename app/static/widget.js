(function () {
  var script = document.currentScript || document.querySelector("script[data-business]");
  if (!script) return;
  var business = script.getAttribute("data-business");
  if (!business) return;

  var title = script.getAttribute("data-title") || "How can we help?";
  var color = script.getAttribute("data-color") || "#f97316";
  if (!/^#[0-9a-fA-F]{3,8}$/.test(color)) color = "#f97316";
  var api = new URL(script.src).origin;

  var css =
    ".ctl-btn{position:fixed;right:16px;bottom:16px;z-index:99999;border:0;border-radius:999px;padding:12px 20px;font:600 15px system-ui,sans-serif;color:#fff;background:" + color + ";box-shadow:0 4px 14px rgba(0,0,0,.25);cursor:pointer}" +
    ".ctl-panel{position:fixed;right:16px;bottom:72px;z-index:99999;width:min(360px,calc(100vw - 32px));height:min(480px,calc(100vh - 100px));display:flex;flex-direction:column;background:#fff;border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,.28);overflow:hidden;font:14px system-ui,sans-serif;color:#222}" +
    ".ctl-head{padding:14px 16px;color:#fff;font-weight:600;background:" + color + "}" +
    ".ctl-log{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px;background:#f7f7f7}" +
    ".ctl-msg{max-width:85%;padding:8px 12px;border-radius:12px;white-space:pre-wrap;word-wrap:break-word}" +
    ".ctl-bot{align-self:flex-start;background:#fff;border:1px solid #e5e5e5}" +
    ".ctl-me{align-self:flex-end;color:#fff;background:" + color + "}" +
    ".ctl-form{display:flex;gap:6px;padding:10px;border-top:1px solid #eee;background:#fff}" +
    ".ctl-form input,.ctl-lead input{flex:1;min-width:0;padding:9px 10px;border:1px solid #ccc;border-radius:8px;font-size:14px}" +
    ".ctl-send{border:0;border-radius:8px;padding:9px 14px;color:#fff;font-weight:600;background:" + color + ";cursor:pointer}" +
    ".ctl-send:disabled{opacity:.5}" +
    ".ctl-lead{display:flex;flex-direction:column;gap:6px;padding:10px;background:#fff;border:1px solid #e5e5e5;border-radius:12px}" +
    ".ctl-note{font-size:12px;color:#666}";
  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  var button = el("button", "ctl-btn", "Chat");
  var panel = el("div", "ctl-panel");
  panel.style.display = "none";
  var head = el("div", "ctl-head", title);
  var log = el("div", "ctl-log");
  var form = el("form", "ctl-form");
  var input = el("input");
  input.type = "text";
  input.placeholder = "Type your question";
  input.maxLength = 500;
  var send = el("button", "ctl-send", "Send");
  send.type = "submit";
  form.appendChild(input);
  form.appendChild(send);
  panel.appendChild(head);
  panel.appendChild(log);
  panel.appendChild(form);
  document.body.appendChild(button);
  document.body.appendChild(panel);

  function say(text, who) {
    var m = el("div", "ctl-msg ctl-" + who, text);
    log.appendChild(m);
    log.scrollTop = log.scrollHeight;
  }

  function post(path, body) {
    return fetch(api + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        return { ok: r.ok, status: r.status, data: d };
      });
    });
  }

  var lastQuestion = "";
  var leadShown = false;

  function showLeadForm() {
    if (leadShown) return;
    leadShown = true;
    var box = el("form", "ctl-lead");
    box.appendChild(el("div", "ctl-note", "Leave your details and our team will get back to you."));
    var name = el("input");
    name.placeholder = "Your name";
    name.required = true;
    name.maxLength = 100;
    var phone = el("input");
    phone.placeholder = "Phone number";
    phone.type = "tel";
    phone.required = true;
    phone.maxLength = 20;
    var go = el("button", "ctl-send", "Submit");
    go.type = "submit";
    box.appendChild(name);
    box.appendChild(phone);
    box.appendChild(go);
    box.appendChild(el("div", "ctl-note", "By submitting, you agree to be contacted about your enquiry."));
    log.appendChild(box);
    log.scrollTop = log.scrollHeight;

    box.addEventListener("submit", function (e) {
      e.preventDefault();
      go.disabled = true;
      post("/leads", {
        business_id: business,
        name: name.value.trim(),
        phone: phone.value.trim(),
        interest: lastQuestion.slice(0, 200) || null
      }).then(function (res) {
        if (res.ok) {
          box.remove();
          say("Thank you! Our team will contact you soon.", "bot");
        } else if (res.status === 422) {
          say("Please check your phone number and try again.", "bot");
          go.disabled = false;
        } else {
          say("Sorry, we could not save your details. Please try again.", "bot");
          go.disabled = false;
        }
      }).catch(function () {
        say("Sorry, something went wrong. Please try again.", "bot");
        go.disabled = false;
      });
    });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = input.value.trim();
    if (!q) return;
    lastQuestion = q;
    input.value = "";
    say(q, "me");
    send.disabled = true;
    post("/ask", { business_id: business, question: q }).then(function (res) {
      if (res.status === 429) {
        say("Please wait a moment and try again.", "bot");
      } else if (!res.ok) {
        say("Sorry, something went wrong. Please try again.", "bot");
      } else {
        say(res.data.answer, "bot");
        if (res.data.handoff) showLeadForm();
      }
    }).catch(function () {
      say("Sorry, something went wrong. Please try again.", "bot");
    }).then(function () {
      send.disabled = false;
    });
  });

  button.addEventListener("click", function () {
    var open = panel.style.display !== "none";
    panel.style.display = open ? "none" : "flex";
    button.textContent = open ? "Chat" : "Close";
  });

  say("Hi! How can we help you today?", "bot");
})();
