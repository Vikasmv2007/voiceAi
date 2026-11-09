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
      if (["READY", "DELIVERED", "CANCELLED"].includes(d.status)) { clearInterval(timer); remember(false); }
    } catch (e) { /* offline for a moment: try again next time */ }
  }, 4000);
}

// If the customer closed the page and came back, keep watching their order.
try { JSON.parse(localStorage.getItem("watching") || "[]").forEach(watchOrder); } catch (e) { /* ignore */ }

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

  // Update QR scanner display if cart has items
  renderPayment(data);

  if (data.confirmed) {
    if (data.payment_mode === "cash") {
      statusEl.textContent = "Order #" + data.order_id + " submitted ⏳ Awaiting Cash Payment";
      showBanner("⏳ Order #" + data.order_id + " submitted. Please pay cash to staff. Kitchen will confirm upon payment.", "cash");
      watchOrder(data.order_id, "AWAITING_CASH");
    } else {
      statusEl.textContent = "Order #" + data.order_id + " confirmed ✅";
      showBanner("✅ Order #" + data.order_id + " confirmed (" + (data.payment_mode ? data.payment_mode.toUpperCase() : "PAID") + ")");
      watchOrder(data.order_id, "CONFIRMED");
    }
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
    cartEl.appendChild(li);
  });
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
  if (!hasItems || data.confirmed) {
    paymentSection.hidden = true;
    return;
  }
  paymentSection.hidden = false;

  // For cash: show the amount to pay; no button — only kitchen can confirm.
  const cashHint = document.getElementById("cashHint");
  if (cashHint && data.cart && data.cart.total) {
    cashHint.textContent = "Please pay \u20b9" + data.cart.total + " cash to the staff. The kitchen will confirm your order after collecting payment.";
  }

  if (data.upi && qrcodeBox) {
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

  // Everything is collected and paid: the order was read back and needs one
  // last explicit "yes" before it goes to the kitchen.
  const finalStep = data.awaiting === "final_confirm";
  if (confirmUpiBtn) confirmUpiBtn.textContent = finalStep ? "\u2705 Yes, Place My Order" : "\u2705 I Have Paid \u00b7 Place Order";
  if (submitCashBtn) submitCashBtn.textContent = finalStep ? "\u2705 Yes, Place My Order" : "\ud83d\udce8 Submit Order (Pay Cash to Staff)";
  if (qrcodeBox) qrcodeBox.hidden = finalStep;
  if (finalStep) {
    if (upiDetails) upiDetails.textContent = "Payment received \u2705 Confirm your order below.";
    if (upiPayLink) upiPayLink.style.display = "none";
    if (cashHint) cashHint.textContent = "Confirm your order below. The kitchen starts only after you say yes.";
  }
}

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
