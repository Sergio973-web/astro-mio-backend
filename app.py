from flask_cors import CORS
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import pytz
import traceback
import swisseph as swe  # PySwissEphemeris

app = Flask(__name__)
CORS(app)

SIDEREAL_PERIOD = 27.321661  # período sideral de la Luna

# Latitud y longitud del observador (Argentina, solo para referencia)
LAT = -35.6581
LON = -63.7575

def datetime_to_julian(fecha):
    """Convierte datetime a JD UT para swe"""
    return swe.julday(
        fecha.year, fecha.month, fecha.day,
        fecha.hour + fecha.minute/60.0 + fecha.second/3600.0
    )

def calcular_posicion_luna(fecha):
    """Devuelve RA y DEC de la Luna en grados usando swe"""
    jd = datetime_to_julian(fecha)
    lon, lat, dist = swe.calc_ut(jd, swe.MOON, swe.FLG_EQUATORIAL)[0:3]
    return lon, lat  # RA, DEC en grados

def calcular_posicion_sol(fecha):
    """Devuelve RA y DEC del Sol en grados usando swe"""
    jd = datetime_to_julian(fecha)
    lon, lat, dist = swe.calc_ut(jd, swe.SUN, swe.FLG_EQUATORIAL)[0:3]
    return lon, lat  # RA, DEC en grados

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

        # Parsear fecha y ajustar a zona horaria Argentina
        argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
        fecha0 = datetime.fromisoformat(fecha_str)
        if fecha0.tzinfo is None:
            fecha0 = argentina_tz.localize(fecha0)
        fecha0 = fecha0.astimezone(pytz.utc)

        # Posición inicial de la Luna
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
                            'ascension_recta': f'{rak:.2f}°',
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
            ra_sol, dec_sol = calcular_posicion_sol(fecha_busqueda)

            diff_ra = abs(ra_luna - ra_sol)
            diff_dec = abs(dec_luna - dec_sol)
            diferencia = (diff_ra**2 + diff_dec**2)**0.5

            if diferencia < diferencia_minima and diff_ra < tol_degrees and diff_dec < tol_degrees:
                diferencia_minima = diferencia
                fecha_sol_mas_cercana = fecha_busqueda

        interpretacion = "Energía Complementaria Día de nacimiento" if sexo in ['masculino', 'femenino'] else ""

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
