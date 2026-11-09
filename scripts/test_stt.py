import os, sys, requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GNANI_API_KEY")
path = sys.argv[1]
lang = sys.argv[2] if len(sys.argv) > 2 else "hi-IN"

with open(path, "rb") as f:
    r = requests.post(
        "https://api.vachana.ai/stt/v3",
        headers={"X-API-Key-ID": API_KEY},
        files={"audio_file": (os.path.basename(path), f)},
        data={"language_code": lang},
        timeout=60,
    )
print("Status:", r.status_code)
print(r.text)