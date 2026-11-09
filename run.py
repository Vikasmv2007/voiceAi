import socket
import sys

from app import config, create_app

app = create_app()


def port_in_use(port):
    """Windows lets a second server share a busy port, and the browser may keep reaching the OLD one
    (old pages). So refuse to start twice."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


if __name__ == "__main__":
    # Local testing only. On a server use:  gunicorn -w 2 -b 0.0.0.0:8000 run:app
    port = 5000
    if port_in_use(port):
        sys.exit(f"Port {port} is already in use: the app (or something else) is already running.\n"
                 "Close the other terminal running it, or run:  taskkill /F /IM python.exe   (Windows)\n"
                 "then start again with:  python run.py")
    app.run(debug=config.DEBUG, port=port)
