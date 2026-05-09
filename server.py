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
            categories = data['meals']

        area_url = "https://www.themealdb.com/api/json/v1/1/list.php?a=list"
        with urllib.request.urlopen(area_url) as response:
            data = json.loads(response.read().decode())
            areas = data['meals']

        ing_url = "https://www.themealdb.com/api/json/v1/1/list.php?i=list"
        with urllib.request.urlopen(ing_url) as response:
            data = json.loads(response.read().decode())
            ingredients = data['meals']
        reference = {'categories': categories, 'areas': areas, 'ingredients': ingredients}

        with open('reference_A4.json', 'w') as f:
            json.dump(reference, f, indent=2)

        print("Reference data saved to reference_A4.json")
        return reference

    except Exception as e:
        print(f"Error fetching data: {e}")
        return None



BASE_URL = "https://www.themealdb.com/api/json/v1/1"

def send_msg(conn, payload):
    data = json.dumps(payload).encode('utf-8')
    conn.sendall(len(data).to_bytes(4, 'big') + data)

def recv_msg(conn):
    raw = _recv_exact(conn, 4)
    if raw is None:
        return None
    length = int.from_bytes(raw, 'big')
    raw = _recv_exact(conn, length)
    if raw is None:
        return None
    return json.loads(raw.decode('utf-8'))

def _recv_exact(conn, n):
    buf = b''
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf

def fetch_url(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"  [HTTP ERROR] {e}")
        return None

def build_brief_list(meals):
    if not meals:
        return []
    return [
        {
            'idMeal':       m.get('idMeal', ''),
            'strMeal':      m.get('strMeal', ''),
            'strMealThumb': m.get('strMealThumb', '')
        }
        for m in meals[:15]
    ]

def build_full_detail(meal):
    if not meal:
        return None
    ingredients = []
    for i in range(1, 21):
        ing = meal.get(f'strIngredient{i}', '')
        mea = meal.get(f'strMeasure{i}', '')
        if ing and ing.strip():
            ingredients.append(f"{mea.strip()} {ing.strip()}".strip())
    return {
        'strMeal':         meal.get('strMeal', ''),
        'strCategory':     meal.get('strCategory', ''),
        'strArea':         meal.get('strArea', ''),
        'strInstructions': meal.get('strInstructions', ''),
        'ingredients':     ingredients,
        'strYoutube':      meal.get('strYoutube', ''),
        'strSource':       meal.get('strSource', ''),
        'strTags':         meal.get('strTags', '')
    }

def handle_client(conn, cache):
    username = conn.recv(1024).decode('ascii')
    print(f"Client name: {username}")
    conn.sendall(f"Welcome {username}!".encode('ascii'))

    while True:
        request = recv_msg(conn)
        if request is None:
            break

        req_type = request.get('type', '')
        params   = request.get('params', '')
        print(f"  [{username}] Request: {req_type}  Params: '{params}'")

        if req_type == 'GET_CATEGORIES':
            send_msg(conn, {'type': 'CATEGORIES', 'data': cache['categories']})

        elif req_type == 'GET_AREAS':
            send_msg(conn, {'type': 'AREAS', 'data': cache['areas']})

        elif req_type == 'GET_INGREDIENTS':
            send_msg(conn, {'type': 'INGREDIENTS', 'data': cache['ingredients'][:50]})

        elif req_type == 'SEARCH_BY_NAME':
            data  = fetch_url(f"{BASE_URL}/search.php?s={params}")
            meals = data.get('meals') if data else None
            send_msg(conn, {'type': 'RECIPE_LIST', 'data': build_brief_list(meals)})

        elif req_type == 'FILTER_BY_CATEGORY':
            data  = fetch_url(f"{BASE_URL}/filter.php?c={params}")
            meals = data.get('meals') if data else None
            send_msg(conn, {'type': 'RECIPE_LIST', 'data': build_brief_list(meals)})

        elif req_type == 'FILTER_BY_AREA':
            data  = fetch_url(f"{BASE_URL}/filter.php?a={params}")
            meals = data.get('meals') if data else None
            send_msg(conn, {'type': 'RECIPE_LIST', 'data': build_brief_list(meals)})

        elif req_type == 'FILTER_BY_INGREDIENT':
            data  = fetch_url(f"{BASE_URL}/filter.php?i={params}")
            meals = data.get('meals') if data else None
            send_msg(conn, {'type': 'RECIPE_LIST', 'data': build_brief_list(meals)})

        elif req_type == 'RANDOM_RECIPE':
            data  = fetch_url(f"{BASE_URL}/random.php")
            meal  = data['meals'][0] if data and data.get('meals') else None
            send_msg(conn, {'type': 'RECIPE_DETAIL', 'data': build_full_detail(meal)})

        elif req_type == 'GET_DETAIL':
            data  = fetch_url(f"{BASE_URL}/lookup.php?i={params}")
            meal  = data['meals'][0] if data and data.get('meals') else None
            send_msg(conn, {'type': 'RECIPE_DETAIL', 'data': build_full_detail(meal)})

        elif req_type == 'QUIT':
            break

        else:
            send_msg(conn, {'type': 'ERROR', 'message': f'Unknown request: {req_type}'})

    conn.close()
    print(f"[-] '{username}' disconnected.")


#main
cache = fetch_reference_data()


ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ss.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
ss.bind(('127.0.0.1', 12000))
ss.listen(1)
print("Server listening on port 12000...")

conn, addr = ss.accept()
print(f"Client connected from {addr}")

handle_client(conn, cache)

ss.close()
conn.sendall(f"Welcome {username}!".encode('ascii'))

conn.close()

ss.close()
