import requests
import json, os
import datetime
from urllib.parse import urlparse

CONFIG_FILE = "config.json"


class MenuError(Exception):
    pass


# Turns a pasted Nutrislice link into its parts.
# e.g. https://wisc-housingdining.nutrislice.com/menu/gordon-avenue-market/dinner/2026-10-06
#   -> district="wisc-housingdining", school="gordon-avenue-market", meal="dinner", date=2026-10-06
# School, meal and date are None when the link stops early.
def parseLink(link):
    link = link.strip()
    if "://" not in link:
        link = "https://" + link
    parsed = urlparse(link)
    host = (parsed.hostname or "").lower()

    if not host.endswith(".nutrislice.com"):
        raise MenuError("That doesn't look like a Nutrislice link.")

    district = host[: -len(".nutrislice.com")]
    if district.endswith(".api"):
        district = district[: -len(".api")]
    if not district:
        raise MenuError("Couldn't find the school name in that link.")

    parts = [p for p in parsed.path.split("/") if p]
    if "menu" in parts:
        parts = parts[parts.index("menu") + 1:]
    else:
        parts = []

    school = parts[0] if len(parts) > 0 else None
    meal = parts[1] if len(parts) > 1 else None
    date = None
    if len(parts) > 2:
        try:
            date = datetime.date.fromisoformat(parts[2])
        except ValueError:
            date = None

    return {"district": district, "school": school, "meal": meal, "date": date}


# Lists every dining hall / school in a district, with the meals each one serves.
def getSchools(district):
    url = f"https://{district}.api.nutrislice.com/menu/api/schools/"
    try:
        response = requests.get(url, timeout=15)
    except requests.RequestException:
        raise MenuError(f"Couldn't find '{district}' on Nutrislice. Check the link and your internet connection.")
    if response.status_code != 200:
        raise MenuError(f"Nutrislice doesn't know a school called '{district}'. Check the link.")
    return response.json()


# Asks the user to pick one option from a list. Returns the chosen option.
def choose(options, label):
    print(f"\nPick a {label}:")
    for i, opt in enumerate(options, start=1):
        print(f"  {i}. {opt['name']}")
    while True:
        answer = input(f"Enter a number (1-{len(options)}): ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1]
        print("Not a valid choice, try again.")


# Fills in anything the link was missing by asking the user,
# and checks that the hall and meal really exist.
def resolveLink(link):
    info = parseLink(link)
    # only offer halls that actually have menus posted
    schools = [s for s in getSchools(info["district"]) if s.get("active_menu_types")]
    if not schools:
        raise MenuError("This school hasn't posted any menus on Nutrislice.")

    if info["school"]:
        school = next((s for s in schools if s["slug"] == info["school"]), None)
        if school is None:
            print(f"Couldn't find '{info['school']}' at this school.")
            school = choose(schools, "dining hall")
    elif len(schools) == 1:
        school = schools[0]
    else:
        school = choose(schools, "dining hall")

    meals = school.get("active_menu_types") or []
    if not meals:
        raise MenuError(f"{school['name']} has no menus right now.")

    if info["meal"]:
        meal = next((m for m in meals if m["slug"] == info["meal"]), None)
        if meal is None:
            print(f"Couldn't find the meal '{info['meal']}' at {school['name']}.")
            meal = choose(meals, "meal")
    elif len(meals) == 1:
        meal = meals[0]
    else:
        meal = choose(meals, "meal")

    date = info["date"] or datetime.date.today()

    return {
        "district": info["district"],
        "school": school["slug"],
        "schoolName": school["name"],
        "meal": meal["slug"],
        "date": date,
    }


# Units Nutrislice puts at the front of its field names, e.g. "mg_sodium".
UNIT_PREFIXES = ("mcg", "mg", "g", "iu", "re")


# Keeps every nutrition field the school listed, with the unit moved to the end
# so it reads naturally: "g_saturated_fat" -> "saturated_fat_g".
# Fields the school left blank (null) are dropped.
def readableNutrition(nutrition):
    result = {}
    for key, value in nutrition.items():
        if value is None:
            continue
        prefix, _, rest = key.partition("_")
        if prefix in UNIT_PREFIXES and rest:
            key = f"{rest}_{prefix}"
        result[key] = value
    return result


def servingSize(food, item):
    info = food.get("serving_size_info") or {}
    amount = info.get("serving_size_amount") or item.get("serving_size_amount")
    unit = info.get("serving_size_unit") or item.get("serving_size_unit")
    return " ".join(str(x) for x in (amount, unit) if x)


# Downloads one day's menu and returns a list of foods with their nutrition.
def getMenu(district, school, meal, date):
    url = (
        f"https://{district}.api.nutrislice.com/menu/api/weeks/school/"
        f"{school}/menu-type/{meal}/{date.year}/{date.month:02d}/{date.day:02d}/"
    )
    try:
        response = requests.get(url, timeout=15)
    except requests.RequestException:
        raise MenuError("Couldn't reach Nutrislice. Check your internet connection.")
    if response.status_code != 200:
        raise MenuError("Failed to receive the menu from Nutrislice.")

    data = response.json()
    target_date = date.isoformat()

    today = None
    for d in data.get("days", []):
        if d.get("date") == target_date:
            today = d
            break

    if today is None or not today.get("menu_items"):
        raise MenuError(f"No menu posted for {target_date}.")

    items = []
    skipped = 0
    station = None

    for item in today["menu_items"]:
        # station headers (e.g. "Grill") come before the foods served there
        if item.get("is_station_header") or item.get("is_section_title"):
            station = (item.get("text") or "").strip() or station
            continue

        food = item.get("food")
        if food is None:
            continue  # headings like "Build Your Own" have no food

        # storing labels of the food (some schools have none)
        icons = food.get("icons") or {}
        iconList = []
        for icon in icons.get("food_icons") or []:
            name = icon.get("synced_name") or icon.get("name")
            if name:
                iconList.append(name)

        # storing nutrition info of each item
        nutrition = food.get("rounded_nutrition_info") or {}
        if nutrition.get("calories") is None:
            skipped += 1
            continue
        items.append({
            "name": food.get("name"),
            "calories": nutrition.get("calories") or 0,
            "protein": nutrition.get("g_protein") or 0,
            "fats": nutrition.get("g_fat") or 0,
            "carbs": nutrition.get("g_carbs") or 0,
            "sugar": nutrition.get("g_sugar") or 0.0,
            "tags": iconList,
            "nutrition": readableNutrition(nutrition),
            "serving_size": servingSize(food, item),
            "ingredients": (food.get("ingredients") or food.get("synced_ingredients") or "").strip(),
            "description": (food.get("description") or "").strip(),
            "category": food.get("food_category") or "",
            "station": station or "",
        })

    if skipped:
        print(f"({skipped} items left out because the school didn't list their nutrition)")
    if not items:
        raise MenuError("None of the foods on this menu have nutrition info.")

    return items


def menuFilename(district, school, meal, date):
    return f"menu_{district}_{school}_{meal}_{date.isoformat()}.json"


def saveMenu(items, district, school, meal, date):
    path = menuFilename(district, school, meal, date)
    with open(path, "w") as f:
        json.dump(items, f, indent=2)
    return path


def loadLastLink():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f).get("lastLink")
    except (OSError, ValueError):
        return None


def saveLastLink(link):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"lastLink": link}, f, indent=2)


# Asks for a link, then fetches and saves the menu.
# Returns (items, path), or (None, None) if something went wrong.
def fetchFromUser():
    last = loadLastLink()
    prompt = "Paste your Nutrislice menu link"
    if last:
        prompt += " (or press Enter to reuse the last one)"
    link = input(prompt + ": ").strip() or last
    if not link:
        print("No link given.")
        return None, None

    try:
        choice = resolveLink(link)
        print(f"\nGetting {choice['meal']} at {choice['schoolName']} for {choice['date'].isoformat()}...")
        items = getMenu(choice["district"], choice["school"], choice["meal"], choice["date"])
    except MenuError as e:
        print(e)
        return None, None

    saveLastLink(link)
    path = saveMenu(items, choice["district"], choice["school"], choice["meal"], choice["date"])
    return items, path


if __name__ == "__main__":
    fetchFromUser()
