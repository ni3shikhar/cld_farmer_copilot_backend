from fastapi import FastAPI, Request
from pydantic import BaseModel
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from fastapi.responses import JSONResponse

import os
import requests

app = FastAPI()

# Key Vault URL (replace with your actual Key Vault name)
KEY_VAULT_URL = "https://kv-cld-farmer-poc.vault.azure.net/"

# Use default credential (works for Azure App Service or local via `az login`)
credential = DefaultAzureCredential()
client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)

# Fetch the secret
retrieved_secret = client.get_secret("OpenWeatherAPIKey")
WEATHER_API_KEY = retrieved_secret.value

# Replace with your actual API key
#OPENWEATHER_API_KEY = "99e6a7cc36fdd82d597fe353e74771f1"

# === Request & Response Schemas ===

class UserInput(BaseModel):
    pin_code: str
    crop_name: str

@app.get("/")
def read_root():
    return {"message": "Farmer Copilot API running"}

@app.post("/analyze")
def analyze(input: UserInput):
    try:
        # === Step 1: Get weather forecast using PIN code ===
        url = f"https://api.weatherapi.com/v1/forecast.json?key={WEATHER_API_KEY}&q={input.pin_code}&days=7"

        response = requests.get(url)
        if response.status_code != 200:
            return JSONResponse(status_code=502, content={"error": "WeatherAPI.com request failed", "details": response.text})

        data = response.json()

        forecast_days = data.get("forecast", {}).get("forecastday", [])
        if not forecast_days:
            return {"error": "No forecast data returned."}

        # === Step 2: Run risk detection rules ===
        detected_risks = []
        recommendations = []

        if input.crop_name.lower() == "rice":
            for day in forecast_days:
                date = day["date"]
                day_data = day["day"]
                rain_mm = day_data["totalprecip_mm"]
                temp_max = day_data["maxtemp_c"]

                if rain_mm < 5:
                    detected_risks.append(f"Drought Risk on {date}")
                    recommendations.append("Apply irrigation to avoid water stress.")
                if temp_max > 38:
                    detected_risks.append(f"Heat Stress Risk on {date}")
                    recommendations.append("Provide shade or increase water supply.")

        # === Step 3: Generate summary for Day 1 ===
        today = forecast_days[0]["day"]
        summary = f"{forecast_days[0]['date']}: {today['condition']['text']}, Max Temp: {today['maxtemp_c']}°C"

        return {
            "location": data["location"]["name"],
            "region": data["location"]["region"],
            "crop": input.crop_name,
            "forecast_summary": summary,
            "detected_risks": list(set(detected_risks)),
            "recommendations": list(set(recommendations))
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Internal Server Error", "detail": str(e)})
