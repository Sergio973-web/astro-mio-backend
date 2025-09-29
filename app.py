from flask import Flask, request, jsonify
from flask_cors import CORS
from skyfield.api import load, wgs84
from datetime import datetime, timedelta
import pytz
import os
from math import radians, degrees, acos, sin, cos

app = Flask(__name__)
CORS(app)

# Cargar efemérides
ephemeris = load('de421.bsp')
earth = ephemeris['earth']
moon = ephemeris['moon']
sun = ephemeris['sun']
ts = load.timescale()
observer = earth + wgs84.latlon(-35.6581, -63.7575, elevation_m=135)

SIDEREAL_PERIOD = 27.321661  # días

def diff_angle(a, b):
    """Diferencia mínima entre dos ángulos en grados"""
    d = abs(a - b) % 360
    return min(d, 360 - d)

def angular_distance(ra1, dec1, ra2, dec2):
    """Devuelve la distancia angular en grados entre dos coordenadas RA/DEC"""
    ra1, dec1, ra2, dec2 = map(radians, [ra1, dec1, ra2, dec2])
    return degrees(acos(sin(dec1)*sin(dec2) + cos(dec1)*cos(dec2)*cos(ra1-ra2)))

@app.route('/')
def home():
    return 'Astro-Mio backend funcionando 🚀'

@app.route('/api/luna', methods=['POST'])
def api_luna():
    try:
        data = request.get_json()
        fecha_str = data.get('fecha')
        tolerancia = float(data.get('tolerancia', 10))
        sexo = data.get('sexo', '').lower()

        argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
        # Intentar parsear fecha en ISO, sino con formato DD/MM/YYYY
        try:
            fecha0 = datetime.fromisoformat(fecha_str)
        except:
            fecha0 = datetime.strptime(fecha_str, '%d/%m/%Y %H:%M')
        if fecha0.tzinfo is None:
            fecha0 = argentina_tz.localize(fecha0)
        fecha0 = fecha0.astimezone(pytz.utc)

        def calcular_posicion_luna(fecha):
            t = ts.utc(fecha.year, fecha.month, fecha.day, fecha.hour, fecha.minute, fecha.second)
            astrometric = observer.at(t).observe(moon).apparent()
            ra, dec, _ = astrometric.radec()
            return ra.hours * 15.0, dec.degrees  # RA en grados

        def calcular_posicion_sol(fecha):
            t = ts.utc(fecha.year, fecha.month, fecha.day)
            astrometric = observer.at(t).observe(sun).apparent()
            ra, dec, _ = astrometric.radec()
            return ra.hours * 15.0, dec.degrees

        # Posición de la Luna en la fecha de nacimiento
        ra_luna, dec_luna = calcular_posicion_luna(fecha0)

        # Buscar la fecha del Sol cuya posición se alinea mejor con la Luna
        # Iterar +/- 365 días (1 año) o más si se quiere
        dias_busqueda = 365
        min_diff = float('inf')
        fecha_sol_equivalente = None

        for delta in range(-dias_busqueda, dias_busqueda + 1):
            f = fecha0 + timedelta(days=delta)
            ra_sol, dec_sol = calcular_posicion_sol(f)
            diff = angular_distance(ra_luna, dec_luna, ra_sol, dec_sol)
            if diff < min_diff:
                min_diff = diff
                fecha_sol_equivalente = f

        resultado = {
            'fecha_luna': fecha0.strftime('%Y-%m-%d %H:%M'),
            'sol_equivalente': fecha_sol_equivalente.strftime('%Y-%m-%d') if fecha_sol_equivalente else None,
            'interpretacion': "Energía Complementaria Día de nacimiento" if sexo else ""
        }

        return jsonify({'orbitas': [resultado]})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port)
