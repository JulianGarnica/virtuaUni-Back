import os
import mysql.connector
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import uvicorn
from dotenv import load_dotenv
from datetime import datetime

# Cargar las variables de entorno
load_dotenv()

# Conexión a la base de datos MySQL
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# App de FastAPI
app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Chat-ID"],  # Asegúrate de permitir el encabezado
    expose_headers=["X-Chat-ID"]
)

default_prompt = "Las respuestas que das son cortas y claras, eres una IA de la universidad UNIMINUTO de la sede de Zipaquirá, por lo cual, sólo puedes dar información relacionada con la UNIMINUTO de la sede de Zipaquirá sin nombrar ninguna otra universidad. Te llamas Minuni, siempre que des respuestas, lo vas a hacer de una forma amigable también usando emojis."

# Azure OpenAI Authentication
endpoint = os.environ["AZURE_OPEN_AI_ENDPOINT"]
api_key = os.environ["AZURE_OPEN_AI_API_KEY"]

client = openai.AsyncAzureOpenAI(
    azure_endpoint=endpoint,
    api_key=api_key,
    api_version="2023-09-01-preview"
)

# Azure OpenAI Model Configuration
deployment = os.environ["AZURE_OPEN_AI_DEPLOYMENT_MODEL"]
temperature = 0.7

# Prompt
class Prompt(BaseModel):
    input: str
    idChat: int = None  # Hacer opcional el idChat
    nombre: str
    email: str
    default: str = default_prompt
class saveMessage(BaseModel):
    idChat: int
    content: str
class Rating(BaseModel):
    idChat: int
    calificacion: int  # Debe estar entre 1 y 5
    comentario: str = None  # Comentario opcional


def combine_prompts(user_prompt: str, default_prompt: str) -> str:
    return f"{default_prompt}\n\n{user_prompt}"

# Generar flujo de mensajes
async def stream_processor(response, id_chat):
    async for chunk in response:
        if len(chunk.choices) > 0:
            delta = chunk.choices[0].delta
            if delta.content:
                
                yield delta.content

# Guardar mensaje en la base de datos
def save_message_to_db(id_chat, message_content, idTipoMensajero=2):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        INSERT INTO Mensajes (idChat, idTipoMensajero, mensaje, fecha)
        VALUES (%s, %s, %s, %s)
    """
    cursor.execute(query, (id_chat, idTipoMensajero, message_content, datetime.now()))
    conn.commit()
    cursor.close()
    conn.close()

# Crear un nuevo chat en la base de datos
def create_new_chat(nombreEstudiante=None, correoEstudiante=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        INSERT INTO Chats (nombreEstudiante, correoEstudiante, fechaCreacion)
        VALUES (%s, %s, %s)
    """
    cursor.execute(query, (nombreEstudiante, correoEstudiante, datetime.now()))  # Asumiendo que idMensajero puede ser nulo
    conn.commit()
    new_chat_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return new_chat_id

# Recuperar historial de mensajes de la base de datos
def get_chat_history(id_chat):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT mensaje FROM Mensajes WHERE idChat = %s ORDER BY fecha ASC
    """
    cursor.execute(query, (id_chat,))
    messages = cursor.fetchall()
    cursor.close()
    conn.close()
    return [{"role": "user", "content": message[0]} for message in messages]

@app.get("/status")
def status():
    return "ok"

@app.post("/api/saveMessage")
def save_message(saveMessage: saveMessage):
    # Guardar el mensaje en la base de datos
    save_message_to_db(saveMessage.idChat, saveMessage.content)

# API Endpoint para el chat
@app.post("/api/stream")
async def stream(prompt: Prompt):
    # Crear un nuevo chat si no se proporciona idChat
    if prompt.idChat is None:
        prompt.idChat = create_new_chat(prompt.nombre, prompt.email)

    # Obtener el historial de la conversación
    chat_history = get_chat_history(prompt.idChat)

    # Añadir el mensaje actual del usuario
    chat_history.append({"role": "user", "content": prompt.input})
    save_message_to_db(prompt.idChat, prompt.input, 1)

    # Generar la respuesta de la IA
    azure_open_ai_response = await client.chat.completions.create(
        model=deployment,
        temperature=temperature,
        messages=[{"role": "system", "content": default_prompt}] + chat_history,
        stream=True
    )

    # Retornar la respuesta junto con el idChat
    return StreamingResponse(
        stream_processor(azure_open_ai_response, prompt.idChat),
        media_type="text/event-stream",
        headers={"X-Chat-ID": str(prompt.idChat)}  # Devolver el idChat en el header
    )

# Endpoint para enviar calificaciones
@app.post("/api/rate")
async def rate_messenger(rating: Rating):
    if rating.calificacion < 1 or rating.calificacion > 5:
        return JSONResponse(status_code=400, content={"message": "La calificación debe estar entre 1 y 5"})

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO Calificaciones (idChat, calificacion, comentario, fecha)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (rating.idChat, rating.calificacion, rating.comentario, datetime.now()))
        conn.commit()
        cursor.close()
        conn.close()
        return JSONResponse(status_code=200, content={"message": "Calificación guardada exitosamente"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Error al guardar la calificación: {str(e)}"})

# Endpoint para obtener calificaciones con filtros
@app.get("/api/ratings")
async def get_ratings(idChat: int = None, min_calificacion: int = None, max_calificacion: int = None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM Calificaciones WHERE 1=1"
        params = []

        if idChat is not None:
            query += " AND idChat = %s"
            params.append(idChat)
        if min_calificacion is not None:
            query += " AND calificacion >= %s"
            params.append(min_calificacion)
        if max_calificacion is not None:
            query += " AND calificacion <= %s"
            params.append(max_calificacion)

        cursor.execute(query, params)
        ratings = cursor.fetchall()
        cursor.close()
        conn.close()
        return JSONResponse(status_code=200, content=ratings)
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Error al obtener las calificaciones: {str(e)}"})

# Endpoint para obtener historial de mensajes con filtros
@app.get("/api/chatHistory")
async def get_chat_history_filtered(idChat: int = None, start_date: str = None, end_date: str = None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM Mensajes WHERE 1=1"
        params = []

        if idChat is not None:
            query += " AND idChat = %s"
            params.append(idChat)
        if start_date is not None:
            query += " AND fecha >= %s"
            params.append(start_date)
        if end_date is not None:
            query += " AND fecha <= %s"
            params.append(end_date)

        cursor.execute(query, params)
        messages = cursor.fetchall()
        cursor.close()
        conn.close()
        return JSONResponse(status_code=200, content=messages)
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Error al obtener el historial de mensajes: {str(e)}"})

"""
if __name__ == "__main__":
    uvicorn.run("main:app", port=8000)
"""