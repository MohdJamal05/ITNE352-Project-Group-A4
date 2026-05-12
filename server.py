import socket
import json
import urllib.request
import threading


# ─────────────────────────────────────────────
#  Utility helpers  (shared by server & client)
# ─────────────────────────────────────────────

class MessageHelper:
    """Encapsulates the length-prefixed JSON framing protocol."""

    @staticmethod
    def send(conn, payload: dict) -> None:
        data = json.dumps(payload).encode('utf-8')
        conn.sendall(len(data).to_bytes(4, 'big') + data)

    @staticmethod
    def receive(conn) -> object:
        raw = MessageHelper._recv_exact(conn, 4)
        if raw is None:
            return None
        length = int.from_bytes(raw, 'big')
        raw = MessageHelper._recv_exact(conn, length)
        if raw is None:
            return None
        return json.loads(raw.decode('utf-8'))

    @staticmethod
    def _recv_exact(conn, n: int) -> object:
        buf = b''
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf


# ─────────────────────────────────────────────
#  MealDB API wrapper
# ─────────────────────────────────────────────

class MealDBClient:
    """
    Encapsulates all HTTP calls to TheMealDB API.
    Responsibility: fetch raw data from the external API.
    """

    BASE_URL = "https://www.themealdb.com/api/json/v1/1"

    def fetch(self, url: str) -> object:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            print(f"  [HTTP ERROR] {e}")
            return None

    def search_by_name(self, name: str) -> object:
        return self.fetch(f"{self.BASE_URL}/search.php?s={name}")

    def filter_by_category(self, category: str) -> object:
        return self.fetch(f"{self.BASE_URL}/filter.php?c={category}")

    def filter_by_area(self, area: str) -> object:
        return self.fetch(f"{self.BASE_URL}/filter.php?a={area}")

    def filter_by_ingredient(self, ingredient: str) -> object:
        return self.fetch(f"{self.BASE_URL}/filter.php?i={ingredient}")

    def random_recipe(self) -> object:
        return self.fetch(f"{self.BASE_URL}/random.php")

    def get_detail(self, meal_id: str) -> object:
        return self.fetch(f"{self.BASE_URL}/lookup.php?i={meal_id}")

    def get_categories(self) -> list:
        data = self.fetch(f"{self.BASE_URL}/list.php?c=list")
        return [{'name': m['strCategory']} for m in data['meals']] if data else []

    def get_areas(self) -> list:
        data = self.fetch(f"{self.BASE_URL}/list.php?a=list")
        return [m['strArea'] for m in data['meals']] if data else []

    def get_ingredients(self) -> list:
        data = self.fetch(f"{self.BASE_URL}/list.php?i=list")
        return [m['strIngredient'] for m in data['meals']] if data else []


# ─────────────────────────────────────────────
#  Data formatter  (pure transformation logic)
# ─────────────────────────────────────────────

class RecipeFormatter:
    """
    Transforms raw API meals into the shapes the client expects.
    Responsibility: data shaping / formatting only.
    """

    @staticmethod
    def brief_list(meals: list, limit: int = 15) -> list:
        if not meals:
            return []
        return [
            {
                'idMeal':       m.get('idMeal', ''),
                'strMeal':      m.get('strMeal', ''),
                'strMealThumb': m.get('strMealThumb', '')
            }
            for m in meals[:limit]
        ]

    @staticmethod
    def full_detail(meal: dict) -> object:
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


# ─────────────────────────────────────────────
#  Reference data cache
# ─────────────────────────────────────────────

class ReferenceCache:
    """
    Fetches and stores the static lookup lists (categories, areas,
    ingredients) at startup so every client thread reads from memory.
    Responsibility: one-time data loading and in-memory caching.
    """

    def __init__(self, api: MealDBClient):
        self._api = api
        self.categories: list = []
        self.areas: list = []
        self.ingredients: list = []

    def load(self) -> bool:
        print("Fetching reference data from TheMealDB...")
        try:
            self.categories  = self._api.get_categories()
            self.areas       = self._api.get_areas()
            self.ingredients = self._api.get_ingredients()

            with open('reference_A4.json', 'w') as f:
                json.dump({
                    'categories':  self.categories,
                    'areas':       self.areas,
                    'ingredients': self.ingredients[:50]
                }, f, indent=2)

            print("Reference data saved to reference_A4.json")
            return True
        except Exception as e:
            print(f"Error fetching reference data: {e}")
            return False


# ─────────────────────────────────────────────
#  Client session handler
# ─────────────────────────────────────────────

class ClientHandler:
    """
    Manages one connected client: reads requests, calls the API or
    cache, formats results, and sends responses back.
    Responsibility: per-client request/response lifecycle.
    """

    def __init__(self, conn: socket.socket, cache: ReferenceCache):
        self._conn      = conn
        self._cache     = cache
        self._api       = MealDBClient()
        self._formatter = RecipeFormatter()
        self._username  = "unknown"

    # ── public entry point ──────────────────────────────────────────

    def run(self) -> None:
        self._handshake()
        self._request_loop()
        self._conn.close()
        print(f"[-] '{self._username}' disconnected.")

    # ── private helpers ─────────────────────────────────────────────

    def _handshake(self) -> None:
        data = b''
        while not data:
            data = self._conn.recv(1024)
        self._username = data.decode('ascii').strip()
        print(f"[+] Client connected: {self._username}")
        self._conn.sendall(f"Welcome {self._username}!".encode('ascii'))

    def _request_loop(self) -> None:
        while True:
            request = MessageHelper.receive(self._conn)
            if request is None:
                break

            req_type = request.get('type', '')
            params   = request.get('params', '')

            if not self._dispatch(req_type, params):
                break

    def _dispatch(self, req_type: str, params: str) -> bool:
        """Routes a request type to its handler. Returns False to stop loop."""

        handlers = {
            'GET_CATEGORIES':      self._handle_get_categories,
            'GET_AREAS':           self._handle_get_areas,
            'GET_INGREDIENTS':     self._handle_get_ingredients,
            'SEARCH_BY_NAME':      self._handle_search_by_name,
            'FILTER_BY_CATEGORY':  self._handle_filter_by_category,
            'FILTER_BY_AREA':      self._handle_filter_by_area,
            'FILTER_BY_INGREDIENT':self._handle_filter_by_ingredient,
            'RANDOM_RECIPE':       self._handle_random_recipe,
            'GET_DETAIL':          self._handle_get_detail,
        }

        if req_type == 'QUIT':
            print(f"  [{self._username}] QUIT")
            return False

        handler = handlers.get(req_type)
        if handler:
            handler(params)
        else:
            MessageHelper.send(self._conn,
                {'type': 'ERROR', 'message': f'Unknown request: {req_type}'})
        return True

    # ── request handlers ────────────────────────────────────────────

    def _handle_get_categories(self, _):
        print(f"  [{self._username}] GET_CATEGORIES  [from CACHE]")
        MessageHelper.send(self._conn,
            {'type': 'CATEGORIES', 'data': self._cache.categories})

    def _handle_get_areas(self, _):
        print(f"  [{self._username}] GET_AREAS  [from CACHE]")
        MessageHelper.send(self._conn,
            {'type': 'AREAS', 'data': self._cache.areas})

    def _handle_get_ingredients(self, _):
        print(f"  [{self._username}] GET_INGREDIENTS  [from CACHE]")
        MessageHelper.send(self._conn,
            {'type': 'INGREDIENTS', 'data': self._cache.ingredients[:50]})

    def _handle_search_by_name(self, params: str):
        print(f"  [{self._username}] SEARCH_BY_NAME  params='{params}'")
        data  = self._api.search_by_name(params)
        brief = self._formatter.brief_list(data.get('meals') if data else None)
        self._save_and_send(brief, 'search_by_name', 'RECIPE_LIST')

    def _handle_filter_by_category(self, params: str):
        print(f"  [{self._username}] FILTER_BY_CATEGORY  params='{params}'")
        data  = self._api.filter_by_category(params)
        brief = self._formatter.brief_list(data.get('meals') if data else None)
        self._save_and_send(brief, 'filter_by_category', 'RECIPE_LIST')

    def _handle_filter_by_area(self, params: str):
        print(f"  [{self._username}] FILTER_BY_AREA  params='{params}'")
        data  = self._api.filter_by_area(params)
        brief = self._formatter.brief_list(data.get('meals') if data else None)
        self._save_and_send(brief, 'filter_by_area', 'RECIPE_LIST')

    def _handle_filter_by_ingredient(self, params: str):
        print(f"  [{self._username}] FILTER_BY_INGREDIENT  params='{params}'")
        data  = self._api.filter_by_ingredient(params)
        brief = self._formatter.brief_list(data.get('meals') if data else None)
        self._save_and_send(brief, 'filter_by_ingredient', 'RECIPE_LIST')

    def _handle_random_recipe(self, _):
        print(f"  [{self._username}] RANDOM_RECIPE")
        data   = self._api.random_recipe()
        meal   = data['meals'][0] if data and data.get('meals') else None
        detail = self._formatter.full_detail(meal)
        self._save_and_send(detail, 'random_recipe', 'RECIPE_DETAIL')

    def _handle_get_detail(self, params: str):
        print(f"  [{self._username}] GET_DETAIL  id='{params}'")
        data   = self._api.get_detail(params)
        meal   = data['meals'][0] if data and data.get('meals') else None
        detail = self._formatter.full_detail(meal)
        self._save_and_send(detail, 'get_detail', 'RECIPE_DETAIL')

    def _save_and_send(self, data, option: str, msg_type: str) -> None:
        import os
        filename = f"{self._username}_{option}_A4.json"
        try:
            save_dir = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(save_dir, filename)
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"  [SAVED] {filepath}")
        except Exception as e:
            print(f"  [SAVE ERROR] {e}")
        MessageHelper.send(self._conn, {'type': msg_type, 'data': data})


# ─────────────────────────────────────────────
#  Server
# ─────────────────────────────────────────────

class RecipeServer:
    """
    Owns the listening socket, accepts connections, and spawns a
    daemon thread for each client.
    Responsibility: network lifecycle and concurrency management.
    """

    def __init__(self, host: str = '127.0.0.1', port: int = 12000):
        self._host  = host
        self._port  = port
        self._cache = ReferenceCache(MealDBClient())

    def start(self) -> None:
        if not self._cache.load():
            print("Could not load reference data. Exiting.")
            return

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self._host, self._port))
        server_socket.listen(5)
        print(f"Server listening on {self._host}:{self._port}...")

        while True:
            conn, addr = server_socket.accept()
            print(f"[+] New connection from {addr}")
            handler = ClientHandler(conn, self._cache)
            thread  = threading.Thread(target=handler.run)
            thread.daemon = True
            thread.start()


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────

if __name__ == '__main__':
    RecipeServer().start()