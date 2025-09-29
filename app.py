from flask import Flask, request, jsonify
from flask_cors import CORS
from skyfield.api import load, wgs84
from datetime import datetime, timedelta
import pytz
import traceback

app = Flask(__name__)
CORS(app)

# Cargar efemérides Skyfield
ephemeris = load('de421.bsp')
earth = ephemeris['earth']
moon = ephemeris['moon']
sun = ephemeris['sun']
ts = load.timescale()
observer = earth + wgs84.latlon(-35.6581, -63.7575, elevation_m=135)

SIDEREAL_PERIOD = 27.321661  # días

def angular_distance(ra1, dec1, ra2, dec2):
    """Distancia angular en grados entre dos coordenadas RA/DEC"""
    from math import radians, degrees, acos, sin, cos
    ra1, dec1, ra2, dec2 = map(radians, [ra1, dec1, ra2, dec2])
    return degrees(acos(sin(dec1)*sin(dec2) + cos(dec1)*cos(dec2)*cos(ra1-ra2)))

@app.route('/')
def home():
    return 'Astro-Mio backend funcionando 🚀'

@app.route('/api/luna', methods=['POST'])
def api_luna():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No se recibió JSON'}), 400

        fecha_str = data.get('fecha')
        tolerancia = float(data.get('tolerancia', 1.0))  # tolerancia en grados
        sexo = data.get('sexo', '').lower()

        if not fecha_str:
            return jsonify({'error': 'Falta parámetro fecha'}), 400

        # Parsear fecha con zona horaria Argentina
        argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
        try:
            fecha0 = datetime.fromisoformat(fecha_str)
        except ValueError:
            try:
                fecha0 = datetime.strptime(fecha_str, '%d/%m/%Y %H:%M')
            except ValueError:
                return jsonify({'error': 'Formato de fecha inválido. Usa ISO o "DD/MM/YYYY HH:MM"'}), 400

        if fecha0.tzinfo is None:
            fecha0 = argentina_tz.localize(fecha0)
        fecha0 = fecha0.astimezone(pytz.utc)

        # Posición de la Luna en fecha de nacimiento
        t_luna = ts.utc(fecha0.year, fecha0.month, fecha0.day, fecha0.hour, fecha0.minute)
        astrometric_luna = observer.at(t_luna).observe(moon).apparent()
        ra_luna, dec_luna, _ = astrometric_luna.radec()
        ra_luna_deg = ra_luna.hours * 15
        dec_luna_deg = dec_luna.degrees

        # Buscar fecha del Sol más cercana a la posición de la Luna
        fecha_sol_equivalente = None
        min_diff = float('inf')

        for delta in range(-365, 366):
            f = fecha0 + timedelta(days=delta)
            t_sol = ts.utc(f.year, f.month, f.day)
            astrometric_sol = observer.at(t_sol).observe(sun).apparent()
            ra_sol, dec_sol, _ = astrometric_sol.radec()
            ra_sol_deg = ra_sol.hours * 15
            dec_sol_deg = dec_sol.degrees

            diff = angular_distance(ra_luna_deg, dec_luna_deg, ra_sol_deg, dec_sol_deg)
            if diff < min_diff:
                min_diff = diff
                fecha_sol_equivalente = f
            if min_diff <= tolerancia:
                break  # coincidencia suficiente

        resultado = {
            'fecha_luna': fecha0.isoformat(),
            'sol_equivalente': fecha_sol_equivalente.isoformat() if fecha_sol_equivalente else None,
            'interpretacion': "Energía Complementaria Día de nacimiento" if sexo else ""
        }

        return jsonify({'orbitas': [resultado]})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Servidor iniciado en http://127.0.0.1:5050")
    app.run(debug=True, port=5050)
