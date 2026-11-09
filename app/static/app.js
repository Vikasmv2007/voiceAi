const micBtn = document.getElementById("micBtn");
const statusEl = document.getElementById("status");
const transcriptEl = document.getElementById("transcript");
const langSel = document.getElementById("language");
const replyEl = document.getElementById("reply");
const cartEl = document.getElementById("cart");
const totalEl = document.getElementById("total");
const typedForm = document.getElementById("typedForm");
const typedInput = document.getElementById("typedInput");

// Customer name, phone & serving fields
const custNameInput = document.getElementById("custName");
const custPhoneInput = document.getElementById("custPhone");
const orderTypeSelect = document.getElementById("orderType");
const tableNoInput = document.getElementById("tableNo");
const tableField = document.getElementById("tableField");

// Payment section elements
const paymentSection = document.getElementById("paymentSection");
const payUpiBtn = document.getElementById("payUpiBtn");
const payCashBtn = document.getElementById("payCashBtn");
const upiBox = document.getElementById("upiBox");
const cashBox = document.getElementById("cashBox");
const qrcodeBox = document.getElementById("qrcodeBox");
const upiDetails = document.getElementById("upiDetails");
const upiPayLink = document.getElementById("upiPayLink");
const confirmUpiBtn = document.getElementById("confirmUpiBtn");
const submitCashBtn = document.getElementById("submitCashBtn");

let currentPaymentMode = "upi";
let qrInstance = null;
const gatewayQr = document.getElementById("gatewayQr");
const taxLine = document.getElementById("taxLine");
const orderBox = document.getElementById("orderBox");
let paymentPoll = null;          // Razorpay QR on screen: ask the server whether the money arrived

function newSessionId() {
  return (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()) + Math.random();
}
let sessionId = newSessionId();

// Remember customer name/phone in this browser
try {
  if (custNameInput && localStorage.getItem("custName")) {
    custNameInput.value = localStorage.getItem("custName");
  }
  if (custPhoneInput && localStorage.getItem("custPhone")) {
    custPhoneInput.value = localStorage.getItem("custPhone");
  }
} catch (e) { /* ignore storage errors */ }

if (custNameInput) {
  custNameInput.addEventListener("change", () => {
    try { localStorage.setItem("custName", custNameInput.value.trim()); } catch (e) {}
  });
}
if (custPhoneInput) {
  custPhoneInput.addEventListener("change", () => {
    try { localStorage.setItem("custPhone", custPhoneInput.value.trim()); } catch (e) {}
  });
}

// Remembered in this browser so "same as last time" works. A QR code on the table can open the page as ?table=5.
let customerId;
try {
  customerId = localStorage.getItem("customerId");
  if (!customerId) { customerId = newSessionId(); localStorage.setItem("customerId", customerId); }
} catch (e) { customerId = newSessionId(); }
const tableFromUrl = new URLSearchParams(location.search).get("table");
if (tableNoInput && tableFromUrl) {
  tableNoInput.value = tableFromUrl;
}
if (orderTypeSelect) {
  orderTypeSelect.addEventListener("change", () => {
    if (tableField) {
      tableField.style.display = orderTypeSelect.value === "takeaway" ? "none" : "";
    }
  });
}

// ---- Alerts on this page: order confirmed, being prepared, READY ----
let audioCtx = null;
function unlockAudio() {          // browsers only allow sound after the customer has tapped something
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
  } catch (e) { /* no sound, the banner still shows */ }
}

function chime(times) {
  if (!audioCtx) return;
  for (let i = 0; i < times * 2; i++) {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    const t = audioCtx.currentTime + i * 0.25;
    osc.frequency.value = i % 2 ? 1175 : 880;
    gain.gain.setValueAtTime(0.8, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.22);
    osc.connect(gain).connect(audioCtx.destination);
    osc.start(t);
    osc.stop(t + 0.24);
  }
}

const bannerStyle = document.createElement("style");
bannerStyle.textContent = `
  .order-banner { padding: 14px; margin-bottom: 12px; border-radius: 10px; font-weight: 700; font-size: 1.1rem;
                  text-align: center; cursor: pointer; background: #dff3e6; color: #12462a; }
  .order-banner.ready { background: #1b8a4b; color: #fff; animation: bannerflash 1s infinite; }
  .order-banner.cash { background: #b45309; color: #fff; }
  .order-banner.bad { background: #b00020; color: #fff; }
  @keyframes bannerflash { 50% { background: #26b862; } }`;
document.head.appendChild(bannerStyle);

const banner = document.createElement("div");
banner.className = "order-banner";
banner.hidden = true;
banner.title = "Tap to dismiss";
let alarmTimer = null;
function stopAlarm() { clearInterval(alarmTimer); alarmTimer = null; }
banner.addEventListener("click", () => { banner.hidden = true; stopAlarm(); });
document.querySelector("main").prepend(banner);

function showBanner(text, kind) {
  banner.textContent = text;
  banner.className = "order-banner " + (kind || "");
  banner.hidden = false;
}

// Asks the server every few seconds how a confirmed order is doing.
function watchOrder(id, initialStatus) {
  let last = initialStatus || "CONFIRMED";
  let checks = 0;
  const remember = (on) => {
    try {
      const ids = JSON.parse(localStorage.getItem("watching") || "[]").filter((x) => x !== id);
      if (on) ids.push(id);
      localStorage.setItem("watching", JSON.stringify(ids));
    } catch (e) { /* storage blocked: alerts still work until the page is closed */ }
  };
  remember(true);
  const timer = setInterval(async () => {
    if (++checks > 2700) { clearInterval(timer); remember(false); return; }   // give up after about 3 hours
    try {
      const res = await fetch("/api/orders/" + id + "/track?lang=" + encodeURIComponent(langSel.value));
      if (!res.ok) return;
      const d = await res.json();
      if (d.status === last) return;
      last = d.status;
      renderOrderBox(id, d);
      if (d.status === "CONFIRMED") {
        showBanner("✅ " + (d.message || ("Order #" + id + " confirmed by kitchen!")));
        chime(1);
        if (d.message) speak(d.message);
      }
      if (d.status === "PREPARING") showBanner("👨‍🍳 " + d.message);
      if (d.status === "READY") {
        showBanner("🔔 " + d.message, "ready");
        let rings = 0;
        const ring = () => {                       // keeps ringing and speaking until the customer taps the banner
          if (banner.hidden || ++rings > 10) { stopAlarm(); return; }
          chime(3);
          speak(d.message, true);
        };
        stopAlarm();
        ring();
        alarmTimer = setInterval(ring, 12000);
      }
      if (d.status === "CANCELLED") { showBanner("⚠ " + d.message, "bad"); chime(1); speak(d.message); }
      if (["DELIVERED", "CANCELLED"].includes(d.status)) { clearInterval(timer); remember(false); }
    } catch (e) { /* offline for a moment: try again next time */ }
  }, 4000);
}

// If the customer closed the page and came back, keep watching their order.
try { JSON.parse(localStorage.getItem("watching") || "[]").forEach((id) => watchOrder(id)); } catch (e) { /* ignore */ }

// ---- Step 5: the agent speaks ----
const speakBox = document.getElementById("speakBox");
let currentAudio = null;

function stopSpeaking() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
}

async function speak(text, force) {
  if ((!speakBox.checked && !force) || !text) return;
  try {
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text, language: langSel.value }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "voice failed");
    }
    const blob = await res.blob();
    stopSpeaking();
    currentAudio = new Audio(URL.createObjectURL(blob));
    await currentAudio.play();
  } catch (err) {
    statusEl.textContent = "Voice problem: " + err.message + " (the text reply still works)";
  }
}

// ---- Convert Audio Blob to 16 kHz Mono 16-bit PCM WAV ----
async function blobToWav16k(blob) {
  const arrayBuffer = await blob.arrayBuffer();
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const audioBuffer = await ctx.decodeAudioData(arrayBuffer);

  const targetSampleRate = 16000;
  const offlineCtx = new OfflineAudioContext(1, Math.ceil(audioBuffer.duration * targetSampleRate), targetSampleRate);
  const source = offlineCtx.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(offlineCtx.destination);
  source.start(0);

  const resampled = await offlineCtx.startRendering();
  const samples = resampled.getChannelData(0);

  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(view, 8, 'WAVE');
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, 1, true); // 1 channel (mono)
  view.setUint32(24, targetSampleRate, true);
  view.setUint32(28, targetSampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true); // 16-bit
  writeString(view, 36, 'data');
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    let s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }

  return new Blob([view], { type: 'audio/wav' });
}

const MAX_SECONDS = 25; // Prisma REST limit is about 30 seconds
let mediaRecorder = null;
let chunks = [];
let stream = null;
let autoStop = null;

micBtn.addEventListener("click", () => {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    stopRecording();
  } else {
    startRecording();
  }
});

async function startRecording() {
  unlockAudio();
  stopSpeaking(); // the agent stops talking when the customer starts
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    statusEl.textContent = "Microphone blocked. Allow it in the browser address bar.";
    return;
  }
  chunks = [];
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  mediaRecorder.onstop = handleStop;
  mediaRecorder.start();
  micBtn.classList.add("recording");
  micBtn.textContent = "⏹ Tap to stop";
  statusEl.textContent = "Listening...";
  autoStop = setTimeout(stopRecording, MAX_SECONDS * 1000);
}

function stopRecording() {
  clearTimeout(autoStop);
  if (mediaRecorder && mediaRecorder.state === "recording") mediaRecorder.stop();
}

async function handleStop() {
  stream.getTracks().forEach((t) => t.stop());
  micBtn.classList.remove("recording");
  micBtn.disabled = true;
  micBtn.textContent = "Working...";
  statusEl.textContent = "Understanding your voice...";
  try {
    const blob = new Blob(chunks, { type: mediaRecorder.mimeType });
    const wavBlob = await blobToWav16k(blob);

    const form = new FormData();
    form.append("audio", wavBlob, "speech.wav");
    form.append("language", langSel.value);

    const res = await fetch("/api/stt", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Something went wrong");

    transcriptEl.textContent = data.transcript || "(nothing heard)";
    if (data.transcript) {
      await sendTurn(data.transcript);
    } else {
      statusEl.textContent = "I couldn't hear anything. Please try again.";
    }
  } catch (err) {
    statusEl.textContent = "Error: " + err.message;
  } finally {
    micBtn.disabled = false;
    micBtn.textContent = "🎤 Tap to speak";
  }
}

// ---- Step 4: talk to the order brain ----
async function sendTurn(text, overridePayment) {
  unlockAudio();
  statusEl.textContent = "Thinking...";
  const custName = (custNameInput && custNameInput.value.trim()) || undefined;
  const custPhone = (custPhoneInput && custPhoneInput.value.trim()) || undefined;
  const orderType = (orderTypeSelect && orderTypeSelect.value) || "dine-in";
  const tableVal = (tableNoInput && tableNoInput.value.trim()) || tableFromUrl || undefined;
  const paymentMode = overridePayment || currentPaymentMode;

  const res = await fetch("/api/turn", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      text: text,
      language: langSel.value,
      customer_id: customerId,
      order_type: orderType,
      table: tableVal,
      customer_name: custName,
      customer_phone: custPhone,
      payment_mode: paymentMode,
    }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Something went wrong");

  // The agent noticed another language (e.g. Tamil typed while English was selected): follow it.
  if (data.language && data.language !== langSel.value && langSel.querySelector('option[value="' + data.language + '"]')) {
    langSel.value = data.language;
  }
  replyEl.textContent = data.reply;
  renderCart(data.cart);
  speak(data.reply);

  // Sync profile details back from order brain
  if (data.customer_name && custNameInput && !custNameInput.value) {
    custNameInput.value = data.customer_name;
    try { localStorage.setItem("custName", data.customer_name); } catch (e) {}
  }
  if (data.customer_phone && custPhoneInput && !custPhoneInput.value) {
    custPhoneInput.value = data.customer_phone;
    try { localStorage.setItem("custPhone", data.customer_phone); } catch (e) {}
  }
  if (data.payment_mode) {
    setPaymentMode(data.payment_mode);
  }
  // If the customer SAID "takeaway" / "table 5", show it in the form too.
  if (data.serving && orderTypeSelect && data.serving.type) {
    orderTypeSelect.value = data.serving.type;
    if (tableField) tableField.style.display = data.serving.type === "takeaway" ? "none" : "";
    if (data.serving.table && tableNoInput && !tableNoInput.value) tableNoInput.value = data.serving.table;
  }

  // Update QR scanner display if cart has items
  renderPayment(data);

  // The customer can only SUBMIT. The staff confirm the order on the dashboard after
  // checking the payment; watchOrder() tells the customer when that happens.
  if (data.submitted) {
    stopPaymentPoll();
    rememberOrder(data.order_id, sessionId);
    if (data.status === "CONFIRMED") {          // paid online and verified by Razorpay
      statusEl.textContent = "Order #" + data.order_id + " confirmed ✅ (paid online)";
      showBanner("✅ Order #" + data.order_id + " confirmed. Payment received.");
    } else if (data.status === "AWAITING_CASH") {
      statusEl.textContent = "Order #" + data.order_id + " submitted ⏳ Awaiting Cash Payment";
      showBanner("⏳ Order #" + data.order_id + " submitted. Please pay ₹" + data.cart.total +
                 " cash to the staff. Your order is confirmed only after the staff collect it.", "cash");
    } else {
      statusEl.textContent = "Order #" + data.order_id + " submitted ⏳ Staff are checking your UPI payment";
      showBanner("⏳ Order #" + data.order_id + " submitted. The staff are checking your UPI payment of ₹" +
                 data.cart.total + ". Your order is confirmed only after they see it.", "cash");
    }
    watchOrder(data.order_id, data.status);
    renderOrderBox(data.order_id, { status: data.status });
    chime(1);
    if (paymentSection) paymentSection.hidden = true;
    sessionId = newSessionId(); // the next order starts fresh
  } else {
    statusEl.textContent = "Done · understood by " + data.source;
  }
  return data;
}

function renderCart(cart) {
  cartEl.replaceChildren();
  cart.items.forEach((it) => {
    const li = document.createElement("li");
    li.textContent = it.quantity + " × " + it.name + " — ₹" + it.line_total + (it.notes ? " (" + it.notes + ")" : "");
    if (it.addons) {
      const a = document.createElement("div");
      a.className = "addon";
      a.textContent = "+ " + it.addons;
      li.appendChild(a);
    }
    cartEl.appendChild(li);
  });
  if (taxLine) {
    taxLine.hidden = !(cart.items.length && cart.tax);
    taxLine.textContent = "Subtotal ₹" + cart.subtotal + " + GST " + cart.gst_rate + "% ₹" + cart.tax;
  }
  totalEl.textContent = cart.items.length ? "Total: ₹" + cart.total : "Your order is empty";
}

// ---- Payment & UPI QR UI ----
function setPaymentMode(mode) {
  currentPaymentMode = mode;
  if (payUpiBtn) payUpiBtn.classList.toggle("active", mode === "upi");
  if (payCashBtn) payCashBtn.classList.toggle("active", mode === "cash");
  if (upiBox) upiBox.hidden = mode !== "upi";
  if (cashBox) cashBox.hidden = mode !== "cash";
}

if (payUpiBtn) {
  payUpiBtn.addEventListener("click", () => setPaymentMode("upi"));
}
if (payCashBtn) {
  payCashBtn.addEventListener("click", () => setPaymentMode("cash"));
}

function renderPayment(data) {
  if (!paymentSection) return;
  const hasItems = data.cart && data.cart.items && data.cart.items.length > 0;
  if (!hasItems || data.submitted) {
    paymentSection.hidden = true;
    return;
  }
  paymentSection.hidden = false;

  // For cash: show the amount to pay; no button — only kitchen can confirm.
  const cashHint = document.getElementById("cashHint");
  if (cashHint && data.cart && data.cart.total) {
    cashHint.textContent = "Please pay \u20b9" + data.cart.total + " cash to the staff. The kitchen will confirm your order after collecting payment.";
  }

  if (gatewayQr) gatewayQr.hidden = true;
  if (data.upi && data.upi.gateway) {
    // Razorpay one-time QR for the exact amount: confirmed automatically when the money arrives.
    if (qrcodeBox) qrcodeBox.replaceChildren();
    gatewayQr.src = data.upi.image_url;
    gatewayQr.hidden = false;
    if (upiDetails) upiDetails.textContent = "Amount: ₹" + data.upi.amount + " · confirmed automatically after payment";
    if (upiPayLink) upiPayLink.style.display = "none";
    startPaymentPoll(data.upi.order_id);
  } else if (data.upi && qrcodeBox) {
    stopPaymentPoll();
    qrcodeBox.replaceChildren();
    if (window.QRCode) {
      new QRCode(qrcodeBox, {
        text: data.upi.uri,
        width: 170,
        height: 170,
        colorDark: "#111111",
        colorLight: "#ffffff",
        correctLevel: QRCode.CorrectLevel.M,
      });
    }
    if (upiDetails) {
      upiDetails.textContent = "Amount: ₹" + data.upi.amount + " · UPI ID: " + data.upi.vpa;
    }
    if (upiPayLink) {
      upiPayLink.href = data.upi.uri;
      upiPayLink.style.display = /Android|iPhone|iPad/i.test(navigator.userAgent) ? "inline-block" : "none";
    }
  }

}

function startPaymentPoll(orderId) {
  if (paymentPoll && paymentPoll.orderId === orderId) return;
  stopPaymentPoll();
  let tries = 0;
  const timer = setInterval(async () => {
    if (++tries > 400) { stopPaymentPoll(); return; }          // about 20 minutes
    try {
      const r = await fetch("/api/orders/" + orderId + "/payment");
      const d = await r.json();
      if (d.paid) { stopPaymentPoll(); sendTurn("paid"); }
    } catch (e) { /* try again */ }
  }, 3000);
  paymentPoll = { orderId, timer };
}

function stopPaymentPoll() {
  if (paymentPoll) clearInterval(paymentPoll.timer);
  paymentPoll = null;
}

// ---- After the order is sent: cancel (before the staff confirm) and rating (after it is served) ----
function orderSessions() {
  try { return JSON.parse(localStorage.getItem("orderSessions") || "{}"); } catch (e) { return window._orderSessions || {}; }
}
function rememberOrder(id, sid) {
  const all = orderSessions();
  all[id] = sid;
  window._orderSessions = all;
  try { localStorage.setItem("orderSessions", JSON.stringify(all)); } catch (e) { /* ignore */ }
}

async function customerPost(id, path, body) {
  const res = await fetch("/api/orders/" + id + "/" + path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(Object.assign({ session_id: orderSessions()[id] }, body || {})),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Something went wrong");
  return data;
}

function renderOrderBox(id, d) {
  if (!orderBox || !orderSessions()[id]) return;
  const make = (tag, text, cls) => { const n = document.createElement(tag); if (text) n.textContent = text; if (cls) n.className = cls; return n; };
  orderBox.replaceChildren();
  orderBox.hidden = true;
  if (d.status === "AWAITING_CASH" || d.status === "AWAITING_UPI") {
    if (d.paid_online) return;
    const btn = make("button", "✖ Cancel order #" + id, "btn-cancel");
    btn.addEventListener("click", async () => {
      if (!confirm("Cancel order #" + id + "?")) return;
      try {
        await customerPost(id, "customer-cancel");
        showBanner("Order #" + id + " cancelled.", "bad");
        orderBox.hidden = true;
      } catch (e) { alert(e.message); }
    });
    orderBox.append(make("p", "Changed your mind? You can cancel until the staff confirm your payment."), btn);
    orderBox.hidden = false;
  } else if ((d.status === "READY" || d.status === "DELIVERED") && !d.rated) {
    let rating = 0;
    const stars = make("div", "", "stars");
    for (let i = 1; i <= 5; i++) {
      const b = make("button", "★");
      b.type = "button";
      b.setAttribute("aria-label", i + " stars");
      b.addEventListener("click", () => { rating = i; [...stars.children].forEach((c, j) => c.classList.toggle("on", j < i)); });
      stars.append(b);
    }
    const comment = make("textarea");
    comment.placeholder = "Anything to tell the kitchen? (optional)";
    comment.maxLength = 300;
    const send = make("button", "Send feedback", "btn-action");
    send.addEventListener("click", async () => {
      if (!rating) { alert("Tap the stars first"); return; }
      try {
        await customerPost(id, "feedback", { rating, comment: comment.value });
        orderBox.replaceChildren(make("p", "🙏 Thank you for your feedback!"));
      } catch (e) { alert(e.message); }
    });
    orderBox.append(make("p", "How was order #" + id + "?"), stars, comment, send);
    orderBox.hidden = false;
  }
}

// ---- The menu with photos: tap a dish to add one ----
async function loadCustomerMenu() {
  const list = document.getElementById("menuList");
  if (!list) return;
  try {
    const items = await (await fetch("/api/menu")).json();
    const nameKey = { "hi-IN": "name_hi", "kn-IN": "name_kn", "ta-IN": "name_ta", "te-IN": "name_te" };
    list.replaceChildren();
    let cat = null;
    for (const it of items) {
      if (it.category !== cat) {
        cat = it.category;
        const h = document.createElement("p");
        h.className = "menu-cat";
        h.textContent = cat;
        list.append(h);
      }
      const shown = it[nameKey[langSel.value]] || it.name_en;
      const b = document.createElement("button");
      b.type = "button";
      b.className = "dish";
      b.disabled = !it.available;
      const pic = it.image_url ? Object.assign(document.createElement("img"), { src: it.image_url, alt: "" })
                               : Object.assign(document.createElement("span"), { className: "ph", textContent: "🍽" });
      const mid = document.createElement("span");
      const nm = document.createElement("div");
      nm.className = "d-name";
      const dot = document.createElement("span");
      dot.className = "veg-dot " + (it.veg ? "veg" : "nonveg");
      nm.append(dot, shown + (it.available ? "" : " (sold out)"));
      const ds = document.createElement("div");
      ds.className = "d-desc";
      ds.textContent = it.description || "";
      mid.append(nm, ds);
      const pr = document.createElement("span");
      pr.className = "d-price";
      pr.textContent = "₹" + it.price;
      b.append(pic, mid, pr);
      b.addEventListener("click", () => sendTurn("one " + it.name_en).catch((e) => { statusEl.textContent = e.message; }));
      list.append(b);
    }
  } catch (e) { /* the menu list is optional */ }
}
loadCustomerMenu();
langSel.addEventListener("change", loadCustomerMenu);

if (confirmUpiBtn) {
  confirmUpiBtn.addEventListener("click", () => {
    sendTurn("confirm", "upi");
  });
}

if (submitCashBtn) {
  submitCashBtn.addEventListener("click", () => {
    sendTurn("confirm", "cash");
  });
}

typedForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = typedInput.value.trim();
  if (!text) return;
  transcriptEl.textContent = text;
  typedInput.value = "";
  try {
    await sendTurn(text);
  } catch (err) {
    statusEl.textContent = "Error: " + err.message;
  }
});
