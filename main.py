from fastapi import FastAPI, Request
from pydantic import BaseModel
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import os
import requests

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or replace "*" with your static web app URL
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# === Crop Risk Profiles ===
CROP_RISK_PROFILES = {
    "rice": {
        "min_rain_mm": 5,
        "max_temp_c": 38,
        "min_temp_c": 20,
        "max_wind_kmph": 40,
        "max_humidity": 90
    },
    "wheat": {
        "min_rain_mm": 2,
        "max_temp_c": 32,
        "min_temp_c": 10,
        "max_wind_kmph": 35,
        "max_humidity": 85
    },
    "maize": {
        "min_rain_mm": 3,
        "max_temp_c": 35,
        "min_temp_c": 18,
        "max_wind_kmph": 45,
        "max_humidity": 88
    },
    "sugarcane": {
        "min_rain_mm": 4,
        "max_temp_c": 40,
        "min_temp_c": 15,
        "max_wind_kmph": 50,
        "max_humidity": 92
    }
}
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
        # Step 1: Get lat/lon from PIN
        geo_url = f"https://nominatim.openstreetmap.org/search?postalcode={input.pin_code}&country=India&format=json"
        headers = {"User-Agent": "FarmerCopilotApp/1.0"}
        geo_response = requests.get(geo_url, headers=headers).json()

        if not geo_response:
            return JSONResponse(status_code=400, content={"error": "Invalid PIN code or location not found."})

        lat = geo_response[0]["lat"]
        lon = geo_response[0]["lon"]

        # Step 2: Get 7-day forecast from WeatherAPI
        weather_url = f"https://api.weatherapi.com/v1/forecast.json?key={WEATHER_API_KEY}&q={lat},{lon}&days=7"
        weather_response = requests.get(weather_url).json()
        forecast_days = weather_response.get("forecast", {}).get("forecastday", [])

        if not forecast_days:
            return JSONResponse(status_code=502, content={"error": "Failed to fetch weather forecast."})

        profile = CROP_RISK_PROFILES.get(input.crop_name.lower())
        if not profile:
            return JSONResponse(status_code=400, content={"error": f"Crop '{input.crop_name}' is not supported."})

        detected_risks = []
        recommendations = []

        # Step 3: Risk Detection Logic
        for day in forecast_days:
            date = day["date"]
            weather = day["day"]

            rain = weather.get("totalprecip_mm", 0)
            temp_max = weather.get("maxtemp_c", 0)
            temp_min = weather.get("mintemp_c", 0)
            wind = weather.get("maxwind_kph", 0)
            humidity = weather.get("avghumidity", 0)

            # Drought
            if rain < profile["min_rain_mm"]:
                detected_risks.append(f"Drought risk on {date}")
                recommendations.append("Irrigate or delay sowing.")

            # Flood
            if rain > 80:
                detected_risks.append(f"Flood risk on {date}")
                recommendations.append("Ensure drainage. Avoid fertilizer application.")

            # Heat stress
            if temp_max > profile["max_temp_c"]:
                detected_risks.append(f"Heat stress on {date}")
                recommendations.append("Provide shade or irrigate during cooler hours.")

            # Cold/frost
            if temp_min < profile["min_temp_c"]:
                detected_risks.append(f"Cold/frost risk on {date}")
                recommendations.append("Use mulch or protective covers for seedlings.")

            # Wind
            if wind > profile["max_wind_kmph"]:
                detected_risks.append(f"Wind damage risk on {date}")
                recommendations.append("Stake tall crops or add windbreaks.")

            # Pest/disease (humidity + heat)
            if humidity > profile["max_humidity"] and temp_max > 30:
                detected_risks.append(f"Pest/disease risk on {date}")
                recommendations.append("Inspect for pests/fungi. Avoid late irrigation.")

        # Step 4: Forecast summary
        today = forecast_days[0]
        summary = f"{today['date']}: {today['day']['condition']['text']}, Max Temp: {today['day']['maxtemp_c']}°C"

        return {
            "location": weather_response["location"]["name"],
            "region": weather_response["location"]["region"],
            "crop": input.crop_name,
            "forecast_summary": summary,
            "detected_risks": list(set(detected_risks)),
            "recommendations": list(set(recommendations))
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Internal Server Error", "detail": str(e)})
