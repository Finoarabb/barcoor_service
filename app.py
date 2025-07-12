from datetime import datetime
from bson import ObjectId
from flask import Flask, current_app, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required, set_access_cookies, unset_jwt_cookies
import requests
from werkzeug.security import generate_password_hash,check_password_hash
import os
from dotenv import load_dotenv
from flask_pymongo import PyMongo

mongo = PyMongo()
jwt = JWTManager()
def create_app():
    load_dotenv()
    app = Flask(__name__)
    # DB
    app.config['MONGO_URI'] = os.getenv('MONGO_URI')
    mongo.init_app(app)
    # JWT
    app.config['JWT_SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3600
    app.config['JWT_TOKEN_LOCATION'] = ['cookies','headers']
    app.config['JWT_COOKIE_SECURE'] = False  
    app.config['JWT_COOKIE_CSRF_PROTECT'] = False
    app.config['JWT_ACCESS_COOKIE_NAME'] ='access_token_cookie'
    app.config["JWT_ACCESS_COOKIE_PATH"] = "/"
    app.config["JWT_ACCESS_COOKIE_SAMESITE"] = "None"
    app.config["JWT_ACCESS_COOKIE_HTTPONLY"] = True
    jwt.init_app(app)
            
    # CORS    
    CORS(app,supports_credentials=True)

    # Auth 
    @app.post('/login')
    def login():
        data = request.get_json()
        uname = data.get('uname')
        password = data.get('password')    
        if not uname or not password:
            return jsonify({'error': 'Missing username or password'}), 400
        account = mongo.db.users.find_one({'uname': uname})   # type: ignore
        if account is None or not check_password_hash(account['hashed_password'], password):
            return jsonify({'error': 'Username or Password wrong, please try again'}), 400
        access_token = create_access_token(identity=uname)    
        response = jsonify({'msg': 'Login Success'})
        set_access_cookies(response,access_token)
        print(response.headers)
        return response

    @app.post('/register')
    def register():
        data = request.get_json()
        uname = data.get('uname')
        password = data.get('password')   
        if not uname or not password:
            return jsonify({'error': 'Missing username or password'}), 400
        if mongo.db.users.find_one({'uname': uname}):  # type: ignore
            return jsonify({'error': 'Username already exists'}), 409
        hashed_password = generate_password_hash(password)
        mongo.db.users.insert_one({'uname': uname, 'hashed_password': hashed_password}) # type: ignore
        return jsonify({'msg': 'Registration successful'}), 201

    @app.delete('/logout')
    def logout():
        response = jsonify({'msg': 'Logout Success'}, 200)
        unset_jwt_cookies(response)
        return response

    @app.post('/places')
    def get_places():
        data = request.get_json()
        lat,lon = data.get('lat'), data.get('lon')
        if not lat or not lon:
            return jsonify({'error': 'Missing latitude, longitude or radius'}), 400
        radius = min(data.get('radius', 1000), 20000)  # Default radius is 1000 meters, max is 10000 meters
        overpass_query = f"""[out:json];
        (
        node["amenity"="restaurant"](around:{radius},{lat},{lon});
        node["amenity"="cafe"](around:{radius},{lat},{lon});
        node["amenity"="bar"](around:{radius},{lat},{lon});
        );
        out body;
        """
        response = requests.post("https://overpass-api.de/api/interpreter", data=overpass_query)
        if response.ok:
            elements = response.json().get('elements', [])
            places = []
            for element in elements:
                name = element.get('tags', {}).get('name', '')
                if not name: continue
                place = {
                    'id': hash((element['id'], name, element['lat'], element['lon'])),
                    'lat': element['lat'],
                    'lon': element['lon'],
                    'type': element.get('type', 'Unknown'),
                    'name': name,
                    'amenity': element.get('tags', {}).get('amenity', 'Unknown'),                
                }
                address = element.get('tags', {}).get('addr:full', '')
                if not address:
                    street = element.get('tags', {}).get('addr:street', '')
                    city = element.get('tags', {}).get('addr:city', '')
                    if street and city:
                        address = f"{element.get('tags', {}).get('addr:street', '')}, {element.get('tags', {}).get('addr:city', '')}"
                    elif street:
                        address = street
                    elif city:
                        address = city
                    else:
                        address = 'Unknown'
                place['address'] = address
                places.append(place)            
            
            return jsonify(places), 200
        else:
            return jsonify({'error': 'Failed to fetch places from Overpass API'}), 500        

    @app.get('/reservations/<placeid>')
    def get_reservations(placeid):
        reservations = list(mongo.db.reservations.find({'placeid':placeid})) # type: ignore
        if not reservations:
            return jsonify({'Reservations not found'}),404        
        return jsonify(reservations),200

    @app.post('/reserve/<placeid>')
    @jwt_required()
    def reserve(placeid):
        data = request.get_json()
        data['placeid'] = placeid
        try:
            data['datetime'] = datetime.fromisoformat(data.get('datetime'))
        except:
            return jsonify({'error':'Invalid datetime format'}),400
        data['uname'] = get_jwt_identity()
        mongo.db.reservations.insert_one(data)  # type: ignore
        return jsonify({'msg': 'Reservation successful'}), 201         

    @app.delete('/cancel/<reserveid>')
    @jwt_required()
    def cancel_reservation(reserveid):
        try:        
            result = mongo.db.reservations.delete_one({'_id':ObjectId(reserveid)}) # type: ignore
            if result.deleted_count == 0:
                return jsonify({'error':'Reservation not found'}),404
            return jsonify({'msg':'Cancel Reservation succeed'}),200
        except Exception as e:
            return jsonify({'error':f'Cancel Reservations failed: {str(e)}'}),400
    return app

app = create_app()
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=True)
 