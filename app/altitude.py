"""Altitud barometrica y altura sobre el terreno.

Los aviones reportan altitud de presion (referida a 1013,25 hPa, "sobre el nivel del mar" en la atmosfera estandar).
La altura real sobre el suelo se obtiene restando la altitud de presion del propio suelo, que sale de la presion
medida en superficie debajo del avion: no depende de ajustes QNH ni de la forma del geoide.
"""

SEA_LEVEL_HPA = 1013.25


def pressure_altitude_m(hpa):
    """Altitud (m) que corresponde a una presion en la atmosfera estandar."""
    return 44330.77 * (1 - (hpa / SEA_LEVEL_HPA) ** 0.190263)


def height_above_ground_m(baro_alt_m, surface_hpa):
    return max(0.0, baro_alt_m - pressure_altitude_m(surface_hpa))
