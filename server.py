import socket
import json
import urllib.request

def fetch_reference_data():
    print("Fetching reference data from TheMealDB...")
    categories = []
    areas = []
    ingredients = []
    try:
        cat_url = "https://www.themealdb.com/api/json/v1/1/list.php?c=list"
        with urllib.request.urlopen(cat_url) as response:
            data = json.loads(response.read().decode())
            categories = [item['strCategory'] for item in data['meals']]

        area_url = "https://www.themealdb.com/api/json/v1/1/list.php?a=list"
        with urllib.request.urlopen(area_url) as response:
            data = json.loads(response.read().decode())
            areas = [item['strArea'] for item in data['meals']]

        ing_url = "https://www.themealdb.com/api/json/v1/1/list.php?i=list"
        with urllib.request.urlopen(ing_url) as response:
            data = json.loads(response.read().decode())
            ingredients = [item['strIngredient'] for item in data['meals']]

        reference = {'categories': categories, 'areas': areas, 'ingredients': ingredients}

        with open('reference_A4.json', 'w') as f:
            json.dump(reference, f, indent=2)

        print("Reference data saved to reference_A4.json")
        return reference

    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

fetch_reference_data()

ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ss.bind(('127.0.0.1', 12000))
ss.listen(1)
print("Server listening on port 12000...")

conn, addr = ss.accept()
print(f"Client connected from {addr}")

username = conn.recv(1024).decode('ascii')
print(f"Client name: {username}")

conn.sendall(f"Welcome {username}!".encode('ascii'))

conn.close()
ss.close()