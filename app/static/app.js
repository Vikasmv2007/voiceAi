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

let currentPaymentMode = null;   // chosen by the customer (button or voice); the agent asks "UPI or cash?"
let qrInstance = null;
const gatewayQr = document.getElementById("gatewayQr");
const taxLine = document.getElementById("taxLine");
const orderBox = document.getElementById("orderBox");
let paymentPoll = null;          // Razorpay QR on screen: ask the server whether the money arrived

// ---- Mic button: icon + state (the status line under it says what is happening) ----
function setMic(state) {
  const icon = { idle: "🎤", listen: "🎤", hear: "🎙️", think: "⏳", speak: "🔊" }[state] || "🎤";
  const label = state === "idle" || !state ? "Tap to start talking" : "Tap to stop the conversation";
  micBtn.replaceChildren(Object.assign(document.createElement("span"), { className: "mic-icon", textContent: icon }));
  micBtn.className = "mic" + (state && state !== "idle" ? " live " + state : "");
  micBtn.setAttribute("aria-label", label);
  micBtn.title = label;
}

// ---- Phones: the cart is a slide-up sheet opened from the bottom bar ----
const cartSheet = document.getElementById("cartSheet");
const cartBar = document.getElementById("cartBar");
const sheetBackdrop = document.getElementById("sheetBackdrop");
const isPhone = () => window.matchMedia("(max-width: 900px)").matches;
function openSheet() {
  if (!cartSheet || !isPhone()) return;
  cartSheet.classList.add("open");
  if (sheetBackdrop) sheetBackdrop.hidden = false;
  if (cartBar) cartBar.hidden = true;
}
function closeSheet() {
  if (!cartSheet) return;
  cartSheet.classList.remove("open");
  if (sheetBackdrop) sheetBackdrop.hidden = true;
  updateCartBar();
}
let cartItemsCount = 0, cartTotalNow = 0;
function updateCartBar() {
  if (!cartBar) return;
  const open = cartSheet && cartSheet.classList.contains("open");
  cartBar.hidden = open || (cartItemsCount === 0 && !(orderBox && !orderBox.hidden));
  document.getElementById("cartCount").textContent = cartItemsCount ? cartItemsCount + (cartItemsCount === 1 ? " item" : " items") : "Your order";
  document.getElementById("cartBarTotal").textContent = cartItemsCount ? "₹" + cartTotalNow : "View status";
}
if (cartBar) cartBar.addEventListener("click", openSheet);
if (sheetBackdrop) sheetBackdrop.addEventListener("click", closeSheet);
const sheetCloseBtn = document.getElementById("sheetClose");
if (sheetCloseBtn) sheetCloseBtn.addEventListener("click", closeSheet);
window.addEventListener("resize", () => { if (!isPhone()) closeSheet(); });

function newSessionId() {
  return (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()) + Math.random();
}
let sessionId = newSessionId();

// Name and phone are NOT remembered: the agent asks every new customer (a shared table device must
// never reuse the previous customer's name). Forget anything an older version saved.
try { localStorage.removeItem("custName"); localStorage.removeItem("custPhone"); } catch (e) { /* ignore */ }

// Remembered in this browser so "same as last time" works. A QR code on the table can open the page as ?table=5.
let customerId;
try {
  customerId = localStorage.getItem("customerId");
  if (!customerId) { customerId = newSessionId(); localStorage.setItem("customerId", customerId); }
} catch (e) { customerId = newSessionId(); }
const tableFromUrl = new URLSearchParams(location.search).get("table");
if (tableFromUrl && /^[1-9][0-9]?$/.test(tableFromUrl) && document.getElementById("whereLine")) {
  document.getElementById("whereLine").textContent = "🍽 Table " + tableFromUrl + " · Order by voice or tap to add";
}
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

// Banner colours live in style.css (they follow light / dark mode).

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
      updateCartBar();
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

// ---- Step 5: the agent speaks (through the page's audio engine, so it also works on iPhones) ----
const speakBox = document.getElementById("speakBox");
let currentVoice = null;          // { source, done } while the agent is talking

function stopSpeaking() {
  if (currentVoice) {
    try { currentVoice.source.stop(); } catch (e) { /* already stopped */ }
    currentVoice.done();
    currentVoice = null;
  }
}

// Resolves when the agent has finished talking (or straight away if speech is off / failed).
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
    unlockAudio();
    const audio = await audioCtx.decodeAudioData(await res.arrayBuffer());
    stopSpeaking();
    await new Promise((resolve) => {
      const source = audioCtx.createBufferSource();
      source.buffer = audio;
      source.connect(audioCtx.destination);
      const voice = { source, done: resolve };
      source.onended = () => { if (currentVoice === voice) currentVoice = null; resolve(); };
      currentVoice = voice;
      source.start();
    });
  } catch (err) {
    statusEl.textContent = "Voice problem: " + err.message + " (the text reply still works)";
  }
}

// ---- Hands-free conversation, like talking to a waiter ----
// Tap the mic once. The agent listens, notices when you stop talking, replies out loud and
// listens again by itself. Talk over it to interrupt. Tap the mic again to stop.
const VAD = {
  frameMs: 0,              // set from the sample rate
  startFrames: 3,          // ~130 ms of voice = you started talking
  silenceMs: 900,          // this much quiet after speaking = you finished
  minSpeechMs: 350,        // shorter sounds (a cough, a click) are ignored
  maxSpeechMs: 20000,      // Gnani Prisma takes up to ~30 s per clip
  idleMs: 25000,           // nobody talks for this long: the agent stops listening
  preRollMs: 400,          // keep the start of the first word
  bargeMs: 350,            // talk this long over the agent to interrupt it
};
const convo = {
  on: false, state: "off", stream: null, source: null, proc: null, sink: null,
  noise: 0.004, loudFrames: 0, quietMs: 0, speechMs: 0, idleMs: 0, bargeLoudMs: 0, bargeQuietMs: 0,
  preRoll: [], frames: [], errors: 0,
};

micBtn.addEventListener("click", () => (convo.on ? endConversation("Stopped. Tap the mic to talk again.") : startConversation()));

async function startConversation() {
  unlockAudio();
  stopSpeaking();
  try {
    convo.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    });
  } catch (err) {
    statusEl.textContent = "Microphone blocked. Allow it in the browser address bar.";
    return;
  }
  convo.on = true;
  convo.errors = 0;
  convo.source = audioCtx.createMediaStreamSource(convo.stream);
  convo.proc = audioCtx.createScriptProcessor(2048, 1, 1);
  convo.sink = audioCtx.createGain();
  convo.sink.gain.value = 0;                       // the processor must be connected, but stays silent
  convo.source.connect(convo.proc);
  convo.proc.connect(convo.sink).connect(audioCtx.destination);
  VAD.frameMs = (2048 / audioCtx.sampleRate) * 1000;
  convo.proc.onaudioprocess = (e) => onAudioFrame(e.inputBuffer.getChannelData(0));
  if (greetedSession !== sessionId) {
    greetedSession = sessionId;
    greetFirst();                                  // "Hello! Welcome. May I know your name please?"
  } else {
    listen();
  }
}

// Like a waiter: the agent speaks first and asks the customer's name, then listens.
let greetedSession = null;
async function greetFirst() {
  setState("think");
  try {
    const result = await sendTurn("hello", undefined, true);
    if (!convo.on) return;
    setState("speak");
    await result.speech;
    if (convo.on && convo.state === "speak") listen();
  } catch (err) {
    statusEl.textContent = "Error: " + err.message;
    if (convo.on) listen();
  }
}

function endConversation(message) {
  convo.on = false;
  convo.state = "off";
  if (convo.proc) { convo.proc.onaudioprocess = null; convo.proc.disconnect(); }
  if (convo.source) convo.source.disconnect();
  if (convo.sink) convo.sink.disconnect();
  if (convo.stream) convo.stream.getTracks().forEach((t) => t.stop());
  convo.proc = convo.source = convo.sink = convo.stream = null;
  micBtn.style.removeProperty("--level");
  setMic("idle");
  micBtn.disabled = false;
  if (message) statusEl.textContent = message;
}

function setState(state) {
  convo.state = state;
  setMic(state);
  statusEl.textContent = {
    listen: "Listening… just speak",
    hear: "Hearing you…",
    think: "Got it, one moment…",
    speak: "Speaking… talk anytime to interrupt",
  }[state] || statusEl.textContent;
}

function listen() {
  if (!convo.on) return;
  convo.frames = [];
  convo.bargeLoudMs = convo.bargeQuietMs = 0;
  convo.loudFrames = convo.quietMs = convo.speechMs = convo.idleMs = 0;
  setState("listen");
}

function rms(buf) {
  let sum = 0;
  for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
  return Math.sqrt(sum / buf.length);
}

function onAudioFrame(input) {
  if (!convo.on) return;
  const frame = new Float32Array(input);           // the browser reuses its buffer
  const level = rms(frame);
  micBtn.style.setProperty("--level", Math.min(1, level * 12).toFixed(2));

  if (convo.state === "speak") {
    // Interrupting the agent needs a clearly louder voice than its own sound coming back from the speaker.
    // Speech dips between syllables, so only a real pause (~250 ms) resets the count.
    const bargeLevel = Math.max(0.06, convo.noise * 8);
    if (level > bargeLevel) {
      convo.bargeLoudMs += VAD.frameMs;
      convo.bargeQuietMs = 0;
    } else if ((convo.bargeQuietMs += VAD.frameMs) > 250) {
      convo.bargeLoudMs = 0;
    }
    keepPreRoll(frame);
    if (convo.bargeLoudMs >= VAD.bargeMs) {
      convo.bargeLoudMs = 0;
      stopSpeaking();                               // like a waiter: stop and listen
      convo.frames = convo.preRoll.slice();
      convo.loudFrames = VAD.startFrames;
      convo.quietMs = 0;
      convo.speechMs = VAD.bargeMs;
      setState("hear");
    }
    return;
  }

  if (convo.state === "listen") {
    const threshold = Math.max(0.012, convo.noise * 3);
    if (level > threshold) {
      convo.loudFrames++;
      keepPreRoll(frame);
      if (convo.loudFrames >= VAD.startFrames) {
        convo.frames = convo.preRoll.slice();       // include the start of the first word
        convo.speechMs = convo.loudFrames * VAD.frameMs;
        convo.quietMs = 0;
        setState("hear");
      }
    } else {
      convo.loudFrames = 0;
      convo.noise = convo.noise * 0.95 + level * 0.05;   // learn the room's background noise
      keepPreRoll(frame);
      convo.idleMs += VAD.frameMs;
      if (convo.idleMs >= VAD.idleMs) endConversation("I stopped listening. Tap the mic when you are ready.");
    }
    return;
  }

  if (convo.state === "hear") {
    convo.frames.push(frame);
    convo.speechMs += VAD.frameMs;
    const threshold = Math.max(0.010, convo.noise * 2.5);
    convo.quietMs = level > threshold ? 0 : convo.quietMs + VAD.frameMs;
    if (convo.quietMs >= VAD.silenceMs || convo.speechMs >= VAD.maxSpeechMs) {
      const voiced = convo.speechMs - convo.quietMs;
      if (voiced < VAD.minSpeechMs) { listen(); return; }   // just a noise
      finishUtterance(convo.frames);
    }
  }
}

function keepPreRoll(frame) {
  convo.preRoll.push(frame);
  const keep = Math.ceil(VAD.preRollMs / VAD.frameMs);
  while (convo.preRoll.length > keep) convo.preRoll.shift();
}

async function finishUtterance(frames) {
  setState("think");
  try {
    const wav = pcmToWav16k(frames, audioCtx.sampleRate);
    const form = new FormData();
    form.append("audio", wav, "speech.wav");
    form.append("language", langSel.value);
    const res = await fetch("/api/stt", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Something went wrong");
    if (!convo.on) return;
    if (!data.transcript) { listen(); return; }                // only noise: keep listening quietly
    convo.errors = 0;
    transcriptEl.textContent = data.transcript;
    const result = await sendTurn(data.transcript, undefined, true);
    if (!convo.on) return;
    setState("speak");
    await result.speech;                                     // let the agent finish (or be interrupted)
    if (!convo.on || convo.state !== "speak") return;        // interrupted: already hearing the customer
    if (result.data && result.data.submitted) {
      endConversation("Order sent ✅ Tap the mic if you need anything else.");
      return;
    }
    listen();
  } catch (err) {
    convo.errors++;
    statusEl.textContent = "Error: " + err.message;
    if (convo.errors >= 2) { endConversation("Error: " + err.message + ". Tap the mic to try again."); return; }
    setTimeout(listen, 800);
  }
}

// Raw microphone samples -> 16 kHz mono 16-bit WAV (what Gnani Prisma expects).
function pcmToWav16k(frames, rate) {
  const total = frames.reduce((n, f) => n + f.length, 0);
  const input = new Float32Array(total);
  let pos = 0;
  for (const f of frames) { input.set(f, pos); pos += f.length; }
  const ratio = rate / 16000;
  const outLen = Math.floor(total / ratio);
  const view = new DataView(new ArrayBuffer(44 + outLen * 2));
  const text = (o, s) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };
  text(0, "RIFF"); view.setUint32(4, 36 + outLen * 2, true); text(8, "WAVE"); text(12, "fmt ");
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, 16000, true); view.setUint32(28, 32000, true); view.setUint16(32, 2, true);
  view.setUint16(34, 16, true); text(36, "data"); view.setUint32(40, outLen * 2, true);
  for (let i = 0; i < outLen; i++) {
    // average the samples that fall into this output sample (simple low-pass + downsample)
    const start = Math.floor(i * ratio), end = Math.min(total, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += input[j];
    const s = Math.max(-1, Math.min(1, sum / Math.max(1, end - start)));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([view], { type: "audio/wav" });
}

// ---- Step 4: talk to the order brain ----
// Returns { data, speech }: speech resolves when the agent has finished saying the reply.
async function sendTurn(text, overridePayment, fromConversation) {
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
  // Typed or tapped while the hands-free conversation is listening: the agent answers, then keeps listening.
  if (convo.on && !fromConversation) setState("speak");
  const speech = speak(data.reply);

  // Sync profile details back from order brain
  if (data.customer_name && custNameInput && !custNameInput.value) {
    custNameInput.value = data.customer_name;
  }
  if (data.customer_phone && custPhoneInput && !custPhoneInput.value) {
    custPhoneInput.value = data.customer_phone;
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
  // On phones the QR / payment and the cancel button live in the cart sheet: bring it up when needed.
  if (data.submitted || ["upi_confirm", "payment", "phone"].includes(data.awaiting)) openSheet();
  if (data.awaiting === "phone" && custPhoneInput) {
    const box = custPhoneInput.closest("details");
    if (box) box.open = true;                      // show the phone box so they can type the number
    if (!custPhoneInput.value) custPhoneInput.focus({ preventScroll: false });
  }

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
    updateCartBar();
    chime(1);
    if (paymentSection) paymentSection.hidden = true;
    sessionId = newSessionId(); // the next order starts fresh
    // The next customer is asked their own name, phone and payment again.
    if (custNameInput) custNameInput.value = "";
    if (custPhoneInput) custPhoneInput.value = "";
    currentPaymentMode = null;
  } else if (!convo.on) {
    statusEl.textContent = "Done · understood by " + data.source;
  }
  if (convo.on && !fromConversation) {
    // Typed / tapped during the hands-free conversation: once the agent has answered, listen again.
    speech.then(() => {
      if (!convo.on || convo.state !== "speak") return;
      if (data.submitted) endConversation("Order sent ✅ Tap the mic if you need anything else.");
      else listen();
    });
  }
  return { data, speech };
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
  cartItemsCount = cart.items.reduce((n, it) => n + it.quantity, 0);
  cartTotalNow = cart.total;
  updateCartBar();
  if (cart.items.length) {
    const label = document.createElement("span");
    label.textContent = "Total";
    const amount = document.createElement("span");
    amount.textContent = "₹" + cart.total;
    totalEl.replaceChildren(label, amount);
  } else {
    totalEl.textContent = "Your order is empty";
  }
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

// ---- The menu: food-app style cards; tap a dish to add one ----
const DISH_EMOJI = [[/dosa|dose|crepe/i, "🥞"], [/idli|idly/i, "🍚"], [/vada|vade/i, "🍩"], [/coffee|kaapi/i, "☕"],
                    [/chai|tea/i, "🍵"], [/pongal|khichdi/i, "🍲"], [/upma|uppit/i, "🥣"], [/kesari|halwa|sweet|payasam/i, "🍮"],
                    [/juice|shake|lassi/i, "🥤"], [/biryani|bath|rice|meal|thali/i, "🍛"], [/roll|wrap/i, "🌯"],
                    [/paneer|curry/i, "🍛"], [/chicken|mutton|egg|fish/i, "🍗"]];
function dishEmoji(item) {
  const hit = DISH_EMOJI.find(([re]) => re.test(item.name_en + " " + item.category));
  return hit ? hit[1] : "🍽️";
}
function node(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

async function loadCustomerMenu() {
  const list = document.getElementById("menuList");
  const chips = document.getElementById("catChips");
  if (!list) return;
  try {
    const items = await (await fetch("/api/menu")).json();
    const nameKey = { "hi-IN": "name_hi", "kn-IN": "name_kn", "ta-IN": "name_ta", "te-IN": "name_te" };
    const cats = [...new Set(items.map((it) => it.category))];
    list.replaceChildren();
    if (chips) chips.replaceChildren();
    cats.forEach((cat, ci) => {
      const inCat = items.filter((it) => it.category === cat);
      const anchor = "cat-" + ci;
      const head = node("h3", "menu-cat", cat);
      head.id = anchor;
      head.append(node("small", null, inCat.length + (inCat.length === 1 ? " item" : " items")));
      list.append(head);
      if (chips) {
        const chip = node("button", "cat-chip" + (ci === 0 ? " active" : ""), cat);
        chip.type = "button";
        chip.addEventListener("click", () => {
          chips.querySelectorAll(".cat-chip").forEach((c) => c.classList.toggle("active", c === chip));
          document.getElementById(anchor).scrollIntoView({ behavior: "smooth", block: "start" });
        });
        chips.append(chip);
      }
      for (const it of inCat) {
        const shown = it[nameKey[langSel.value]] || it.name_en;
        const card = node("button", "dish");
        card.type = "button";
        card.disabled = !it.available;
        card.setAttribute("aria-label", "Add " + it.name_en + ", ₹" + it.price);
        const photo = node("div", "d-photo c" + (ci % 5));
        if (it.image_url) {
          const img = node("img");
          img.src = it.image_url;
          img.alt = "";
          img.loading = "lazy";
          img.onerror = () => { img.remove(); photo.prepend(dishEmoji(it)); };
          photo.append(img);
        } else {
          photo.append(dishEmoji(it));
        }
        if (!it.available) photo.append(node("span", "sold-tag", "Sold out"));
        if (it.available) photo.append(node("span", "d-add on-photo", "ADD"));
        const body = node("div", "d-body");
        const name = node("div", "d-name");
        name.append(node("span", "veg-dot " + (it.veg ? "veg" : "nonveg")), shown);
        body.append(name, node("div", "d-desc", it.description || ""));
        const foot = node("div", "d-foot");
        foot.append(node("span", "d-price", "₹" + it.price), node("span", "d-add in-foot", it.available ? "ADD" : "Sold out"));
        body.append(foot);
        card.append(photo, body);
        card.addEventListener("click", () => {
          card.classList.remove("added"); void card.offsetWidth; card.classList.add("added");
          transcriptEl.textContent = "one " + shown;
          sendTurn("one " + it.name_en).catch((e) => { statusEl.textContent = e.message; });
        });
        list.append(card);
      }
    });
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
