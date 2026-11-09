const LANG_NAMES = { "en-IN": "English", "hi-IN": "हिन्दी", "kn-IN": "ಕನ್ನಡ", "ta-IN": "தமிழ்", "te-IN": "తెలుగు" };
const NEXT_STATUS = { AWAITING_CASH: "CONFIRMED", AWAITING_UPI: "CONFIRMED", CONFIRMED: "PREPARING", PREPARING: "READY", READY: "DELIVERED" };
const NEXT_LABEL = { AWAITING_CASH: "✅ Cash Collected → Confirm Order", AWAITING_UPI: "✅ UPI Payment Received → Confirm Order",
                     CONFIRMED: "Start preparing", PREPARING: "Mark ready", READY: "Mark delivered" };
// Orders the customer has submitted but the staff have not confirmed yet (payment not checked).
const AWAITING = ["AWAITING_CASH", "AWAITING_UPI"];
const isAwaiting = (o) => AWAITING.includes(o.status);
const placedAt = (o) => o.confirmed_at || o.created_at;

// ---------- small helpers ----------

// el("div", {class: "x"}, "text", otherNode) builds HTML safely (no innerHTML).
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key === "checked" || key === "value") node[key] = value;
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

// Staff actions (confirm orders, edit the menu) need the STAFF_PIN from .env.
function staffPin() {
  try { return localStorage.getItem("staffPin") || ""; } catch (e) { return window._staffPin || ""; }
}
function saveStaffPin(pin) {
  window._staffPin = pin;
  try { if (pin) localStorage.setItem("staffPin", pin); else localStorage.removeItem("staffPin"); } catch (e) { /* ignore */ }
}

async function api(path, options, retried) {
  const opts = Object.assign({}, options || {});
  const ownPin = opts.headers && opts.headers["X-Confirm-Pin"];   // payment confirmation: PIN typed just now
  opts.headers = Object.assign({ "X-Staff-Pin": staffPin() || window._staffPin || "" }, opts.headers || {});
  if (ownPin) retried = true;                                      // never ask again / never remember it
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && data.login && !data.staff_pin) {     // staff accounts: go and log in
    location.href = "/login?next=" + encodeURIComponent(location.pathname);
    throw new Error("Please log in");
  }
  if (res.status === 401 && data.staff_pin && !retried) {
    const pin = prompt(staffPin() ? "Wrong staff PIN. Enter the staff PIN:" : "Enter the staff PIN:");
    if (pin) { saveStaffPin(pin.trim()); return api(path, options, true); }
  }
  if (res.status === 401 && data.staff_pin && !ownPin) saveStaffPin("");
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function sendJson(method, body) {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

function clock(iso) {
  return iso ? new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "";
}

function dateTime(iso) {
  return iso ? new Date(iso).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "";
}

function ago(iso) {
  if (!iso) return "";
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return mins < 1 ? "just now" : mins + " min ago";
}

function servingLabel(order) {
  if (order.channel === "phone") return "📞 Phone";
  if (order.order_type === "takeaway") return "🥡 Takeaway";
  return order.table_no ? "🍽 Table " + order.table_no : "🍽 Dine-in";
}

function paymentLabel(mode) {
  if (mode === "upi") return "📱 UPI";
  if (mode === "cash") return "💵 Cash";
  return mode ? mode.toUpperCase() : "";
}

function setConnection(ok) {
  const box = document.getElementById("conn");
  box.textContent = ok ? "● live" : "⚠ cannot reach server";
  box.className = ok ? "conn" : "conn bad";
}

// ---------- sound alert ----------

let soundOn = false;
let audioCtx = null;

function beep() {
  if (!soundOn || !audioCtx) return;
  [880, 1175, 880, 1175].forEach((freq, i) => {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.8, audioCtx.currentTime + i * 0.2);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + i * 0.2 + 0.18);
    osc.connect(gain).connect(audioCtx.destination);
    osc.start(audioCtx.currentTime + i * 0.2);
    osc.stop(audioCtx.currentTime + i * 0.2 + 0.2);
  });
}

document.getElementById("soundBtn").addEventListener("click", (e) => {
  soundOn = !soundOn;
  if (soundOn) {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    beep();
  }
  e.target.textContent = soundOn ? "🔔 Sound alerts ON" : "🔔 Enable sound alerts";
  e.target.classList.toggle("on", soundOn);
});

// ---------- loud alerts: beep + voice announcement + red banner ----------

function announce(text) {
  if (!soundOn || !("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-IN";
  u.volume = 1;
  u.rate = 0.95;
  window.speechSynthesis.speak(u);
}

function servingSpoken(order) {
  const who = order.customer_name ? "for " + order.customer_name + ", " : "";
  if (order.channel === "phone") return who + "phone order";
  if (order.order_type === "takeaway") return who + "takeaway";
  return who + (order.table_no ? "table " + order.table_no : "dine in");
}

// Who is logged in (staff accounts) -> name + log out button in the header.
fetch("/api/me").then((r) => r.json()).then((me) => {
  if (!me.staff || me.staff.name === "PIN") return;
  document.querySelector(".top-right").append(
    el("span", { class: "who" }, "👤 " + me.staff.name + " (" + me.staff.role + ")"),
    el("a", { class: "btn ghost", href: "/logout" }, "Log out"));
}).catch(() => {});

const alertBar = el("div", { class: "alert-bar", hidden: "" });
document.querySelector("header.top").after(alertBar);
let lastRing = 0;

// ---------- live board ----------

let knownIds = null; // null until the first load, so old orders don't beep
let knownReady = null;

function orderCard(order, fresh) {
  const lines = order.items.map((it) =>
    el("li", {}, it.quantity + " × " + it.name,
       it.addons ? el("span", { class: "addon" }, "+ " + it.addons) : "",
       it.notes ? el("span", { class: "note" }, "↳ " + it.notes) : ""));
  const isCashPending = order.status === "AWAITING_CASH";
  const isUpiPending = order.status === "AWAITING_UPI";
  const buttons = [];
  if (NEXT_STATUS[order.status]) {
    buttons.push(el("button", {
      class: "btn small" + (isCashPending ? " cash-collect" : isUpiPending ? " upi-check" : ""),
      onclick: () => {
        if (isCashPending || isUpiPending) {
          // Payment confirmation: the secret staff PIN is asked EVERY time.
          const what = isCashPending ? "Cash of ₹" + order.total + " collected" : "UPI payment of ₹" + order.total + " received";
          const pin = prompt("Order #" + order.id + ": " + what + "?\nEnter the staff PIN to confirm the order:");
          if (!pin) return;
          changeStatus(order.id, "CONFIRMED", pin.trim());
          return;
        }
        changeStatus(order.id, NEXT_STATUS[order.status]);
      }
    }, NEXT_LABEL[order.status]));
  }
  if (!isAwaiting(order)) {        // the bill and kitchen ticket exist only after the payment is confirmed
    buttons.push(el("a", { class: "btn small", href: "/kot/" + order.id + "?print=1", target: "_blank" }, "🧾 KOT"));
    buttons.push(el("a", { class: "btn small", href: "/bill/" + order.id, target: "_blank" }, "🖨 Bill"));
  }
  buttons.push(el("button", { class: "btn small danger", onclick: () => {
    if (confirm("Cancel order #" + order.id + "?")) changeStatus(order.id, "CANCELLED");
  } }, "Cancel"));

  const metaChips = [
    el("span", { class: "chip" }, LANG_NAMES[order.language] || order.language),
    el("span", { class: "chip serving" }, servingLabel(order)),
  ];
  if (order.payment_mode) {
    metaChips.push(el("span", { class: "chip payment" }, paymentLabel(order.payment_mode)));
  }
  if (order.customer_name) {
    metaChips.push(el("span", { class: "chip customer" }, "👤 " + order.customer_name + (order.customer_phone ? " · " + order.customer_phone : "")));
  }
  if (order.eta_minutes && ["CONFIRMED", "PREPARING"].includes(order.status) && order.confirmed_at) {
    const left = Math.round(order.eta_minutes - (Date.now() - new Date(order.confirmed_at).getTime()) / 60000);
    metaChips.push(el("span", { class: "chip eta" + (left < 0 ? " late" : "") },
      left < 0 ? "⏱ " + (-left) + " min late" : "⏱ ~" + left + " min left"));
  }
  if (order.confirmed_by) {
    metaChips.push(el("span", { class: "chip by" }, "✔ " + (order.confirmed_by === "Razorpay" ? "Paid online" : order.confirmed_by)));
  }

  return el("div", { class: "card status-" + order.status + (fresh ? " fresh" : "") },
    ...(isCashPending ? [el("div", { class: "cash-banner" }, "💵 COLLECT CASH ₹" + order.total + " BEFORE PREPARING")] : []),
    ...(isUpiPending ? [el("div", { class: "upi-banner" }, "📱 CHECK UPI PAYMENT OF ₹" + order.total + " IN YOUR UPI APP BEFORE PREPARING")] : []),
    el("div", { class: "card-head" },
      el("strong", {}, "#" + order.id),
      el("span", { class: "meta" }, clock(placedAt(order)) + " · " + ago(placedAt(order)), ...metaChips)),
    el("ul", { class: "lines" }, lines),
    el("div", { class: "card-foot" }, el("span", { class: "total" }, "₹" + order.total), el("span", {}, buttons)));
}

async function loadLive() {
  try {
    const orders = await api("/api/orders/live");
    setConnection(true);
    const ids = new Set(orders.map((o) => o.id));
    const newOnes = knownIds === null ? [] : orders.filter((o) => !knownIds.has(o.id));
    const waiting = orders.filter((o) => o.status === "CONFIRMED" || isAwaiting(o));
    if (newOnes.length) {
      beep();
      const cashNew = newOnes.filter((o) => o.status === "AWAITING_CASH");
      let msg = "New order number " + newOnes.map((o) => o.id).join(" and ") + ". " +
        newOnes.map((o) => servingSpoken(o) + ". " + o.items.map((i) => i.quantity + " " + i.name).join(", ")).join(". ");
      if (cashNew.length) {
        msg += ". Cash payment. Please collect " +
          cashNew.map((o) => "rupees " + o.total + " for order number " + o.id).join(" and ") + ".";
      }
      const upiNew = newOnes.filter((o) => o.status === "AWAITING_UPI");
      if (upiNew.length) {
        msg += ". U P I payment. Please check " +
          upiNew.map((o) => "rupees " + o.total + " for order number " + o.id).join(" and ") + " in your U P I app.";
      }
      announce(msg);
      lastRing = Date.now();
    } else if (waiting.length && Date.now() - lastRing > 20000) {   // nobody has accepted it yet: ring again
      beep();
      announce(waiting.length + (waiting.length === 1 ? " new order is" : " new orders are") + " waiting");
      lastRing = Date.now();
    }
    alertBar.hidden = !waiting.length;
    alertBar.textContent = "🔔 " + waiting.length + " new order" + (waiting.length === 1 ? "" : "s") +
      " waiting: " + waiting.map((o) => "#" + o.id).join(", ") + (soundOn ? "" : "   (turn on sound alerts above)");
    const readyNow = new Set(orders.filter((o) => o.status === "READY").map((o) => o.id));
    if (knownReady !== null) {
      orders.filter((o) => o.status === "READY" && !knownReady.has(o.id)).forEach((o) => {
        beep();
        announce("Order number " + o.id + " is ready" +
          (o.order_type === "takeaway" ? " for pickup" : o.table_no ? " for table " + o.table_no : ""));
      });
    }
    knownReady = readyNow;
    const freshIds = new Set(newOnes.map((o) => o.id));
    knownIds = ids;
    for (const status of ["CONFIRMED", "PREPARING", "READY"]) {
      const mine = orders.filter((o) => o.status === status || (status === "CONFIRMED" && isAwaiting(o)));
      document.getElementById("count-" + status).textContent = mine.length;
      document.getElementById("col-" + status).replaceChildren(
        ...(mine.length ? mine.map((o) => orderCard(o, freshIds.has(o.id) || (status === "CONFIRMED" && placedAt(o) && newestSeconds(o) < 60)))
                        : [el("div", { class: "empty" }, "No orders")]));
    }
  } catch (err) {
    setConnection(false);
  }
}

function newestSeconds(order) {
  return (Date.now() - new Date(placedAt(order)).getTime()) / 1000;
}

async function changeStatus(id, status, confirmPin) {
  try {
    const options = sendJson("POST", { status });
    if (confirmPin) options.headers["X-Staff-Pin"] = options.headers["X-Confirm-Pin"] = confirmPin;
    await api("/api/orders/" + id + "/status", options);
  } catch (err) {
    alert(confirmPin && /PIN/.test(err.message) && !/STAFF_PIN/.test(err.message)
      ? "Wrong staff PIN. Order #" + id + " was NOT confirmed." : err.message);
  }
  loadLive();
}

// ---------- history ----------

async function loadHistory() {
  const orders = await api("/api/orders/history?limit=100");
  const box = document.getElementById("historyBox");
  if (!orders.length) {
    box.replaceChildren(el("div", { class: "empty" }, "No finished orders yet"));
    return;
  }
  const rows = orders.map((o) => el("tr", {},
    el("td", {}, "#" + o.id),
    el("td", {}, dateTime(o.confirmed_at)),
    el("td", {}, o.customer_name ? o.customer_name + (o.customer_phone ? " (" + o.customer_phone + ")" : "") : "—"),
    el("td", {}, o.items.map((i) => i.quantity + " × " + i.name).join(", ")),
    el("td", {}, "₹" + o.total),
    el("td", {}, (o.payment_mode ? paymentLabel(o.payment_mode) : "—")),
    el("td", {}, servingLabel(o)),
    el("td", {}, el("span", { class: "badge " + o.status }, o.status)),
    el("td", {}, o.confirmed_by || "—"),
    el("td", {}, el("a", { href: "/bill/" + o.id, target: "_blank" }, "🖨"))));
  box.replaceChildren(el("table", {},
    el("thead", {}, el("tr", {}, ["Order", "Time", "Customer", "Items", "Total", "Payment", "Type", "Status", "Confirmed by", "Bill"].map((h) => el("th", {}, h)))),
    el("tbody", {}, rows)));
}

// ---------- menu manager ----------

const MENU_FIELDS = [
  ["name_en", "English name *"], ["name_hi", "Hindi name"], ["name_kn", "Kannada name"],
  ["name_ta", "Tamil name"], ["name_te", "Telugu name"], ["category", "Category * (e.g. Tiffin, Drinks)"],
  ["price", "Price ₹ *", "number"], ["stock", "Stock count (empty = unlimited)", "number"],
  ["aliases", "Other spoken names, comma separated (e.g. dose, dosai)"],
  ["addons", "Paid add-ons (e.g. Extra Cheese:15, Extra Chutney:10)"],
  ["description", "Description (the agent reads this when asked \"what is it?\")"],
  ["image_url", "Photo link (https://...) or upload below"],
];

function menuForm(item, onDone) {
  const inputs = {};
  const rows = MENU_FIELDS.map(([key, label, type]) => {
    const input = el(key === "description" ? "textarea" : "input",
                     { type: type || "text", value: item && item[key] != null ? item[key] : "" });
    if (type === "number") input.min = "0";
    inputs[key] = input;
    return el("label", { class: "form-row" }, el("span", {}, label), input);
  });
  const veg = el("input", { type: "checkbox", checked: item ? !!item.veg : true });
  const photo = el("input", { type: "file", accept: "image/jpeg,image/png,image/webp" });
  const msg = el("p", { class: "form-msg" });
  const save = el("button", { class: "btn", type: "submit" }, item ? "Save changes" : "➕ Add dish");
  const form = el("form", { class: "menu-form" }, ...rows,
    el("label", { class: "form-row inline" }, veg, el("span", {}, "Vegetarian")),
    el("label", { class: "form-row" }, el("span", {}, "Upload photo (JPG/PNG/WEBP, under 2 MB)"), photo),
    el("div", { class: "form-actions" }, save,
       el("button", { class: "btn ghost-dark", type: "button", onclick: () => onDone(false) }, "Cancel")),
    msg);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = { veg: veg.checked };
    for (const [key] of MENU_FIELDS) body[key] = inputs[key].value.trim();
    save.disabled = true;
    try {
      const saved = item
        ? await api("/api/menu/" + item.id, sendJson("PATCH", body))
        : await api("/api/menu", sendJson("POST", body));
      if (photo.files[0]) {
        const fd = new FormData();
        fd.append("image", photo.files[0]);
        await api("/api/menu/" + saved.id + "/image", { method: "POST", body: fd });
      }
      onDone(true);
    } catch (err) {
      msg.textContent = "⚠ " + err.message;
      save.disabled = false;
    }
  });
  return form;
}

async function loadMenu() {
  const items = await api("/api/menu");
  const box = document.getElementById("menuBox");
  const addBox = el("div", { class: "add-box" });
  const addBtn = el("button", { class: "btn", onclick: () => {
    addBox.replaceChildren(menuForm(null, (changed) => { addBox.replaceChildren(addBtn); if (changed) loadMenu(); }));
  } }, "➕ Add a new dish");
  addBox.append(addBtn);
  const nodes = [addBox];
  let lastCategory = null;
  for (const item of items) {
    if (item.category !== lastCategory) {
      nodes.push(el("h3", { class: "cat" }, item.category));
      lastCategory = item.category;
    }
    const priceInput = el("input", { type: "number", min: "1", max: "5000", value: item.price, title: "Price ₹" });
    const stockInput = el("input", { type: "number", min: "0", placeholder: "∞", value: item.stock == null ? "" : item.stock,
                                     title: "Stock count (empty = unlimited)" });
    const editBox = el("div", { class: "edit-box" });
    const row = el("div", { class: "menu-row" + (item.available ? "" : " off") },
      item.image_url ? el("img", { class: "thumb", src: item.image_url, alt: "" }) : el("span", { class: "thumb none" }, "🍽"),
      el("span", { class: "name" }, item.name_en,
         item.addons ? el("small", {}, "+ " + item.addons.replace(/:(\d+)/g, " ₹$1")) : ""),
      el("span", { class: "price-box" }, "₹", priceInput, "Stock", stockInput,
         el("button", { class: "btn small", onclick: async () => {
           try {
             await api("/api/menu/" + item.id, sendJson("PATCH", { price: priceInput.value, stock: stockInput.value }));
             loadMenu();
           } catch (err) { alert(err.message); }
         } }, "Save")),
      el("label", { class: "switch" },
         el("input", { type: "checkbox", checked: !!item.available, onchange: async (e) => {
           try {
             await api("/api/menu/" + item.id, sendJson("PATCH", { available: e.target.checked }));
           } catch (err) { alert(err.message); }
           loadMenu();
         } }),
         item.available ? "Available" : "Sold out"),
      el("span", { class: "row-actions" },
         el("button", { class: "btn small", onclick: () => {
           editBox.replaceChildren(menuForm(item, (changed) => { editBox.replaceChildren(); if (changed) loadMenu(); }));
         } }, "✏ Edit"),
         el("button", { class: "btn small danger", onclick: async () => {
           if (!confirm("Remove " + item.name_en + " from the menu? Old bills keep it.")) return;
           try { await api("/api/menu/" + item.id, { method: "DELETE" }); loadMenu(); } catch (err) { alert(err.message); }
         } }, "Remove")));
    nodes.push(row, editBox);
  }
  box.replaceChildren(...nodes);
}

// ---------- today's numbers ----------

function barList(rows) {
  if (!rows.length) return el("div", { class: "empty" }, "No data yet");
  const max = Math.max(...rows.map((r) => r.quantity));
  return el("div", {}, rows.map((r) => el("div", { class: "bar-row" },
    el("span", {}, r.name),
    el("div", { class: "bar" }, el("span", { style: "width:" + Math.round((r.quantity / max) * 100) + "%" })),
    el("strong", {}, r.quantity))));
}

// Rows of {name, value}; "show" turns the number into text (for example "₹1,200").
function bars(rows, show = (v) => v) {
  if (!rows.length) return el("div", { class: "empty" }, "No data yet");
  const max = Math.max(...rows.map((r) => r.value), 1);
  return el("div", {}, rows.map((r) => el("div", { class: "bar-row" },
    el("span", {}, r.name),
    el("div", { class: "bar" }, el("span", { style: "width:" + Math.round((r.value / max) * 100) + "%" })),
    el("strong", {}, show(r.value)))));
}

function hourName(h) {
  const hr = h % 12 === 0 ? 12 : h % 12;
  return hr + (h < 12 ? " AM" : " PM");
}

async function loadStats() {
  const s = await api("/api/stats");
  const a = await api("/api/analytics");
  const feedback = await api("/api/feedback").catch(() => []);
  const langs = s.languages.length
    ? s.languages.map((l) => el("div", { class: "bar-row" },
        el("span", {}, LANG_NAMES[l.language] || l.language),
        el("div", { class: "bar" }, el("span", { style: "width:" + Math.round((l.orders / s.orders_today) * 100) + "%" })),
        el("strong", {}, l.orders)))
    : [el("div", { class: "empty" }, "No data yet")];
  document.getElementById("statsBox").replaceChildren(
    el("div", { class: "stat-cards" },
      el("div", { class: "stat" }, el("div", { class: "num" }, s.orders_today), el("div", { class: "label" }, "Orders today")),
      el("div", { class: "stat" }, el("div", { class: "num" }, "₹" + s.revenue_today), el("div", { class: "label" }, "Sales today")),
      el("div", { class: "stat" }, el("div", { class: "num" }, "₹" + s.average_order), el("div", { class: "label" }, "Average order")),
      el("div", { class: "stat" }, el("div", { class: "num" }, a.average_rating ? "★ " + a.average_rating : "—"),
         el("div", { class: "label" }, "Customer rating (" + a.ratings + " reviews)"))),
    el("div", { class: "two" },
      el("div", {}, el("h3", {}, "Top dishes today"), barList(s.top_today)),
      el("div", {}, el("h3", {}, "Orders by language"), el("div", {}, langs)),
      el("div", {}, el("h3", {}, "Top dishes of all time"), barList(s.top_all_time))),
    el("h3", { class: "section" }, "Last 7 days"),
    el("div", { class: "two" },
      el("div", {}, el("h3", {}, "Sales per day"),
         bars(a.days.map((d) => ({ name: d.day, value: d.revenue })), (v) => "₹" + v.toLocaleString("en-IN"))),
      el("div", {}, el("h3", {}, "Orders per day"), bars(a.days.map((d) => ({ name: d.day, value: d.orders })))),
      el("div", {}, el("h3", {}, "Top dishes this week"), bars(a.top_week.map((d) => ({ name: d.name, value: d.quantity })))),
      el("div", {}, el("h3", {}, "Dine-in / takeaway / phone"), bars(a.types.map((t) => ({ name: t.name, value: t.orders })))),
      el("div", {}, el("h3", {}, "Busy hours (last 30 days)"),
         bars(a.busy_hours.map((h) => ({ name: hourName(h.hour) + " – " + hourName((h.hour + 1) % 24), value: h.orders })))),
      el("div", {}, el("h3", {}, "Customers"),
         el("p", { class: "meta" }, a.repeat_customers + " of " + a.customers + " identified customers ordered more than once"))),
    el("h3", { class: "section" }, "Latest customer feedback"),
    feedback.length
      ? el("ul", { class: "feedback" }, feedback.slice(0, 10).map((f) => el("li", {},
          el("strong", {}, "★".repeat(f.rating) + "☆".repeat(5 - f.rating)), " #" + f.order_id +
          (f.customer_name ? " · " + f.customer_name : ""), f.comment ? el("div", { class: "meta" }, "“" + f.comment + "”") : "")))
      : el("div", { class: "empty" }, "No feedback yet"));
}

// ---------- tabs and refresh ----------

const LOADERS = { live: loadLive, history: loadHistory, menu: loadMenu, stats: loadStats };
let activeTab = "live";

function showTab(name) {
  activeTab = name;
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => { p.hidden = p.id !== "tab-" + name; });
  LOADERS[name]().catch((err) => setConnection(false));
}

document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));

loadLive();
setInterval(loadLive, 4000);                      // always watching for new orders
setInterval(() => {                                // other tabs refresh more slowly
  if (activeTab === "history" || activeTab === "stats") LOADERS[activeTab]().catch(() => {});
}, 10000);
