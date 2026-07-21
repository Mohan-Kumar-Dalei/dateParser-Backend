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

# 3. URL se Date nikalne wala Route
class URLRequest(BaseModel):
    url: str

def is_valid_date_string(s):
    s = s.strip()
    if len(s) < 5: return False
    if re.search(r'\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}', s): return True
    if re.search(r'(?i)\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\b', s): 
        if re.search(r'\d{1,4}', s): 
            return True
    return False

# Naya Helper: Ye tag ka CSS selector jaisa naam banayega (e.g., div#date.entry-meta)
def get_element_signature(element):
    if not element or not element.name:
        return ""
    
    tag = element.name
    el_id = element.get('id', '')
    el_classes = element.get('class', [])
    
    sig = tag
    if el_id:
        sig += f"#{el_id}"
    if el_classes:
        class_str = ".".join(el_classes) if isinstance(el_classes, list) else el_classes
        sig += f".{class_str}"
        
    return sig

@app.post("/extract-url-dates")
async def extract_url_dates(req: URLRequest):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(req.url, headers=headers, follow_redirects=True, timeout=20.0)
            
            # Anti-Scraping Block Check
            if response.status_code in [403, 401, 429, 503]:
                return {
                    "status": "error", 
                    "message": f"Website is blocking bots. HTTP Status: {response.status_code}"
                }
                
            html_content = response.text
            
        soup = BeautifulSoup(html_content, "html.parser")
        extracted_dates = []

        # 1. Meta Tags (Same as before)
        for meta in soup.find_all("meta"):
            prop = meta.get("property", "").lower()
            name = meta.get("name", "").lower()
            content = meta.get("content", "")
            if content and ("time" in prop or "date" in prop or "time" in name or "date" in name):
                extracted_dates.append({"source": f"Meta ({prop or name})", "raw_date": content})

        # 2. Time Tags
        for time_tag in soup.find_all("time"):
            dt = time_tag.get("datetime")
            if dt:
                sig = get_element_signature(time_tag)
                extracted_dates.append({"source": f"HTML <time> [{sig}]", "raw_date": dt})

        # 3. JSON-LD / Schema
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if "datePublished" in data:
                        extracted_dates.append({"source": "Schema (Published)", "raw_date": str(data["datePublished"])})
                    if "dateModified" in data:
                        extracted_dates.append({"source": "Schema (Modified)", "raw_date": str(data["dateModified"])})
            except:
                pass

        # 4. THE UNIVERSAL DOM CLIMBER (For visible text)
        ignore_tags = ['script', 'style', 'noscript', 'head', 'meta', 'title']
        
        for text_node in soup.find_all(string=True):
            immediate_parent = text_node.parent
            if immediate_parent and immediate_parent.name not in ignore_tags:
                text = text_node.strip()
                if 5 <= len(text) <= 150:
                    for _, raw_string in datefinder.find_dates(text, source=True):
                        clean_str = raw_string.strip()
                        if is_valid_date_string(clean_str):
                            
                            # 🚀 Yahan hum upar ke 3 levels tak check karenge jab tak Class ya ID na mile
                            current_element = immediate_parent
                            best_signature = ""
                            
                            for _ in range(3): # Max 3 levels upar jayega
                                if not current_element or current_element.name in ignore_tags:
                                    break
                                    
                                current_sig = get_element_signature(current_element)
                                # Agar ID ya Class mil gayi, toh yahi best hai! Break kar do.
                                if "#" in current_sig or "." in current_sig:
                                    best_signature = current_sig
                                    break
                                
                                # Agar nahi mili, toh uske parent (upar) check karo
                                current_element = current_element.parent
                            
                            # Agar 3 level upar tak koi class/id nahi mili, toh immediate tag ka naam de do
                            if not best_signature:
                                best_signature = f"<{immediate_parent.name}> (No Class/ID)"
                                
                            extracted_dates.append({"source": f"Element: {best_signature}", "raw_date": clean_str})

        # 5. Fallback JS/JSON Brute Force
        if len(extracted_dates) == 0:
            for script in soup.find_all("script"):
                script_text = script.string if script.string else ""
                if script_text:
                    raw_dates = re.findall(r'(?:"|\b)(202[0-9][-/\.][0-1][0-9][-/\.][0-3][0-9])(?:"|\b)', script_text)
                    for rd in set(raw_dates):
                         extracted_dates.append({"source": "Hidden JS/JSON Data", "raw_date": rd})

        # Unique Dates Filter
        unique_dates = {f"{d['source']}_{d['raw_date']}": d for d in extracted_dates}.values()

        if len(unique_dates) == 0:
            return {
                 "status": "success",
                 "url": req.url,
                 "total_found": 0,
                 "dates": [],
                 "message": "Page loaded successfully, but no dates were found in the HTML. Site might be using advanced Client-Side Rendering."
            }

        return {
            "status": "success",
            "url": req.url,
            "total_found": len(unique_dates),
            "dates": list(unique_dates)
        }

    except Exception as e:
        return {"status": "error", "message": f"Failed to fetch or parse URL: {str(e)}"}