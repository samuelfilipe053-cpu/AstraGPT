import requests

url = "https://openrouter.ai/api/v1/models"

response = requests.get(url)

if response.status_code == 200:
    models = response.json()["data"]

    print("\n=== MODELOS DISPONÍVEIS ===\n")

    for model in models:
        pricing = model.get("pricing", {})

        if pricing.get("prompt") == "0" and pricing.get("completion") == "0":
            print(f"🟢 {model['id']}")

    print("\n=== FIM ===")
else:
    print("❌ Erro:", response.status_code)