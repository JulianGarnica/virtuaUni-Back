import os
from openai import AzureOpenAI
from dotenv import load_dotenv
  
load_dotenv()
#From https://learn.microsoft.com/es-es/azure/ai-services/openai/assistants-reference?tabs=python
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPEN_AI_API_KEY"),  
    api_version="2024-08-01-preview",
    azure_endpoint = os.getenv("AZURE_OPEN_AI_ENDPOINT")
    )

my_assistant = client.beta.assistants.retrieve("asst_G7VBtTFcNWkYuqjBlal8xq4B")
print(my_assistant)
