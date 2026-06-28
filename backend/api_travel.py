import httpx
import os
from typing import List, Dict

WEATHER_KEY = os.getenv("OPENWEATHER_KEY")
GEOAPIFY_KEY = os.getenv("GEOAPIFY_KEY") 
UNSPLASH_KEY = os.getenv("UNSPLASH_KEY")

async def buscar_clima(cidade: str) -> Dict:
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "q": cidade,
        "appid": WEATHER_KEY,
        "units": "metric",
        "lang": "pt_br",
        "cnt": 5
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    
    dias = []
    for item in data["list"]:
        dias.append({
            "data": item["dt_txt"][:10],
            "temp": round(item["main"]["temp"]),
            "desc": item["weather"][0]["description"]
        })
    return {"cidade": data["city"]["name"], "previsao": dias}

async def buscar_coords(cidade: str) -> tuple:
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": cidade, "format": "json", "limit": 1}
    headers = {"User-Agent": "vacation_ai"}
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params, headers=headers)
        data = r.json()
    if not data:
        return None, None
    return float(data[0]["lat"]), float(data[0]["lon"])

async def buscar_pontos_turisticos(cidade: str) -> List[Dict]:
    lat, lon = await buscar_coords(cidade)
    if not lat:
        return []
    
    url = "https://api.geoapify.com/v2/places"
    params = {
        "categories": "tourism.sights",
        "filter": f"circle:{lon},{lat},5000",
        "limit": 5,
        "apiKey": GEOAPIFY_KEY
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        data = r.json()
    
    pontos = []
    for p in data.get("features", []):
        nome = p["properties"].get("name")
        if nome:
            pontos.append({"nome": nome, "tipo": "Ponto Turístico"})
    return pontos

async def buscar_hoteis(cidade: str) -> List[Dict]:
    lat, lon = await buscar_coords(cidade)
    if not lat:
        return []
    
    url = "https://api.geoapify.com/v2/places"
    params = {
        "categories": "accommodation.hotel",
        "filter": f"circle:{lon},{lat},5000",
        "limit": 3,
        "apiKey": GEOAPIFY_KEY
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        data = r.json()
    
    hoteis = []
    for p in data.get("features", []):
        nome = p["properties"].get("name")
        if nome:
            hoteis.append({"nome": nome})
    return hoteis

async def buscar_foto(cidade: str) -> str:
    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": f"{cidade} city",
        "per_page": 1,
        "client_id": UNSPLASH_KEY
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        data = r.json()
    
    if data["results"]:
        return data["results"][0]["urls"]["regular"]
    return ""