import socket
import json
server_add = ('127.0.0.1', 12000)

cs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cs.connect(server_add)

username = input("Enter your name: ")
cs.sendall(username.encode('ascii'))

response = cs.recv(1024)
print("Server says:", response.decode('ascii'))

# ── Stage 4 & 5: Added helpers ────────────────────────────────────────
 
VALID_CATEGORIES = ['Beef', 'Chicken', 'Seafood', 'Vegetarian', 'Dessert', 'Pasta', 'Breakfast']
VALID_AREAS      = ['Italian', 'Indian', 'Mexican', 'Japanese', 'Moroccan', 'British', 'American', 'Thai']
 
def send_msg(sock, payload):
    data = json.dumps(payload).encode('utf-8')
    sock.sendall(len(data).to_bytes(4, 'big') + data)
 
def recv_msg(sock):
    raw = _recv_exact(sock, 4)
    if raw is None:
        return None
    length = int.from_bytes(raw, 'big')
    raw = _recv_exact(sock, length)
    if raw is None:
        return None
    return json.loads(raw.decode('utf-8'))
 
def _recv_exact(sock, n):
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf
 
def show_header(title):
    print(f"\n{'─' * 55}\n  {title}\n{'─' * 55}")
 
def show_recipe_list(meals):
    if not meals:
        print("  No results found.")
        return
    show_header("Results")
    for i, m in enumerate(meals, 1):
        print(f"  {i:>2}. {m['strMeal']}")
        print(f"       {m['strMealThumb']}")
 
def show_recipe_detail(d):
    if not d:
        print("  No detail available.")
        return
    show_header(d.get('strMeal', 'Recipe'))
    print(f"  Category : {d.get('strCategory', 'N/A')}")
    print(f"  Cuisine  : {d.get('strArea', 'N/A')}")
    print(f"  Tags     : {d.get('strTags') or 'N/A'}")
    print(f"  YouTube  : {d.get('strYoutube') or 'N/A'}")
    print(f"  Source   : {d.get('strSource') or 'N/A'}")
    print("\n  Ingredients:")
    for ing in d.get('ingredients', []):
        print(f"    • {ing}")
    print("\n  Instructions:")
    words, line = d.get('strInstructions', '').split(), "    "
    for w in words:
        if len(line) + len(w) + 1 > 74:
            print(line)
            line = "    " + w + " "
        else:
            line += w + " "
    if line.strip():
        print(line)
 
def show_flat_list(items, key):
    if not items:
        print("  No data.")
        return
    for i, item in enumerate(items, 1):
        print(f"  {i:>3}. {item.get(key, '')}")
 
def pick(options):
    for i, o in enumerate(options, 1):
        print(f"  {i}. {o}")
    while True:
        raw = input("\n  Choice: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw)
        print(f"  Enter a number 1-{len(options)}.")
 
def pick_from(prompt, valid):
    print(f"\n  Options: {', '.join(valid)}")
    while True:
        v = input(f"  {prompt}: ").strip()
        match = next((x for x in valid if x.lower() == v.lower()), None)
        if match:
            return match
        print(f"  Not valid. Choose from: {', '.join(valid)}")
 
def ask(prompt):
    while True:
        v = input(f"  {prompt}: ").strip()
        if v:
            return v
        print("  Cannot be empty.")
 
def drill_down(sock, meals):
    if not meals:
        return
    show_recipe_list(meals)
    print(f"\n  Enter 1-{len(meals)} for full details, or 0 to go back.")
    while True:
        raw = input("  Choice: ").strip()
        if raw == '0':
            return
        if raw.isdigit() and 1 <= int(raw) <= len(meals):
            meal_id = meals[int(raw) - 1]['idMeal']
            send_msg(sock, {'type': 'GET_DETAIL', 'params': meal_id})
            resp = recv_msg(sock)
            if resp and resp.get('type') == 'RECIPE_DETAIL':
                show_recipe_detail(resp.get('data'))
            return
        print(f"  Enter 0 or a number 1-{len(meals)}.")
 
def recipes_menu(sock):
    while True:
        show_header("Recipes Menu")
        choice = pick([
            "Search by name",
            "Filter by category",
            "Filter by area",
            "Filter by ingredient",
            "Random recipe",
            "Back to main menu"
        ])
        if choice == 1:
            kw = ask("Enter keyword")
            send_msg(sock, {'type': 'SEARCH_BY_NAME', 'params': kw})
            resp = recv_msg(sock)
            if resp and resp['type'] == 'RECIPE_LIST':
                drill_down(sock, resp['data'])
        elif choice == 2:
            cat = pick_from("Enter category", VALID_CATEGORIES)
            send_msg(sock, {'type': 'FILTER_BY_CATEGORY', 'params': cat})
            resp = recv_msg(sock)
            if resp and resp['type'] == 'RECIPE_LIST':
                drill_down(sock, resp['data'])
        elif choice == 3:
            area = pick_from("Enter area", VALID_AREAS)
            send_msg(sock, {'type': 'FILTER_BY_AREA', 'params': area})
            resp = recv_msg(sock)
            if resp and resp['type'] == 'RECIPE_LIST':
                drill_down(sock, resp['data'])
        elif choice == 4:
            ing = ask("Enter ingredient").strip().replace(' ', '_')
            send_msg(sock, {'type': 'FILTER_BY_INGREDIENT', 'params': ing})
            resp = recv_msg(sock)
            if resp and resp['type'] == 'RECIPE_LIST':
                drill_down(sock, resp['data'])
        elif choice == 5:
            send_msg(sock, {'type': 'RANDOM_RECIPE', 'params': ''})
            resp = recv_msg(sock)
            if resp and resp['type'] == 'RECIPE_DETAIL':
                show_recipe_detail(resp['data'])
        elif choice == 6:
            return
 
def reference_menu(sock):
    while True:
        show_header("Reference Menu")
        choice = pick([
            "List all categories",
            "List all areas",
            "List all ingredients",
            "Back to main menu"
        ])
        if choice == 1:
            send_msg(sock, {'type': 'GET_CATEGORIES', 'params': ''})
            resp = recv_msg(sock)
            if resp and resp['type'] == 'CATEGORIES':
                show_header("All Categories")
                show_flat_list([{'strCategory': c} for c in resp['data']], 'strCategory')
        elif choice == 2:
            send_msg(sock, {'type': 'GET_AREAS', 'params': ''})
            resp = recv_msg(sock)
            if resp and resp['type'] == 'AREAS':
                show_header("All Areas")
                show_flat_list([{'strArea': a} for a in resp['data']], 'strArea')
        elif choice == 3:
            send_msg(sock, {'type': 'GET_INGREDIENTS', 'params': ''})
            resp = recv_msg(sock)
            if resp and resp['type'] == 'INGREDIENTS':
                show_header("Ingredients (first 50)")
                show_flat_list([{'strIngredient': i} for i in resp['data']], 'strIngredient')
        elif choice == 4:
            return
 
def main_menu(sock):
    while True:
        show_header("Main Menu")
        choice = pick(["Browse recipes", "Reference lists", "Quit"])
        if choice == 1:
            recipes_menu(sock)
        elif choice == 2:
            reference_menu(sock)
        elif choice == 3:
            print("\n  Goodbye!")
            send_msg(sock, {'type': 'QUIT', 'params': ''})
            return
 
# ── Stage 4: enter the menu system ───────────────────────────────────
 
main_menu(cs)
cs.close()