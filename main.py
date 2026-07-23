from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import dateparser
import httpx
from bs4 import BeautifulSoup
import datefinder
import json
import re

app = FastAPI()

# CORS allow karna zaroori hai taaki aapka HTML isse baat kar sake
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DateRequest(BaseModel):
    date_string: str

# 1. UptimeRobot ke liye Bulletproof Health Check (Duplicate hata diya gaya hai)
@app.api_route("/", methods=["GET", "POST", "HEAD"])
def home():
    return {"status": "Server is awake and running!"}

# 2. Date Parsing Route (Speed Boost ke sath)
@app.post("/parse-date")
def parse_date(request: DateRequest):
    # Fast settings apply kar di gayi hain
    parsed_date = dateparser.parse(
        request.date_string,
        settings={'LANGUAGES': ['en']}
    )

    if parsed_date:
        # ISO format mein return karega (e.g., 2026-07-20T19:37:09)
        return {"status": "success", "parsed_date": parsed_date.isoformat()}
    else:
        return {"status": "error", "message": "Invalid date string"}
