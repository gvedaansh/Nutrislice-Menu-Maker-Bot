import json, os
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
import fetch_menu

load_dotenv()
key = os.getenv("GEMINI_API_KEY")

client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)



# the exact shape we want back from Gemini
class Planner(BaseModel):
    items: list[str]
    reason: str
    nutrition: str

menu, menu_path = fetch_menu.fetchFromUser()
if not menu:
    raise SystemExit

user_prompt = input("What kind of meal do you want? ")

system_msg = (
    "You are a meal planner for a school or college dining hall. "
    "make the meal plan like a proffesional nutritionist with PFC method"
    "Only choose items from the menu provided, using their exact names. "
    "Respect every dietary restriction using each item's tags: "
    "diet tags like Vegetarian, Vegan, Halal mean the item IS that; "
    "allergen tags like Dairy, Wheat, Egg mean the item CONTAINS that. "
    "Vegan items count as vegetarian. "
    "Tag names can vary in spelling or case between schools, and some items may have no tags; "
    "if a restriction can't be confirmed from the tags, avoid that item. "
    "When an item lists ingredients, use them too to check allergies and restrictions. "
    "Each item's 'nutrition' has every nutrient the school listed (units at the end of the name, "
    "e.g. sodium_mg); use it for requests like low sodium or high fiber."

)

completion = client.beta.chat.completions.parse(
    model="gemini-3.8-flash",
    reasoning_effort="low",
    messages=[
        {"role": "system", "content": system_msg},
        {"role": "user", "content": f"Request: {user_prompt}\n\nMenu:\n{json.dumps(menu)}"},
    ],
    response_format=Planner,
    temperature=0.9,
)

plan = completion.choices[0].message.parsed

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

