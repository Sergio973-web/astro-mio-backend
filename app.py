from flask import Flask, request, jsonify
from flask_cors import CORS
from skyfield.api import load, wgs84
from datetime import datetime, timedelta
import pytz
import os

app = Flask(__name__)
CORS(app)

# Cargar efemérides (se descargará automáticamente si no existe localmente)
ephemeris = load('de421.bsp')

earth = ephemeris['earth']
moon = ephemeris['moon']
sun = ephemeris['sun']
ts = load.timescale()
observer = earth + wgs84.latlon(-35.6581, -63.7575, elevation_m=135)

SIDEREAL_PERIOD = 27.321661

@app.route('/api/luna', methods=['POST'])
def api_luna():
    try:
        data = request.get_json()
        fecha_str = data.get('fecha')
        tolerancia = float(data.get('tolerancia', '10'))
        sexo = data.get('sexo', '').lower()

        argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
        fecha0 = datetime.fromisoformat(fecha_str)
        if fecha0.tzinfo is None:
            fecha0 = argentina_tz.localize(fecha0)
        fecha0 = fecha0.astimezone(pytz.utc)

        def calcular_posicion_luna(fecha):
            t = ts.utc(fecha.year, fecha.month, fecha.day, fecha.hour, fecha.minute)
            astrometric = observer.at(t).observe(moon).apparent()
            ra, dec, _ = astrometric.radec()
            return ra.hours * 15.0, dec.degrees

        ra0, dec0 = calcular_posicion_luna(fecha0)
        orbitas = []
        fin = fecha0 + timedelta(days=365)

        k = 0
        while True:
            fecha_k = fecha0 + timedelta(days=SIDEREAL_PERIOD * k)
            if fecha_k > fin:
                break
            rak, deck = calcular_posicion_luna(fecha_k)
            if abs(ra0 - rak) < tolerancia and abs(dec0 - deck) < tolerancia:
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

            # Buscar fecha del Sol más cercana
            fecha_sol = None
            min_diff = float('inf')

            for i in range(366):
                fecha_busqueda = fecha_luna.replace(month=1, day=1) + timedelta(days=i)
                t_sol = ts.utc(fecha_busqueda.year, fecha_busqueda.month, fecha_busqueda.day)
                astrometric_sol = observer.at(t_sol).observe(sun).apparent()
                ra_sol, dec_sol, _ = astrometric_sol.radec()
                diff = abs(ra_luna - ra_sol.hours * 15) + abs(dec_luna - dec_sol.degrees)
                if diff < min_diff:
                    min_diff = diff
                    fecha_sol = fecha_busqueda

            orbita['sol_equivalente'] = fecha_sol.strftime('%Y-%m-%d') if fecha_sol else None
            orbita['interpretacion'] = "Energía Complementaria Día de nacimiento" if sexo else ""

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
