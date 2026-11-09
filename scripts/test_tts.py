import os, requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GNANI_API_KEY")

r = requests.post(
    "https://api.vachana.ai/api/v1/tts/inference",
    headers={"Content-Type": "application/json", "X-API-Key-ID": API_KEY},
    json={
        "text": "नमस्ते, आप कैसे हैं?",
        "voice": "Nalini",
        "model": "timbre-v2.5",
        "language": "hi-IN",
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 48000, "num_channels": 1, "sample_width": 2,
            "encoding": "linear_pcm", "container": "wav",
        },
    },
    timeout=30,
)
print("Status:", r.status_code)
if r.ok:
    open("hello.wav", "wb").write(r.content)
    print("Saved hello.wav - double-click it to listen")
else:
    print(r.text)