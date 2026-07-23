from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import dateparser

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

# 1. UptimeRobot ke liye Bulletproof Health Check
@app.api_route("/", methods=["GET", "POST", "HEAD"])
def home():
    return {"status": "Server is awake and running!"}

# 2. Date Parsing Route (Safety Net ke sath)
@app.post("/parse-date")
def parse_date(request: DateRequest):
    try:
        # Fast settings ke sath date parse karna
        parsed_date = dateparser.parse(
            request.date_string
        )

        if parsed_date:
            # ISO format mein return karega (e.g., 2026-07-20T19:37:09)
            return {"status": "success", "parsed_date": parsed_date.isoformat()}
        else:
            return {"status": "error", "message": "Invalid date string"}
            
    except Exception as e:
        return {"status": "error", "message": f"Backend Error: {str(e)}"}