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
            fecha0 = datetime.strptime(fecha_str, '%d/%m/%Y')
        if fecha0.tzinfo is None:
            fecha0 = argentina_tz.localize(fecha0)
        fecha0 = fecha0.astimezone(pytz.utc)
        # Tomar solo la fecha, ignorar hora para coincidencias
        fecha0 = fecha0.replace(hour=0, minute=0, second=0, microsecond=0)

        def calcular_posicion_luna(fecha):
            t = ts.utc(fecha.year, fecha.month, fecha.day, fecha.hour, fecha.minute, fecha.second)
            astrometric = observer.at(t).observe(moon).apparent()
            ra, dec, _ = astrometric.radec()
            return ra.hours * 15.0, dec.degrees  # RA en grados

        ra0, dec0 = calcular_posicion_luna(fecha0)
        orbitas = []
        fin = fecha0 + timedelta(days=365)

        # Buscar siguiente posición similar de la Luna (aprox. cada periodo sideral)
        k = 0
        while True:
            fecha_k = fecha0 + timedelta(days=SIDEREAL_PERIOD * k)
            if fecha_k > fin:
                break
            rak, deck = calcular_posicion_luna(fecha_k)
            if diff_angle(ra0, rak) < tolerancia and abs(dec0 - deck) < tolerancia:
                orbitas.append({
                    'fecha': fecha_k.strftime('%Y-%m-%d'),
                    'luna': {
                        'ascension_recta': f'{rak / 15:.2f}h',
                        'declinacion': f'{deck:.2f}°'
                    },
                    'ra_luna': rak,
                    'dec_luna': deck
                })
                break  # Solo una coincidencia
            k += 1

        if orbitas:
            orbita = orbitas[0]
            ra_luna = orbita['ra_luna']
            dec_luna = orbita['dec_luna']
            fecha_luna = datetime.strptime(orbita['fecha'], '%Y-%m-%d').replace(tzinfo=pytz.utc)

            # Buscar fecha del Sol más cercana a la posición de la Luna
            fecha_inicio = fecha_luna - timedelta(days=182)  # medio año antes
            fecha_fin = fecha_luna + timedelta(days=182)
            min_diff = float('inf')
            fecha_sol = None

            for i in range((fecha_fin - fecha_inicio).days + 1):
                f = fecha_inicio + timedelta(days=i)
                t_sol = ts.utc(f.year, f.month, f.day)
                ra_sol, dec_sol, _ = observer.at(t_sol).observe(sun).apparent().radec()
                diff = angular_distance(ra_luna, dec_luna, ra_sol.hours * 15, dec_sol.degrees)
                if diff < min_diff:
                    min_diff = diff
                    fecha_sol = f

            orbita['sol_equivalente'] = fecha_sol.strftime('%Y-%m-%d') if fecha_sol else None
            orbita['interpretacion'] = "Energía Complementaria Día de nacimiento" if sexo else ""

            # Limpiar datos internos
            del orbita['ra_luna']
            del orbita['dec_luna']

            return jsonify({'orbitas': [orbita]})
        else:
            return jsonify({'orbitas': []})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port)
