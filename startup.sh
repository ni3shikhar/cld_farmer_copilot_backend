az webapp config set \
  --resource-group rg-cld-farmerpoc \
  --name farmer-copilot-api \
  --startup-file "gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app"
