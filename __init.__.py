# analyze/__init__.py

import azure.functions as func
from azure.functions import AsgiMiddleware
from .main import app  # ← Import the FastAPI app from main.py

# Azure Functions entry point for HTTP trigger
main = AsgiMiddleware(app)
