"""Aterrizajes inferidos: un avion sobre la pista no siempre avisa que esta en tierra.

Cerca de un aeropuerto, pegado al suelo y sin subir ni bajar, el avion esta en tierra aunque su transpondedor
no lo diga. "Pegado al suelo" se mide con la presion en superficie del aeropuerto (altura real sobre el terreno);
si no hay dato de presion se compara con la elevacion del aeropuerto con un margen amplio, porque la altitud
barometrica en pista puede diferir de la elevacion en cientos de metros segun el dia (hasta ~170 m en Bogota).
"""
from app.altitude import height_above_ground_m
from app.flight import mark_grounded

RADIUS_KM = 4.0  # distancia maxima al aeropuerto
PREFILTER_M = 300  # mas lejos de la elevacion del aeropuerto ni se consulta la presion
GROUND_AGL_M = 40  # altura sobre el terreno que se considera "en tierra"
FALLBACK_TOLERANCE_M = 100  # sin presion: diferencia admitida con la elevacion del aeropuerto
MAX_SPEED_MS = 100  # ~195 kt: mas rapido ya es despegue o aproximacion
MAX_VRATE_MS = 1.5  # en pista no sube ni baja (en final baja ~3-5 m/s)
LOST_AFTER_S = 25  # sin recibirse tanto tiempo, se asume que aterrizo si estaba a nivel de pista


def looks_grounded(flight, static, pressure_at=None, lost=False):
    """True si el vuelo parece estar en tierra.

    `pressure_at(lat, lon)` da la presion en superficie en hPa (o None). `lost`: el vuelo ya no se recibe, asi que
    no se le exige verse sin subir ni bajar.
    """
    if flight.get("gnd") or flight.get("alt") is None:
        return False
    airport = static.airport_near(flight["lat"], flight["lon"], RADIUS_KM)
    if airport is None:
        return False
    elevation, a_lat, a_lon = airport
    if abs(flight["alt"] - elevation) > PREFILTER_M:
        return False
    hpa = pressure_at(a_lat, a_lon) if pressure_at else None
    if hpa:
        at_ground = height_above_ground_m(flight["alt"], hpa) <= GROUND_AGL_M
    else:
        at_ground = abs(flight["alt"] - elevation) <= FALLBACK_TOLERANCE_M
    if not at_ground:
        return False
    if lost:
        return True
    speed, vrate = flight.get("spd"), flight.get("vr")
    return (speed is None or speed <= MAX_SPEED_MS) and (vrate is None or abs(vrate) <= MAX_VRATE_MS)


def apply_ground_inference(flights, static, pressure_at=None):
    for f in flights:
        if looks_grounded(f, static, pressure_at):
            mark_grounded(f)
