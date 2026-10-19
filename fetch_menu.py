import requests
import json, os
import datetime

hall = "gordon-avenue-market"
meal = "lunch"
year, month, day = 2026, 10, 19
target_date = f"{year}-{month:02d}-{day:02d}"

url = (
    "https://wisc-housingdining.api.nutrislice.com/menu/api/weeks/school/"
    f"{hall}/menu-type/{meal}/{year}/{month:02d}/{day:02d}/"
)

response = requests.get(url)


if response.status_code == 200:
    data= response.json()
    
else:
    print("failed to recieve data")





today =None
for d in data["days"]:
    if d.get("date") == target_date:
        today = d
        break

if today is None:
     print("no menu")
     exit()

items = []

for item in today["menu_items"]:
        print
        food = item.get("food")
        if food is None:
            continue  # headings like "Build Your Own" have no food

#storing labels of the food
        iconList =[]
        icons = food.get("icons")
        for icon in icons.get("food_icons"):
             iconList.append(icon.get("synced_name"))

#storing nutrition info of each item
        nutrition = food.get("rounded_nutrition_info") or {}

        items.append({
            "name" : food.get("name"),
            "calories" : nutrition.get("calories") or 0,
            "protein": nutrition.get("g_protein") or 0,
            "fats" : nutrition.get("g_fat") or 0,
            "carbs" : nutrition.get("g_carbs") or 0,
            "sugar" : (nutrition.get("g_sugar") or 0.0) + (nutrition.get("g_added_sugar") or 0.0),
            "tags" : iconList,
        })


with open(f"menu_{target_date}.json","w") as f:
     json.dump(items, f ,indent=2)

with open(f"menu_{target_date}.json", "r") as f:
    items = json.load(f)
print(len(items), "items loaded")
for i in range(len(items)):
    print(items[i].get("name"))
