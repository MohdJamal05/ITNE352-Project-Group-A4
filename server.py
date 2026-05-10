import socket
import json
import urllib.request
import threading


def fetch_reference_data():
    print("Fetching reference data from TheMealDB...")
    categories = []
    areas = []
    ingredients = []
    try:
        cat_url = "https://www.themealdb.com/api/json/v1/1/list.php?c=list"
        with urllib.request.urlopen(cat_url) as response:
            data = json.loads(response.read().decode())
            categories = [
                {'name': m['strCategory']}
                for m in data['meals']
            ]

        area_url = "https://www.themealdb.com/api/json/v1/1/list.php?a=list"
        with urllib.request.urlopen(area_url) as response:
            data = json.loads(response.read().decode())
            areas = [m['strArea'] for m in data['meals']]

        ing_url = "https://www.themealdb.com/api/json/v1/1/list.php?i=list"
        with urllib.request.urlopen(ing_url) as response:
            data = json.loads(response.read().decode())
            ingredients = [m['strIngredient'] for m in data['meals']]

        reference = {'categories': categories, 'areas': areas, 'ingredients': ingredients}

        with open('reference_A4.json', 'w') as f:
            json.dump({
                'categories': categories,
                'areas': areas,
                'ingredients': ingredients[:50]
            }, f, indent=2)

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
def save_json(username, option, data):
    filename = f"{username}_{option}_A4.json"
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"  [SAVED] {filename}")

def handle_client(conn, cache):
    username = conn.recv(1024).decode('ascii')
    print(f"[+] Client connected: {username}")
    conn.sendall(f"Welcome {username}!".encode('ascii'))

    while True:
        request = recv_msg(conn)
        if request is None:
            break

        req_type = request.get('type', '')
        params   = request.get('params', '')

        if req_type == 'GET_CATEGORIES':
            print(f"  [{username}] GET_CATEGORIES  [from CACHE]")
            send_msg(conn, {'type': 'CATEGORIES', 'data': cache['categories']})

        elif req_type == 'GET_AREAS':
            print(f"  [{username}] GET_AREAS  [from CACHE]")
            send_msg(conn, {'type': 'AREAS', 'data': cache['areas']})

        elif req_type == 'GET_INGREDIENTS':
            print(f"  [{username}] GET_INGREDIENTS  [from CACHE]")
            send_msg(conn, {'type': 'INGREDIENTS', 'data': cache['ingredients'][:50]})

        elif req_type == 'SEARCH_BY_NAME':
            print(f"  [{username}] SEARCH_BY_NAME  params='{params}'  [from API]")
            data  = fetch_url(f"{BASE_URL}/search.php?s={params}")
            meals = data.get('meals') if data else None
            brief = build_brief_list(meals)
            save_json(username, 'search_by_name', brief)
            send_msg(conn, {'type': 'RECIPE_LIST', 'data': brief})

        elif req_type == 'FILTER_BY_CATEGORY':
            print(f"  [{username}] FILTER_BY_CATEGORY  params='{params}'  [from API]")
            data  = fetch_url(f"{BASE_URL}/filter.php?c={params}")
            meals = data.get('meals') if data else None
            brief = build_brief_list(meals)
            save_json(username, 'filter_by_category', brief)
            send_msg(conn, {'type': 'RECIPE_LIST', 'data': brief})

        elif req_type == 'FILTER_BY_AREA':
            print(f"  [{username}] FILTER_BY_AREA  params='{params}'  [from API]")
            data  = fetch_url(f"{BASE_URL}/filter.php?a={params}")
            meals = data.get('meals') if data else None
            brief = build_brief_list(meals)
            save_json(username, 'filter_by_area', brief)
            send_msg(conn, {'type': 'RECIPE_LIST', 'data': brief})

        elif req_type == 'FILTER_BY_INGREDIENT':
            print(f"  [{username}] FILTER_BY_INGREDIENT  params='{params}'  [from API]")
            data  = fetch_url(f"{BASE_URL}/filter.php?i={params}")
            meals = data.get('meals') if data else None
            brief = build_brief_list(meals)
            save_json(username, 'filter_by_ingredient', brief)
            send_msg(conn, {'type': 'RECIPE_LIST', 'data': brief})

        elif req_type == 'RANDOM_RECIPE':
            print(f"  [{username}] RANDOM_RECIPE  [from API]")
            data  = fetch_url(f"{BASE_URL}/random.php")
            meal  = data['meals'][0] if data and data.get('meals') else None
            detail = build_full_detail(meal)
            save_json(username, 'random_recipe', detail)
            send_msg(conn, {'type': 'RECIPE_DETAIL', 'data': detail})

        elif req_type == 'GET_DETAIL':
            print(f"  [{username}] GET_DETAIL  id='{params}'  [from API]")
            data  = fetch_url(f"{BASE_URL}/lookup.php?i={params}")
            meal  = data['meals'][0] if data and data.get('meals') else None
            detail = build_full_detail(meal)
            save_json(username, 'get_detail', detail)
            send_msg(conn, {'type': 'RECIPE_DETAIL', 'data': detail})

        elif req_type == 'QUIT':
            print(f"  [{username}] QUIT")
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
ss.listen(5)
print("Server listening on port 12000...")

while True:
    conn, addr = ss.accept()
    print(f"[+] New connection from {addr}")
    thread = threading.Thread(target=handle_client, args=(conn, cache))
    thread.daemon = True
    thread.start()