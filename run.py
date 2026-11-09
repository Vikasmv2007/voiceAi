from app import config, create_app

app = create_app()

if __name__ == "__main__":
    # Local testing only. On a server use:  gunicorn -w 2 -b 0.0.0.0:8000 run:app
    app.run(debug=config.DEBUG)
