import socket
import json


# ─────────────────────────────────────────────
#  Utility helpers  (shared protocol layer)
# ─────────────────────────────────────────────

class MessageHelper:
    """Encapsulates the length-prefixed JSON framing protocol."""

    @staticmethod
    def send(sock: socket.socket, payload: dict) -> None:
        # Serialize the payload dict to JSON bytes
        data = json.dumps(payload).encode('utf-8')
        # Prepend a 4-byte big-endian length header, then send the full message
        sock.sendall(len(data).to_bytes(4, 'big') + data)

    @staticmethod
    def receive(sock: socket.socket) -> dict | None:
        # Read the 4-byte length header first
        raw = MessageHelper._recv_exact(sock, 4)
        if raw is None:
            return None 
        length = int.from_bytes(raw, 'big')
        # Now read exactly that many bytes for the message body
        raw = MessageHelper._recv_exact(sock, length)
        if raw is None:
            return None # Connection closed or no data received
        return json.loads(raw.decode('utf-8'))

    @staticmethod
    def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
        # Keep reading until we have exactly n bytes (handles TCP fragmentation)
        buf = b''
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf


# ─────────────────────────────────────────────
#  Display / UI helpers
# ─────────────────────────────────────────────

class Display:
    """
    All terminal output lives here.
    Responsibility: presentation only — no network or business logic.
    """ 
    @staticmethod
    def header(title: str) -> None:
        # Print a consistent section header for all screens
        print(f"\n{'─' * 55}\n  {title}\n{'─' * 55}")

    @staticmethod
    def recipe_list(meals: list) -> None:
        # Display a numbered list of meals with their thumbnail URLs
        if not meals:
            print("  No results found.")
            return
        Display.header("Results")
        for i, m in enumerate(meals, 1):
            print(f"  {i:>2}. {m['strMeal']}")
            print(f"       {m['strMealThumb']}")

    @staticmethod
    def recipe_detail(d: dict) -> None:
        # Display full recipe details including ingredients and instructions
        if not d:
            print("  No detail available.")
            return
        Display.header(d.get('strMeal', 'Recipe'))
        print(f"  Category : {d.get('strCategory', 'N/A')}")
        print(f"  Cuisine  : {d.get('strArea', 'N/A')}")
        print(f"  Tags     : {d.get('strTags') or 'N/A'}")
        print(f"  YouTube  : {d.get('strYoutube') or 'N/A'}")
        print(f"  Source   : {d.get('strSource') or 'N/A'}")
        print("\n  Ingredients:")
        for ing in d.get('ingredients', []):
            print(f"    • {ing}")
        print("\n  Instructions:")
        # Word-wrap the instructions at 74 characters for readability
        words, line = d.get('strInstructions', '').split(), "    "
        for w in words:
            if len(line) + len(w) + 1 > 74:
                print(line)
                line = "    " + w + " "
            else:
                line += w + " "
        if line.strip():
            print(line)

    @staticmethod
    def flat_list(items: list, key: str | None = None) -> None:
        # Display a flat numbered list; if items are dicts, extract by key
        if not items:
            print("  No data.")
            return
        for i, item in enumerate(items, 1):
            val = item[key] if key and isinstance(item, dict) else item
            print(f"  {i:>3}. {val}")


# ─────────────────────────────────────────────
#  Input helpers
# ─────────────────────────────────────────────

class InputHelper:
    """
    All user-input gathering lives here.
    Responsibility: validated console input — no display or network.
    """
    @staticmethod
    def pick(options: list) -> int:
        # Show numbered options and loop until the user picks a valid number
        for i, o in enumerate(options, 1):
            print(f"  {i}. {o}")
        while True:
            raw = input("\n  Choice: ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return int(raw)
            print(f"  Enter a number 1-{len(options)}.")
 
    @staticmethod
    def pick_from(prompt: str, valid: list) -> str:
        # Show allowed values and loop until the user enters a valid one
        # Comparison is case-insensitive for user convenience
        print(f"\n  Options: {', '.join(valid)}")
        while True:
            v = input(f"  {prompt}: ").strip()
            match = next((x for x in valid if x.lower() == v.lower()), None)
            if match:
                return match
            print(f"  Not valid. Choose from: {', '.join(valid)}")

    @staticmethod
    def ask(prompt: str) -> str:
        # Keep prompting until the user enters a non-empty string
        while True:
            v = input(f"  {prompt}: ").strip()
            if v:
                return v
            print("  Cannot be empty.")


# ─────────────────────────────────────────────
#  Menu screens  (inheritance hierarchy)
# ─────────────────────────────────────────────

class BaseMenu:
    """
    Abstract base for all menu screens.
    Provides shared socket, display, and input helpers.
    Subclasses implement run().
    """

    # Permitted filter values as defined in the project spec (Table 2)
    VALID_CATEGORIES = ['Beef', 'Chicken', 'Seafood', 'Vegetarian',
                        'Dessert', 'Pasta', 'Breakfast']
    VALID_AREAS      = ['Italian', 'Indian', 'Mexican', 'Japanese',
                        'Moroccan', 'British', 'American', 'Thai']

    def __init__(self, sock: socket.socket):
        self._sock    = sock # Shared TCP socket to the server
        self._display = Display() # Presentation helper
        self._input   = InputHelper() # Input validation helper

    def run(self) -> None:
        # Subclasses must override this to define their screen behaviour
        raise NotImplementedError("Subclasses must implement run()")

    # ── convenience wrappers ────────────────────────────────────────

    def _send(self, payload: dict) -> None:
        # Delegate to MessageHelper so subclasses don't import it directly
        MessageHelper.send(self._sock, payload)

    def _recv(self) -> dict | None:
        # Delegate to MessageHelper so subclasses don't import it directly
        return MessageHelper.receive(self._sock)

    def _drill_down(self, meals: list) -> None:
        """Let the user pick a meal from a list and view its full detail."""
        if not meals:
            return
        self._display.recipe_list(meals)
        print(f"\n  Enter 1-{len(meals)} for full details, or 0 to go back.")
        while True:
            raw = input("  Choice: ").strip()
            if raw == '0':
                return   # User chose to go back
            if raw.isdigit() and 1 <= int(raw) <= len(meals):
                # Send the meal ID to the server and display the full detail
                meal_id = meals[int(raw) - 1]['idMeal']
                self._send({'type': 'GET_DETAIL', 'params': meal_id})
                resp = self._recv()
                if resp and resp.get('type') == 'RECIPE_DETAIL':
                    self._display.recipe_detail(resp.get('data'))
                return
            print(f"  Enter 0 or a number 1-{len(meals)}.")


class RecipesMenu(BaseMenu):
    """
    Inherits from BaseMenu.
    Handles all recipe-search and filter operations.
    """

    def run(self) -> None:
        # Loop until the user chooses to go back to the main menu
        while True:
            self._display.header("Recipes Menu")
            choice = self._input.pick([
                "Search by name",
                "Filter by category",
                "Filter by area",
                "Filter by ingredient",
                "Random recipe",
                "Back to main menu"
            ])
            if choice == 1:
                self._search_by_name()
            elif choice == 2:
                self._filter_by_category()
            elif choice == 3:
                self._filter_by_area()
            elif choice == 4:
                self._filter_by_ingredient()
            elif choice == 5:
                self._random_recipe()
            elif choice == 6:
                return  # Back to main menu

    def _search_by_name(self) -> None:
        # Ask for a keyword, send to server, then show drill-down list
        kw = self._input.ask("Enter keyword")
        self._send({'type': 'SEARCH_BY_NAME', 'params': kw})
        resp = self._recv()
        if resp and resp['type'] == 'RECIPE_LIST':
            self._drill_down(resp['data'])

    def _filter_by_category(self) -> None:
        # Validate category input before sending to server
        cat = self._input.pick_from("Enter category", self.VALID_CATEGORIES)
        self._send({'type': 'FILTER_BY_CATEGORY', 'params': cat})
        resp = self._recv()
        if resp and resp['type'] == 'RECIPE_LIST':
            self._drill_down(resp['data'])

    def _filter_by_area(self) -> None:
        # Validate area/cuisine input before sending to server
        area = self._input.pick_from("Enter area", self.VALID_AREAS)
        self._send({'type': 'FILTER_BY_AREA', 'params': area})
        resp = self._recv()
        if resp and resp['type'] == 'RECIPE_LIST':
            self._drill_down(resp['data'])

    def _filter_by_ingredient(self) -> None:
        # Replace spaces with underscores as required by the API
        ing = self._input.ask("Enter ingredient").strip().replace(' ', '_')
        self._send({'type': 'FILTER_BY_INGREDIENT', 'params': ing})
        resp = self._recv()
        if resp and resp['type'] == 'RECIPE_LIST':
            self._drill_down(resp['data'])

    def _random_recipe(self) -> None:
        # Random recipe returns full detail directly — no list step
        self._send({'type': 'RANDOM_RECIPE', 'params': ''})
        resp = self._recv()
        if resp and resp['type'] == 'RECIPE_DETAIL':
            self._display.recipe_detail(resp['data'])


class ReferenceMenu(BaseMenu):
    """
    Inherits from BaseMenu.
    Handles browsing static reference lists (categories, areas, ingredients).
    """

    def run(self) -> None:
        # Loop until the user chooses to go back to the main menu
        while True:
            self._display.header("Reference Menu")
            choice = self._input.pick([
                "List all categories",
                "List all areas",
                "List all ingredients",
                "Back to main menu"
            ])
            if choice == 1:
                self._list_categories()
            elif choice == 2:
                self._list_areas()
            elif choice == 3:
                self._list_ingredients()
            elif choice == 4:
                return  # Back to main menu

    def _list_categories(self) -> None:
        # Served from server cache — no API call needed
        self._send({'type': 'GET_CATEGORIES', 'params': ''})
        resp = self._recv()
        if resp and resp['type'] == 'CATEGORIES':
            self._display.header("All Categories")
            self._display.flat_list(resp['data'], 'name')

    def _list_areas(self) -> None:
        # Served from server cache — no API call needed
        self._send({'type': 'GET_AREAS', 'params': ''})
        resp = self._recv()
        if resp and resp['type'] == 'AREAS':
            self._display.header("All Areas")
            self._display.flat_list(resp['data'])

    def _list_ingredients(self) -> None:
        # Server caps this at 50 entries as per spec
        self._send({'type': 'GET_INGREDIENTS', 'params': ''})
        resp = self._recv()
        if resp and resp['type'] == 'INGREDIENTS':
            self._display.header("Ingredients (first 50)")
            self._display.flat_list(resp['data'])


class MainMenu(BaseMenu):
    """
    Inherits from BaseMenu.
    Top-level menu that delegates to RecipesMenu and ReferenceMenu.
    Demonstrates polymorphism: all menus share the same run() interface.
    """

    def run(self) -> None:
        # Loop until the user quits the application
        while True:
            self._display.header("Main Menu")
            choice = self._input.pick(["Browse recipes", "Reference lists", "Quit"])
            if choice == 1:
                RecipesMenu(self._sock).run()       # polymorphic call
            elif choice == 2:
                ReferenceMenu(self._sock).run()     # polymorphic call
            elif choice == 3:
                print("\n  Goodbye!")
                # Notify the server before closing so it logs the disconnect
                self._send({'type': 'QUIT', 'params': ''})
                return


# ─────────────────────────────────────────────
#  Client connection manager
# ─────────────────────────────────────────────

class RecipeClient:
    """
    Manages the socket connection and application lifecycle.
    Responsibility: connect, authenticate, launch menus, disconnect.
    """

    SERVER_ADDR = ('127.0.0.1', 12000)

    def __init__(self):
        self._sock: socket.socket | None = None

    def start(self) -> None:
        # Create a TCP socket and connect to the server
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect(self.SERVER_ADDR)

        # Send the username as a raw string (handshake step) 
        username = input("Enter your name: ")
        self._sock.sendall(username.encode('ascii'))

        # Receive the welcome message from the server
        response = self._sock.recv(1024)
        print("Server says:", response.decode('ascii'))

        # Launch the main menu and block until the user quits
        MainMenu(self._sock).run()
        self._sock.close()


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────

if __name__ == '__main__':
    RecipeClient().start()