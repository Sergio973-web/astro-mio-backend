from flask_cors import CORS
from flask import Flask, request, jsonify
from skyfield.api import load, wgs84
from datetime import datetime, timedelta
import pytz
import traceback
import sys

app = Flask(__name__)
CORS(app)

try:
    # Cargar efemérides DE421
    ephemeris = load('de421.bsp')
    earth = ephemeris['earth']
    moon = ephemeris['moon']
    sun = ephemeris['sun']
    ts = load.timescale()
    observer = earth + wgs84.latlon(-35.6581, -63.7575, elevation_m=135)
except Exception as e:
    print("❌ Error al cargar efemérides o inicializar observador:")
    traceback.print_exc()
    sys.exit(1)

SIDEREAL_PERIOD = 27.321661  # período sideral de la Luna

def angular_distance(ra1, dec1, ra2, dec2):
    from math import radians, degrees, acos, sin, cos
    ra1, dec1, ra2, dec2 = map(radians, [ra1, dec1, ra2, dec2])
    return degrees(acos(sin(dec1)*sin(dec2) + cos(dec1)*cos(dec2)*cos(ra1-ra2)))

@app.route('/api/luna', methods=['POST'])
def api_luna():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No se recibió un JSON válido'}), 400

        fecha_str = data.get('fecha')
        tolerancia_str = data.get('tolerancia', '10')
        sexo = data.get('sexo', '').lower()

        if not fecha_str:
            return jsonify({'error': 'Falta el parámetro "fecha"'}), 400

        try:
            tol_degrees = float(tolerancia_str)
        except ValueError:
            return jsonify({'error': 'Tolerancia debe ser un número'}), 400
        
        try:
            # Parsear fecha y ajustar a zona horaria Argentina
            argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
            fecha0 = datetime.fromisoformat(fecha_str)
            if fecha0.tzinfo is None:
                fecha0 = argentina_tz.localize(fecha0)
            fecha0 = fecha0.astimezone(pytz.utc)
        except ValueError:
            return jsonify({'error': 'Formato de fecha inválido. Usá ISO 8601, ej. "2023-05-11T00:00:00"'}), 400

        def calcular_posicion_luna(fecha):
            t = ts.utc(fecha.year, fecha.month, fecha.day, fecha.hour, fecha.minute)
            astrometric = observer.at(t).observe(moon).apparent()
            ra, dec, _ = astrometric.radec()
            return ra.hours * 15.0, dec.degrees

        ra0, dec0 = calcular_posicion_luna(fecha0)
        inicio = fecha0 - timedelta(days=30)
        fin = datetime.now(pytz.utc) + timedelta(days=365)

        k = 0
        orbita_encontrada = None

        while True:
            fecha_k = fecha0 + timedelta(days=SIDEREAL_PERIOD * k)
            if fecha_k > fin:
                break
            if fecha_k >= inicio:
                rak, deck = calcular_posicion_luna(fecha_k)
                if abs(ra0 - rak) < tol_degrees and abs(dec0 - deck) < tol_degrees:
                    orbita_encontrada = {
                        'fecha': fecha_k.strftime('%Y-%m-%d'),
                        'luna': {
                            'ascension_recta': f'{(rak / 15):.2f}h',
                            'declinacion': f'{deck:.2f}°'
                        },
                        'ra_luna': rak,
                        'dec_luna': deck
                    }
                    break
            k += 1

        if not orbita_encontrada:
            return jsonify({'orbitas': []})

        # Buscar fecha solar equivalente
        fecha_luna = datetime.strptime(orbita_encontrada['fecha'], '%Y-%m-%d').replace(tzinfo=pytz.utc)
        ra_luna = orbita_encontrada['ra_luna']
        dec_luna = orbita_encontrada['dec_luna']

        fecha_sol_mas_cercana = None
        diferencia_minima = float('inf')

        for i in range(366):
            fecha_busqueda = fecha_luna.replace(month=1, day=1) + timedelta(days=i)
            t_sol = ts.utc(fecha_busqueda.year, fecha_busqueda.month, fecha_busqueda.day)
            astrometric_sol = observer.at(t_sol).observe(sun).apparent()
            ra_sol, dec_sol, _ = astrometric_sol.radec()

            diff_ra = abs(ra_luna - ra_sol.hours * 15)
            diff_dec = abs(dec_luna - dec_sol.degrees)
            diferencia = (diff_ra * 2 + diff_dec * 2) * 0.5

            if diferencia < diferencia_minima and diff_ra < tol_degrees and diff_dec < tol_degrees:
                diferencia_minima = diferencia
                fecha_sol_mas_cercana = fecha_busqueda
                ra_sol_final = ra_sol.hours * 15
                dec_sol_final = dec_sol.degrees

        interpretacion = "Energía Complementaria Día de nacimiento" if sexo in ['masculino','femenino'] else ""

        orbita_encontrada['sol_equivalente'] = fecha_sol_mas_cercana.strftime('%Y-%m-%d') if fecha_sol_mas_cercana else "No encontrada"
        orbita_encontrada['interpretacion'] = interpretacion

        del orbita_encontrada['ra_luna']
        del orbita_encontrada['dec_luna']

        return jsonify({'orbitas': [orbita_encontrada]})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Servidor iniciado en http://127.0.0.1:5050")
    app.run(debug=True, port=5050)
