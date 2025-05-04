from fastapi import FastAPI, Request
from pydantic import BaseModel
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

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
OPENWEATHER_API_KEY = retrieved_secret.value

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
    print("Received input:", input)
    # === Step 1: Convert PIN to lat/lon (via LocationIQ, Azure Maps, or similar) ===
    geo_url = f"https://nominatim.openstreetmap.org/search?postalcode={input.pin_code}&country=India&format=json"
    geo_response = requests.get(geo_url).json()

    if not geo_response:
        return {"error": "Invalid PIN code or unable to geolocate."}

    lat = geo_response[0]["lat"]
    lon = geo_response[0]["lon"]

    # === Step 2: Get 7-day weather forecast ===
    weather_url = (
        f"https://api.openweathermap.org/data/2.5/onecall"
        f"?lat={lat}&lon={lon}&exclude=current,minutely,hourly,alerts"
        f"&appid={OPENWEATHER_API_KEY}&units=metric"
    )
    weather_response = requests.get(weather_url).json()
    daily_forecast = weather_response.get("daily", [])

    if not daily_forecast:
        return {"error": "Failed to fetch weather forecast."}

    # === Step 3: Basic Risk Detection Rules ===
    detected_risks = []
    recommendations = []

    if input.crop_name.lower() == "rice":
        for day in daily_forecast[:7]:
            rain = day.get("rain", 0)
            temp_max = day["temp"]["max"]
            if rain < 5:
                detected_risks.append("Drought Risk")
                recommendations.append("Apply irrigation to avoid water stress.")
            if temp_max > 38:
                detected_risks.append("Heat Stress Risk")
                recommendations.append("Provide shade or increase water supply.")

    summary = f"{daily_forecast[0]['weather'][0]['description'].capitalize()}, Max Temp: {daily_forecast[0]['temp']['max']}°C"

    return {
        "location": f"{input.pin_code} (India)",
        "crop": input.crop_name,
        "forecast_summary": summary,
        "detected_risks": list(set(detected_risks)),  # remove duplicates
        "recommendations": list(set(recommendations)),
    }
