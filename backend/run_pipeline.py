import fitz  # PyMuPDF
import json
import psycopg2
import requests
import re
import time
import streamlit as st
from pypdf import PdfReader
from sqlalchemy import create_engine  # <-- Ajout de l'import pour le moteur

def get_db_connection():
    return psycopg2.connect(
        host=st.secrets["DB_HOST"],
        database=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASS"],
        port=st.secrets["DB_PORT"]
    )

def get_sqlalchemy_engine():
    """Crée un moteur SQLAlchemy pour que Pandas (pd.read_sql) 
    puisse lire la base de données sans provoquer de Segmentation fault."""
    user = st.secrets["DB_USER"]
    password = st.secrets["DB_PASS"]
    host = st.secrets["DB_HOST"]
    port = st.secrets["DB_PORT"]
    dbname = st.secrets["DB_NAME"]
    
    # Construction de l'URL de connexion PostgreSQL
    url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    return create_engine(url)

def call_groq_cloud(prompt):
    """Envoie une requête HTTP synchrone à l'API Groq Cloud en utilisant les secrets."""
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        raise Exception(f"Erreur API Groq (Code {response.status_code}): {response.text}")

def clean_json_response(raw_text):
    """Extrait la structure JSON pure en éliminant le texte environnant."""
    try:
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        return match.group(0) if match else raw_text
    except Exception:
        return raw_text


# --- LOGIQUE DU PARSEUR INTEGRÉE DIRECTEMENT ICI ---

# Ton regex strict et ta liste d'exclusion
DEFECT_PATTERN = re.compile(r'\b\d\.\d+(?:\.\d+)*[A-Z]\b|\b2[A-N]\b')
EXCLUDE_KEYWORDS = ["JIRA", "CP22", "TICKET", "SOLL", "IST"]

VALID_DEFECT_CODES = {
    # Page 1 : Crimp & Welded Joints
    "1.1.1A", "1.1.1B", "1.1.1C", "1.1.1D", "1.1.1E", "1.1.1F", "1.1.1G", "1.1.1H", "1.1.1J", "1.1.1K", "1.1.1L", "1.1.1M", "1.1.1N", "1.1.1O", "1.1.1P", "1.1.1Q", "1.1.1R", "1.1.1V", "1.1.1W", "1.1.1X", "1.1.1Z",
    "1.1.2A", "1.1.2B", "1.1.2C", "1.1.2D", "1.1.2F", "1.1.2G", "1.1.2H", "1.1.2J", "1.1.2K", "1.1.2M", "1.1.2N", "1.1.2O", "1.1.2P", "1.1.2Q", "1.1.2R", "1.1.2Z",
    "1.1.3A", "1.1.3B", "1.1.3C", "1.1.3D", "1.1.3E", "1.1.3F", "1.1.3G", "1.1.3H", "1.1.3J", "1.1.3K", "1.1.3L", "1.1.3M", "1.1.3N", "1.1.3O", "1.1.3Q", "1.1.3U",
    "1.1.4A", "1.1.4B", "1.1.4C", "1.1.4D", "1.1.4E", "1.1.4G", "1.1.4H", "1.1.4J", "1.1.4K", "1.1.4L", "1.1.4M", "1.1.4N", "1.1.4O", "1.1.4Q", "1.1.4U",
    "1.2A", "1.2B", "1.2C", "1.2D", "1.2E", "1.2F", "1.2G", "1.2H", "1.2J", "1.2K", "1.2L", "1.2M", "1.2N", "1.2O", "1.2P", "1.2Q", "1.2R", "1.2S", "1.2T", "1.2U",
    "1.3.1A", "1.3.1B", "1.3.1C", "1.3.1D", "1.3.1E", "1.3.1F", "1.3.1G", "1.3.1H", "1.3.1I", "1.3.1J", "1.3.1K", "1.3.1L", "1.3.1M", "1.3.1N", "1.3.1P", "1.3.1S",
    "1.3.2A", "1.3.2B", "1.3.2C", "1.3.2D", "1.3.2F", "1.3.2H", "1.3.2L",
    "1.5A", "1.5B", "1.5C",

    # Page 2 : Connector Housings & Wires
    "2A", "2B", "2C", "2D", "2E", "2F", "2G", "2H", "2I", "2J", "2K", "2L", "2M", "2N",
    "3.1.1A", "3.1.1B", "3.1.1C", "3.1.1D", "3.1.1E", "3.1.1F", "3.1.1G", "3.1.1I", "3.1.1J", "3.1.1L", "3.1.1M", "3.1.1N", "3.1.1O", "3.1.1P", "3.1.1Q", "3.1.1R", "3.1.1S", "3.1.1T",
    "3.1.2B", "3.1.2C", "3.1.2D", "3.1.2E", "3.1.2F", "3.1.2G",
    "3.1.3A", "3.1.3B", "3.1.3C", "3.1.3D", "3.1.3E", "3.1.3F", "3.1.3G", "3.1.3I", "3.1.3J", "3.1.3L", "3.1.3M", "3.1.3N", "3.1.3O", "3.1.3P", "3.1.3Q", "3.1.3R", "3.1.3S", "3.1.3T",
    "3.2A", "3.2B", "3.2C", "3.2D", "3.2E", "3.2F", "3.2G", "3.2I", "3.2J", "3.2K", "3.2U", "3.2V",
    "3.3A", "3.3B", "3.3C", "3.3D", "3.3E", "3.3F", "3.3G", "3.3H", "3.3I", "3.3J", "3.3K", "3.3N", "3.3T", "3.3V",

    # Page 3 : Grommets & Wire Protective Systems
    "4.1A", "4.1B", "4.1C", "4.1D", "4.1E", "4.1H",
    "4.2A", "4.2B", "4.2C", "4.2D", "4.2E", "4.2I",
    "4.3A", "4.3B", "4.3C", "4.3D", "4.3E", "4.3M", "4.3O",
    "4.4A", "4.4B", "4.4C", "4.4D", "4.4E", "4.4L", "4.4M", "4.4N", "4.4O",
    "4.5A", "4.5B", "4.5C", "4.5D", "4.5E", "4.5L", "4.5M", "4.5N", "4.5O",
    "5.1A", "5.1B", "5.1C", "5.1D", "5.1F", "5.1H", "5.1K", "5.1M", "5.1N", "5.1P", "5.1Q",
    "5.2A", "5.2B", "5.2C", "5.2D", "5.2E", "5.2G", "5.2R", "5.2S",

    # Page 4 : Taping / General Components / Packaging
    "6.1A", "6.1B", "6.1C", "6.1D", "6.1E", "6.1F", "6.1G", "6.1H", "6.1I", "6.1J",
    "6.2A", "6.2B", "6.2C", "6.2F", "6.2G",
    "6.3A", "6.3B", "6.3C", "6.3F", "6.3G", "6.3H",
    "7.1A", "7.1B", "7.1C", "7.1D", "7.1F", "7.1G", "7.1H", "7.1L", "7.1M", "7.1N", "7.1O", "7.1P",
    "7.2A", "7.2B", "7.2C", "7.2D", "7.2F", "7.2L", "7.2M", "7.2P",
    "7.4A", "7.4B", "7.4D", "7.4K", "7.4L", "7.4P",
    "8.1A", "8.1B", "8.1D", "8.1G", "8.1H", "8.1L", "8.1R",
    "8.2A", "8.2B", "8.2D", "8.2T", "8.2U"
}

def clean_and_validate_defect_code(raw_text):
    match = DEFECT_PATTERN.search(raw_text)
    if not match:
        return None
    code = match.group(0)
    upper_line = raw_text.upper()
    if any(keyword in upper_line for keyword in EXCLUDE_KEYWORDS):
        return None
    if code not in VALID_DEFECT_CODES:
        return None
    return code

def parse_defects_with_python(page_text):
    print("🚀 LA NOUVELLE FONCTION EN MEMOIRE S'EXECUTE !") # Ligne de test
    valid_defects = []
    if page_text:
        for line in page_text.split('\n'):
            validated_code = clean_and_validate_defect_code(line)
            if validated_code:
                valid_defects.append(validated_code)
    return valid_defects
# --------------------------------------------------

def extract_dynamic_pdf_data(pdf_file_bytes):
    """Analyzes the PDF and deterministically extracts the summary and detailed harness data."""
    doc = fitz.open(stream=pdf_file_bytes, filetype="pdf")
    pages_text = []
    
    for page in doc:
        blocks = page.get_text("blocks")
        blocks.sort(key=lambda b: (b[1], b[0]))
        page_lines = []
        for b in blocks:
            text_block = b[4].strip()
            if len(text_block) > 1:
                page_lines.append(text_block)
        pages_text.append("\n".join(page_lines))
    doc.close()

    if not pages_text:
        raise Exception("The PDF is empty or corrupted.")

    # =========================================================================
    # STEP A: Global Summary Extraction (Page 1)
    # =========================================================================
    print("⚡ [1/3] Extracting Global Summary...", flush=True)
    first_page_text = pages_text[0]
    
    prompt_summary = f"""
    You are a rigid Data Engineering Extraction Pipeline for Volkswagen/Dräxlmaier automotive quality audits.
    Your sole task is to convert the global monthly summary page text into a precise JSON object matching a strict schema.

    CRITICAL INSTRUCTIONS FOR DYNAMIC PLANT, COUNTRY, AND QK EXTRACTION:
    
    1. PLANT NAME & COUNTRY LOCATION (HIGH PRIORITY):
        - Look at the main results table section (usually starting with numbered lines like "1 A- ...", "2 Standort ...").
        - Example: "1 A- DAD Zrenjanin (Serbien)" -> Plant is "DAD Zrenjanin" (or "Zrenjanin") and Country is "Serbien".
        - Clean the plant name: Remove any prefixes like "1", "A-", or leading whitespace. Keep the name clean and accurate.
        - If a country name is inside parentheses next to the plant, extract it into the "country" field (e.g., "(Serbien)" -> "Serbien").

    2. QK METRICS LOCATION & CONVERSION:
        - Extract the numerical QK metrics (QK min, QK avg, QK max) aligned with the active plant line.
        - Even if the QK values are "0.0" or "0", extract them as float 0.0. 
        - Replace any German commas "," with dots "." for float casting (e.g., "0,3" -> 0.3).
        - "audits_count" is the number of tested harnesses (usually listed in columns like "Anzahl geprüfter Leitungsstränge" or listed as "Ltg.stränge geprüft: (3)"). If not explicitly in a cell next to the plant, look for the total count.

    3. DATE CONVERSION:
            Convert the German month name under "Monat / Jahr" to a two-digit numeric string.
            Mapping: Januar->01, Februar->02, März->03, April->04, Mai->05, Juni->06, Juli->07, August->08, September->09, Oktober->10, November->11, Dezember->12.
        - E-xtract the 4-digit year (e.g., "2026").

    Return a comprehensive valid JSON object matching this structure exactly:
    {{
        "supplier": "Exact company name found under 'Firma' or 'Von' (e.g., 'Dräxlmaier Group')",
        "plant": "Exact plant site name string (e.g., 'DAD Zrenjanin')",
        "country": "Extract the country name if present (e.g., 'Serbien')",
        "report_month": "Two-digit month numeric string, e.g. '06'",
        "report_year": "Four-digit year numeric string, e.g. '2026'",
        "QK_min": 0.0,
        "QK_avg": 0.0,
        "QK_max": 0.0,
        "audits_count": 3
    }}

    Document Text to analyze (Page 1):
    {first_page_text}
    """
    
    while True:
        try:
            raw_summary = call_groq_cloud(prompt_summary)
            summary_data = json.loads(clean_json_response(raw_summary))
            break
        except Exception as e:
            if "Rate limit reached" in str(e):
                match_wait = re.search(r"try again in ([0-9.]+)(s|ms)", str(e))
                wait_time = float(match_wait.group(1)) if match_wait else 5.0
                if match_wait and match_wait.group(2) == "ms":
                    wait_time = wait_time / 1000.0
                print(f"⏳ Rate limiting (Page 1). Waiting for {wait_time + 1}s...", flush=True)
                time.sleep(wait_time + 1.0)
            else:
                raise e

    time.sleep(4.5)

    # =========================================================================
    # STEP B: Master Reference Index Creation (Page 2)
    # =========================================================================
    print("⚡ [2/3] Creating matching registry (Page 2)...", flush=True)
    page_2_text = pages_text[1]
    
    prompt_master_table = f"""
    You are a precise data extraction specialist. Analyze this summary table from Page 2 of a Volkswagen/Dräxlmaier audit report.
    Extract EVERY harness row listed in the main table.

    Be careful with shifted layouts or merged columns (like HV and QK columns). Map the QK score to its correct row even if columns look misaligned.
    Convert any commas to dots in numerical fields.

    Return a JSON object with a "harnesses" array matching this format exactly:
    {{
        "harnesses": [
            {{
                "drawing_number": "The exact Sachnummer/drawing number or table key string (e.g., 'TAB_016_471_AQ' or '2643533')",
                "audit_type": "Z",
                "QK_score": 0.9
            }}
        ]
    }}

    Text to analyze:
    {page_2_text}
    """
    
    harness_registry = {}
    while True:
        try:
            raw_master = call_groq_cloud(prompt_master_table)
            master_data = json.loads(clean_json_response(raw_master))
            for h in master_data.get("harnesses", []):
                dn_key = str(h.get("drawing_number", "")).strip()
                if dn_key:
                    qk_raw = str(h.get("QK_score", "0.0")).replace(",", ".").strip()
                    try:
                        qk_val = float(qk_raw)
                    except ValueError:
                        qk_val = 0.0
                    harness_registry[dn_key] = {
                        "audit_type": h.get("audit_type", "P"),
                        "QK_score": qk_val
                    }
            break
        except Exception as e:
            if "Rate limit reached" in str(e):
                print("⏳ Timeout on master analysis (Page 2)...", flush=True)
                time.sleep(6.0)
            else:
                print(f"⚠️ Unable to create Page 2 registry: {e}. Fallback mode activated.", flush=True)
                break

    time.sleep(4.5)

    # =========================================================================
    # STEP C: Iterative Page-by-Page Harness Extraction (Pages 3+)
    # =========================================================================
    print("⚡ [3/3] Iterative Harness Extraction...", flush=True)
    all_harnesses = []

    for i in range(1, len(pages_text)):
        page_content = pages_text[i]
        page_content_lower = page_content.lower()
        
        if "ergebnisübersicht" in page_content_lower or "jahresübersicht" in page_content_lower:
            continue

        # Version universelle (Allemand, Français, Anglais)
        is_valid_audit_page = (
            "fahrzeug" in page_content_lower or "vehicule" in page_content_lower or "vehicle" in page_content_lower or
            "sachnummer" in page_content_lower or "sach-nr" in page_content_lower or "part number" in page_content_lower or "reference" in page_content_lower or
            "auditor" in page_content_lower or "auditeur" in page_content_lower or
            "tabelle" in page_content_lower or "tableau" in page_content_lower or "table" in page_content_lower
        )
        
        if not is_valid_audit_page:
            continue

        # ---------------------------------------------------------------------
        # 1. ESSAI DE PARSING DES DÉFAUTS (Isolé et sécurisé)
        # ---------------------------------------------------------------------
        try:
            extracted_defects = parse_defects_with_python(page_content)
            if not extracted_defects:
                extracted_defects = []
        except Exception as defect_err:
            # Si le parser de défauts plante, on ne bloque pas tout le pipeline !
            # On log l'erreur et on initialise une liste vide pour continuer.
            print(f"⚠️ Erreur de parsing des défauts sur la page {i+1} (ignorée) : {defect_err}", flush=True)
            extracted_defects = []

        # ---------------------------------------------------------------------
        # 2. EXTRACTION DU RESTE DES DONNÉES (Le faisceau s'injectera quand même)
        # ---------------------------------------------------------------------
        prompt_single_page = f"""
        Analyze this unstructured layout text from ONE single page...
        """
        
        # ... (Le reste de ton code d'extraction Groq continue ici) ...
        
        prompt_single_page = f"""
        Analyze this unstructured layout text from ONE single page of an automotive wire harness product audit report.
        Extract the item header information. Do NOT attempt to extract the raw defects table list.

        Return a single JSON object matching this format exactly:
        {{
            "vehicle_type": "Vehicle/platform name string (e.g., 'VW VN 35S')", 
            "drawing_number": "Drawing / part number string or Table reference found (e.g., 'TAB_016_471_AQ' or '2643533')", 
            "part_description": "Assembly specification description string (e.g., 'RL')",
            "QK_score": 0.0, 
            "auditor_name": "Auditor full name string (e.g., 'Braiek Ali')", 
            "calculation_factor": 0.7, 
            "count_wires": 272, 
            "count_contacts": 417, 
            "count_components": 200, 
            "audit_type": "P"
        }}

        Document Text to analyze (Page {i+1}):
        {page_content}
        """
        
        success = False
        while not success:
            print(f"📄 Processing Page {i+1}/{len(pages_text)}...", flush=True)
            try:
                raw_page_data = call_groq_cloud(prompt_single_page)
                harness_obj = json.loads(clean_json_response(raw_page_data))
                
                if not isinstance(harness_obj, dict):
                    harness_obj = {}
                
                drawing_no = str(harness_obj.get("drawing_number", "")).strip()
                
                matched_master = None
                for key, val in harness_registry.items():
                    if key in drawing_no or drawing_no in key:
                        matched_master = val
                        break
                
                if matched_master:
                    harness_obj["audit_type"] = matched_master["audit_type"]
                    harness_obj["QK_score"] = matched_master["QK_score"]
                else:
                    try:
                        qk_raw = str(harness_obj.get("QK_score", "0.0")).replace(",", ".").strip()
                        harness_obj["QK_score"] = float(qk_raw)
                    except (ValueError, TypeError):
                        harness_obj["QK_score"] = 0.0
                
                for field in ["count_wires", "count_contacts", "count_components"]:
                    try:
                        harness_obj[field] = int(str(harness_obj.get(field, "0")).strip())
                    except ValueError:
                        harness_obj[field] = 0

                harness_obj["raw_defects_list"] = extracted_defects
                harness_obj["defect_count"] = len(extracted_defects)
                harness_obj["defect_points"] = 0
                                
                all_harnesses.append(harness_obj)
                success = True 
                time.sleep(4.5)
                
            except Exception as e:
                if "Rate limit reached" in str(e):
                    match_wait = re.search(r"try again in ([0-9.]+)(s|ms)", str(e))
                    wait_time = float(match_wait.group(1)) if match_wait else 5.0
                    time.sleep(wait_time + 1.5)
                else:
                    print(f"⚠️ Processing error ignored on page {i+1}: {e}", flush=True)
                    success = True  
                    time.sleep(3.0)

    # =========================================================================
    # PIPELINE RETURN GUARD LAUNCHPAD
    # =========================================================================
    if not all_harnesses:
        print("❌ Critical Failure: Zero harness items were populated.", flush=True)
        return {"audits_count": 0, "user_email": None}, []

    try:
        summary_data["QK_min"] = float(str(summary_data.get("QK_min", 0.0)).replace(",", "."))
        summary_data["QK_avg"] = float(str(summary_data.get("QK_avg", 0.0)).replace(",", "."))
        summary_data["QK_max"] = float(str(summary_data.get("QK_max", 0.0)).replace(",", "."))
    except (ValueError, TypeError):
        scores = [h.get('QK_score', 0.0) for h in all_harnesses]
        summary_data["QK_min"] = min(scores) if scores else 0.0
        summary_data["QK_avg"] = sum(scores)/len(scores) if scores else 0.0
        summary_data["QK_max"] = max(scores) if scores else 0.0

    if summary_data.get("audits_count") == 0 or "audits_count" not in summary_data:
        summary_data["audits_count"] = len(all_harnesses)

    if "user_email" not in summary_data:
        summary_data["user_email"] = None

    return summary_data, all_harnesses