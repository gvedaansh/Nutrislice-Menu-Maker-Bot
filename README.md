# NutriSlice Menu Maker

Plans a meal from your dining hall's menu. Works with any school or college that uses
[Nutrislice](https://nutrislice.com) for its menus, and with an AI provider of your choice.

You paste your school's Nutrislice menu link, say what kind of meal you want
("high protein, no dairy"), and it picks items from that day's menu and adds up the nutrition.

## Setup

1. Install Python 3.10 or newer.
2. Install the packages:
   ```
   pip install -r requirements.txt
   ```
3. Get an API key from any of these providers:

   | Provider | Where to get a key | Key starts with |
   |---|---|---|
   | Google Gemini (has a free tier) | aistudio.google.com | `AIza` |
   | OpenAI | platform.openai.com | `sk-` |
   | Anthropic Claude | console.anthropic.com | `sk-ant-` |
   | OpenRouter (many models, one key) | openrouter.ai | `sk-or-` |
   | Groq | console.groq.com | `gsk_` |
   | xAI Grok | console.x.ai | `xai-` |
   | Mistral | console.mistral.ai | |
   | DeepSeek | platform.deepseek.com | |
   | Ollama (runs on your computer, no key) | ollama.com | |

   Other providers that accept OpenAI-style requests work too: choose "Other" during setup
   and enter their web address.

## Run it

```
python Planner.py
```

The first time, it asks for your API key, guesses the provider from it, and lets you pick a model.
Your choices are saved in a `.env` file on your computer. Git ignores it, so your key
is never uploaded.

To change the key, provider or model later:

```
python Planner.py --setup
```

You can also fill in `.env` yourself. Copy `.env.example` to `.env` and follow the comments in it.

## Finding your menu link

Open your school's Nutrislice menu in a browser, go to the dining hall and meal you want, and copy the address.
It looks like:

```
https://wisc-housingdining.nutrislice.com/menu/gordon-avenue-market/dinner/2026-10-06
```

A shorter link like `https://yourschool.nutrislice.com/menu` also works: the program lists the
dining halls and meals for you to choose from. If the link has no date, it uses today.

To only download a menu without planning a meal:

```
python fetch_menu.py
```

This saves the menu as a JSON file with every nutrient, ingredient list and food label the school provides.
