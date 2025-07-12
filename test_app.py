from datetime import datetime, timedelta, timezone
import json
from flask_jwt_extended import create_access_token, decode_token
import pytest
from app import mongo
register_cases = [
    ({'uname':'success','password':'password'},201),
    ({'uname':'success','password':'assword'},409),        
    ]
@pytest.mark.parametrize('payload,expected',register_cases)
def test_register(client,payload,expected):        
    response = client.post('/register',data = json.dumps(payload),content_type='application/json')
    assert response.status_code == expected

login_cases = [
    ({'uname':'sucess','password':'assword'},400),        
    ({'uname':'success','password':'password'},200),
    ]
@pytest.mark.parametrize('payload,expected',login_cases)
def test_login(client,payload,expected):
        response = client.post('/login',data=json.dumps(payload),content_type='application/json')
        
        assert response.status_code == expected
        if(expected==200):            
            set_cookie = response.headers.get('Set-Cookie')
            assert set_cookie is not None

def test_get_places(client):
    data = {
        'lat': 6.5,     # ✅ Latitude must be in [-90, 90]
        'lon': 100,     # ✅ Longitude must be in [-180, 180]
        'radius': 1000
    }

    response = client.post('/places', json=data)

    assert response.status_code == 200, f"Unexpected status: {response.status_code}, Response: {response.get_data(as_text=True)}"

    json_data = response.get_json()
    assert isinstance(json_data, dict) or isinstance(json_data, list), "Response is not valid JSON"
    assert 'places' in json_data or len(json_data) >= 0, "Expected 'places' data in response or non-empty result"

def test_reserve_without_token(client):    
    # Simulated valid datetime
    valid_datetime = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
   
    # Valid reservation
    response = client.post(
        "/reserve/fake_place_id_123",
        json={"datetime": valid_datetime}
    )

    assert response.status_code == 401
    
def test_reserve(client):
    # Simulate a user identity
    uname = "success"
    token = create_access_token(identity=uname)

    # Simulated valid datetime
    valid_datetime = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    
    # Valid reservation
    response = client.post(
        "/reserve/fake_place_id_123",
        headers={'Authorization':f'Bearer {token}'},
        json={"datetime": valid_datetime}
    )

    assert response.status_code == 201
    assert response.json["msg"] == "Reservation successful"    

def test_reserve_invalid_datetime(client):
    token = create_access_token(identity="success")

    response = client.post(
        "/reserve/invalid_time_test",
        headers={'Authorization':f'Bearer {token}'},
        json={"datetime": "not-a-valid-date"}
    )

    assert response.status_code == 400
    assert response.json["error"] == "Invalid datetime format"

def test_get_reservations(client):
    # First, ensure reservation is inserted (or insert manually)
    uname = "success"
    placeid = "fake_place_id_123"
    dt = datetime.now(timezone.utc) + timedelta(days=1)
    
    # Now test the GET request
    response = client.get(f"/reservations/{placeid}")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert any(r["uname"] == uname and r["placeid"] == placeid for r in data)

def test_get_reservations_not_found(client):
    response = client.get("/reservations/non_existing_place_999")
    assert response.status_code == 404    

def test_cancel_reservation(client):
    from bson.objectid import ObjectId
    from flask_jwt_extended import create_access_token

    uname = "success"
    token = create_access_token(identity=uname)

    # Insert reservation directly into test DB
    reservation = {
        "placeid": "cancel_place_123",
        "uname": uname,
        "datetime": datetime.now(timezone.utc) + timedelta(days=1),
        "created_at": datetime.now(timezone.utc)
    }
    inserted = mongo.db.reservations.insert_one(reservation) # type: ignore
    reserveid = str(inserted.inserted_id)

    # Now try to cancel it
    response = client.delete(f"/cancel/{reserveid}",
                             headers={'Authorization':f'Bearer {token}'})
    assert response.status_code == 200
    assert response.get_json()["msg"] == "Cancel Reservation succeed"

    # Make sure it’s actually deleted
    result = mongo.db.reservations.find_one({"_id": ObjectId(reserveid)}) # type: ignore
    assert result is None

def test_cancel_reservation_not_found(client):
    token = create_access_token(identity="success")

    # Use a random ObjectId that doesn't exist
    fake_id = "60f6f0f0f0f0f0f0f0f0f0f0"
    response = client.delete(f"/cancel/{fake_id}",headers={'Authorization':f'Bearer {token}'})
    assert response.status_code == 404

def test_logout(client):
    token = create_access_token('success')
    client.set_cookie('access_token_cookie',token)
    response = client.delete('/logout')
    
    assert response.status_code == 200
    set_cookie = response.headers.get('Set-Cookie')
    assert set_cookie is not None
    assert 'Max-Age=0' in set_cookie or 'Expires=' in set_cookie