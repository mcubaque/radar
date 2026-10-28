from app import create_app

app = create_app()

if __name__ == "__main__":
    # Solo desarrollo local. En produccion: gunicorn (ver Dockerfile).
    app.run(debug=app.config["DEBUG"], use_reloader=False, threaded=True)
