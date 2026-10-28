from app import create_app

app = create_app()

if __name__ == "__main__":
    # use_reloader=False: el reloader duplicaria el recorder en segundo plano
    app.run(debug=app.config["DEBUG"], use_reloader=False)
