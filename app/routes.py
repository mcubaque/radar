from flask import Flask, render_template
from flask import jsonify
from opensky_api import OpenSkyApi
from app import app
import mysql.connector
from config import DATABASE_CONFIG

def get_db():
    return mysql.connector.connect(**DATABASE_CONFIG)

# Ruta Index
@app.route('/')
def index():
    return render_template('index.html')



# Ruta para obtener datos de tráfico aéreo
@app.route('/get_traffic_data')
def get_traffic_data():
    # Asumo que min_latitude, max_latitude, min_longitude, max_longitude están definidos
    api = OpenSkyApi()

       # Define las coordenadas de la caja delimitadora para la región que te interesa
    # Aquí, uso coordenadas aproximadas de Nueva York como ejemplo
    min_latitude = 40.4774
    max_latitude = 40.9176
    min_longitude = -74.2591
    max_longitude = -73.7004

    # Obtén datos de tráfico aéreo dentro de la caja delimitadora utilizando el método get_states
    states = api.get_states(bbox=(min_latitude, max_latitude, min_longitude, max_longitude))

    # Verifica si states no es None antes de intentar acceder a la propiedad states
    if states:
        # Formatea los datos en el formato que deseas (por ejemplo, solo callsign, latitude y longitude)
        traffic_data = [
            {
                "callsign": state.callsign, 
                "latitude": state.latitude, 
                "longitude": state.longitude,
                "altitude": state.baro_altitude,
                "velocity": state.velocity}
            for state in states.states  # Accede a la propiedad states de OpenSkyStates
        ]

        # Guarda los datos en la base de datos
        save_to_database(traffic_data)

        # Devuelve los datos en formato JSON
        return jsonify(traffic_data)

    # Si states es None, devuelve un JSON vacío o un mensaje de error según sea necesario
    return jsonify([])

def save_to_database(traffic_data):
    # Establece la conexión con la base de datos
    connection = get_db()

    # Crea un cursor para ejecutar consultas
    cursor = connection.cursor()

    # Itera sobre los datos y ejecuta una consulta para insertar cada registro
    for flight in traffic_data:
        query = "INSERT INTO traffic_data (callsign, latitude, longitude, velocidad, altitud) VALUES (%s, %s, %s, %s, %s)"
        values = (flight['callsign'], flight['latitude'], flight['longitude'], flight['velocity'], flight['altitude'])
        cursor.execute(query, values)
    # Realiza el commit para confirmar los cambios en la base de datos
    connection.commit()

    print("Datos guardados en la base de datos")

    # Cierra la conexión
    cursor.close()
    connection.close()
