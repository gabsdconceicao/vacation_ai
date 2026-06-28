from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import markdown2
import httpx
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RoteiroRequest(BaseModel):
    message: str

# Caminho absoluto pro frontend
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

client_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

@app.get("/")
async def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

async def buscar_coordenadas(cidade: str):
    url = f"https://nominatim.openstreetmap.org/search"
    params = {"q": cidade, "format": "json", "limit": 1}
    headers = {"User-Agent": "VacationAI/1.0"}
    
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params, headers=headers)
        data = r.json()
        if not data:
            raise HTTPException(status_code=404, detail="Cidade não encontrada")
        return float(data[0]["lat"]), float(data[0]["lon"]), data[0]["display_name"]

async def buscar_clima(lat: float, lon: float):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,weathercode",
        "timezone": "auto",
        "forecast_days": 7
    }
    
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        return r.json()

def gerar_resposta_ia(pergunta_usuario: str, cidade: str, clima_data: dict):
    clima_texto = f"Previsão dos próximos dias para {cidade}: "
    for i in range(3):
        dia = clima_data["daily"]["time"][i]
        temp_max = round(clima_data["daily"]["temperature_2m_max"][i])
        temp_min = round(clima_data["daily"]["temperature_2m_min"][i])
        clima_texto += f"{dia}: {temp_min}°C a {temp_max}°C. "

    prompt = f"""
    Você é um agente de viagens especialista em turismo mundial. O usuário perguntou: "{pergunta_usuario}"
    
    Dados climáticos reais de {cidade}:
    {clima_texto}
    
    Responda em português de forma natural, completa e específica. Se o usuário mencionou um mês/ano específico como "Janeiro de 2027", 
    explique:
    1. Qual é a estação do ano nesse mês em {cidade}
    2. Temperatura média esperada para essa época
    3. O que levar na mala
    4. Melhores regiões/bairros para se hospedar, com justificativa
    5. Top 3 hotéis REAIS com nome e bairro
    6. Top 5 passeios/atrações recomendados para essa época, explicando por que são bons nesse mês
    7. Dicas extras: transporte, moeda, costumes locais, o que evitar
    
    Seja específico. Use nomes reais de hotéis, restaurantes e atrações. Não invente.
    Use títulos em negrito com ** para destacar as seções.
    """

    chat_completion = client_groq.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        temperature=0.7,
        max_tokens=1500
    )
    
    resposta_markdown = chat_completion.choices[0].message.content
    resposta_html = markdown2.markdown(resposta_markdown)
    
    return resposta_html

@app.post("/api/roteiro")
async def criar_roteiro(request: RoteiroRequest):
    pergunta = request.message.strip()
    
    if not pergunta:
        raise HTTPException(status_code=400, detail="Digite sua pergunta")
    
    try:
        extracao = client_groq.chat.completions.create(
            messages=[{
                "role": "user", 
                "content": f"Extraia APENAS o nome da cidade da frase: '{pergunta}'. Se houver país, inclua. Responda só 'Cidade, País' ou só 'Cidade', nada mais. Exemplo: 'Paris' ou 'Rio de Janeiro, Brasil'"
            }],
            model="llama-3.1-8b-instant",
            temperature=0,
            max_tokens=50
        )
        cidade = extracao.choices[0].message.content.strip()
        
        lat, lon, nome_completo = await buscar_coordenadas(cidade)
        clima_data = await buscar_clima(lat, lon)
        
        resposta_ia = gerar_resposta_ia(pergunta, nome_completo, clima_data)
        
        foto_url = f"https://source.unsplash.com/800x400/?{cidade},travel,city"
        
        return {
            "cidade": nome_completo,
            "foto_url": foto_url,
            "resposta_completa": resposta_ia,
            "clima": clima_data
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

# ADICIONA ISSO AQUI NO FINAL
if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)