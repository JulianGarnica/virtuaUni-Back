import os
from openai import AzureOpenAI
from dotenv import load_dotenv
  
load_dotenv()
#From https://learn.microsoft.com/es-es/azure/ai-services/openai/assistants-reference?tabs=python
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),  
    api_version="2024-08-01-preview",
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    )

assistant = client.beta.assistants.create(
  instructions="Las respuestas que das son cortas y claras, eres una IA de la universidad UNIMINUTO de la sede de Zipaquirá, por lo cual, sólo puedes dar información relacionada con la UNIMINUTO de la sede de Zipaquirá sin nombrar ninguna otra universidad. Te llamas Minuni, siempre que des respuestas, lo vas a hacer de una forma amigable también usando emojis.",
  model="<REPLACE WITH MODEL DEPLOYMENT NAME>", # replace with model deployment name. 
  tools=[{"type": "code_interpreter"}]
)