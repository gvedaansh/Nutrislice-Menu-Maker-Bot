import json, sys
from pydantic import BaseModel
import fetch_menu
import llm


# the exact shape we want back from the AI
class Planner(BaseModel):
    items: list[str]
    reason: str
    nutrition: str

# run "python Planner.py --setup" to change the API key, provider or model
try:
    settings = llm.getSettings(force_setup="--setup" in sys.argv)
except llm.LLMError as e:
    print(e)
    raise SystemExit

menu, menu_path = fetch_menu.fetchFromUser()
if not menu:
    raise SystemExit

user_prompt = input("What kind of meal do you want? ")

system_msg = (
    "You are a meal planner for a school or college dining hall. "
    "make the meal plan like a proffesional nutritionist with PFC method. "
    "Only choose items from the menu provided, using their exact names. "
    "Respect every dietary restriction using each item's tags: "
    "diet tags like Vegetarian, Vegan, Halal mean the item IS that; "
    "allergen tags like Milk or Dairy, Wheat, Egg mean the item CONTAINS that "
    "(a Milk tag means the item has dairy). "
    "Vegan items count as vegetarian. "
    "Tag names can vary in spelling or case between schools, and some items may have no tags; "
    "if a restriction can't be confirmed from the tags, avoid that item. "
    "When an item lists ingredients, use them too to check allergies and restrictions. "
    "Each item's 'nutrition' has every nutrient the school listed (units at the end of the name, "
    "e.g. sodium_mg); use it for requests like low sodium or high fiber."

)

print("Planning your meal...")
try:
    plan = llm.askJson(
        settings,
        system_msg,
        f"Request: {user_prompt}\n\nMenu:\n{json.dumps(menu)}",
        Planner,
    )
except llm.LLMError as e:
    print(e)
    raise SystemExit

# adds up every nutrient listed for the chosen items
totals = {}
print("\nYour meal:")
for name in plan.items:
    match = next((m for m in menu if m["name"] == name), None)
    if match is None:
        print(f"  (skipped '{name}', not on the menu)")
        continue
    serving = match.get("serving_size")
    print(f"{name}" + (f" ({serving})" if serving else ""))
    for key, value in match.get("nutrition", {}).items():
        totals[key] = totals.get(key, 0) + value

print("\nTotals:")
for key, value in totals.items():
    print(f"  {key.replace('_', ' ')}: {round(value, 1)}")
print("Why:", plan.reason)

