import os
import time
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
default_prompt = "Las respuestas que das son cortas y claras, eres una IA de la universidad UNIMINUTO de la sede de Zipaquirá, por lo cual, sólo puedes dar información relacionada con la UNIMINUTO de la sede de Zipaquirá sin nombrar ninguna otra universidad. Te llamas Minuni, siempre que des respuestas, lo vas a hacer de una forma amigable también usando emojis."

# Azure OpenAI Authentication
endpoint = os.environ["AZURE_OPEN_AI_ENDPOINT"]
api_key = os.environ["AZURE_OPEN_AI_API_KEY"]
assistantId = os.environ["AZURE_OPEN_AI_ASSISTANT_ID"]
deployment = os.environ["AZURE_OPEN_AI_DEPLOYMENT_MODEL"]
temperature = 0.7

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



client = openai.AsyncAzureOpenAI(
    azure_endpoint=endpoint,
    api_key=api_key,
    api_version="2024-03-01-preview"
)
async def retrieve_assistant():
    assistant = await client.beta.assistants.retrieve(assistantId)

    return assistant




# Azure OpenAI Model Configuration


# Prompt
class Prompt(BaseModel):
    input: str
    idChat: str = None  # Hacer opcional el idChat
    idRun: str = None  # Hacer opcional el idRun
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
async def create_new_chat(thread, nombreEstudiante=None, correoEstudiante=None):
    
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        INSERT INTO Chats (idChat, nombreEstudiante, correoEstudiante, fechaCreacion)
        VALUES (%s, %s, %s, %s)
    """
    cursor.execute(query, (thread.id, nombreEstudiante, correoEstudiante, datetime.now()))  # Asumiendo que idMensajero puede ser nulo
    conn.commit()
    cursor.close()
    conn.close()
    return thread.id



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

async def send_message(idChat,inputValue):
    message = await client.beta.threads.messages.create(
        thread_id=idChat,
        role="user",
        content=inputValue
    )
    return message
async def get_message(idChat, idRun, inputValue):
    while True:
        runInfo = await client.beta.threads.runs.retrieve(thread_id=idChat, run_id=idRun)
        
        if runInfo.completed_at:
            # elapsed = runInfo.completed_at - runInfo.created_at
            # elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed))
            print(f"Run completed")
            messages = await client.beta.threads.messages.list(idChat)
            messageResponse = messages.data[0].content[0].text.value
            break
        elif runInfo.failed_at or runInfo.cancelled_at:
            print(runInfo)
            messageResponse = "Error al obtener la respuesta, ¡vuélvelo a intentar!"
            break
        print("Waiting 1sec...")
        time.sleep(1)
    
    
    save_message_to_db(idChat, inputValue, 1)
    save_message_to_db(idChat, messageResponse)
    return messageResponse

async def chat(prompt):
    assistant = await retrieve_assistant()
        
    if prompt.idChat is None:
        thread = await client.beta.threads.create()
        prompt.idChat = await create_new_chat(thread, prompt.nombre, prompt.email)
        
        print("New chat created with id:", prompt.idChat)
            
    await send_message(prompt.idChat, prompt.input)
    
    runCreate = await client.beta.threads.runs.create(
        thread_id=prompt.idChat,
        assistant_id=assistant.id
    )
    prompt.idRun = runCreate.id 

    print("Actual idChat:", prompt.idChat)
    print("Actual idRun:", prompt.idRun)
    
    messageResponse = ""
    
    messageResponse = await get_message(prompt.idChat, prompt.idRun, prompt.input)
    # Retornar la respuesta junto con el idChat
    return JSONResponse(
        status_code=200,
        content={"message": messageResponse, "idChat": prompt.idChat, "idRun": prompt.idRun}
    )

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
    response = await chat(prompt)
    return response



        

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