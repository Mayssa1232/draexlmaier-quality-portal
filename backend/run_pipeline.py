import fitz  # PyMuPDF
import json
import psycopg2
import requests
import re
import time
import streamlit as st
from pypdf import PdfReader

def get_db_connection():
    return psycopg2.connect(
        host=st.secrets["DB_HOST"],
        database=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASS"],
        port=st.secrets["DB_PORT"]
    )

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

def parse_defects_with_python(page_text, page_number=None):
    """Analyse le texte pour extraire les codes défauts et leurs points associés."""
    defects_list = []
    
    # Prise en compte des formats de codes complexes à points et lettres (ex: 3.1.2E, 3.2K)
    defect_pattern = re.compile(r'\b(?:[1-9][A-Z]|\d+(?:\.\d+)+[A-Z])\b')
    
    lines = page_text.split('\n')
    for idx, line in enumerate(lines):
        clean_line = line.strip()
        matches = defect_pattern.findall(clean_line)
        if matches:
            for code in matches:
                points = 0
                for offset in range(1, 5):  # Augmenté à 4 lignes d'écart pour la tolérance de layout
                    if idx + offset < len(lines):
                        next_line = lines[idx + offset].strip()
                        if next_line.isdigit():
                            val_points = int(next_line)
                            if val_points > 0:
                                points = val_points
                                break
                                
                defects_list.append({"code": code, "points": points})
                
    return defects_list

def extract_dynamic_pdf_data(pdf_file_bytes):
    """Analyse le PDF et extrait de manière déterministe le résumé et le détail des faisceaux."""
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
        raise Exception("Le PDF est vide ou corrompu.")

    # =========================================================================
    # STEP A: Extraction du Résumé Global (Page 1)
    # =========================================================================
    print("⚡ [1/3] Extraction du Résumé Global...", flush=True)
    first_page_text = pages_text[0]
    
    prompt_summary = f"""
    You are a rigid Data Engineering Extraction Pipeline for Volkswagen/Dräxlmaier automotive quality audits.
    Your sole task is to convert the global monthly summary page text into a precise JSON object matching a strict schema.

    CRITICAL INSTRUCTIONS FOR DYNAMIC PLANT & QK EXTRACTION:
    1. PLANT NAME LOCATION: Look at the main results table section (usually under 'Fertigungsstätten' or listing numbered sites like '1. A- ...'). Extract the exact full plant name found there.
    2. QK METRICS LOCATION: Extract the numerical values (QK min, QK avg, QK max) aligned with that plant. Replace any commas ',' with dots '.' for numerical consistency.
    3. DATE CONVERSION: Convert the German month name found under 'Monat / Jahr' (e.g., 'Juni 2026' -> '06', 'Mai' -> '05').

    Return a comprehensive valid JSON object matching this structure exactly:
    {{
        "supplier": "Exact company name found (e.g., 'Dräxlmaier Group')",
        "plant": "Exact plant site name string (e.g., 'SATE El Jem (Tunesien)')",
        "country": "Extract the country name if present (e.g., 'Tunesien')",
        "report_month": "Two-digit month numeric string, e.g. '06'",
        "report_year": "Four-digit year numeric string, e.g. '2026'",
        "QK_min": 0.0,
        "QK_avg": 0.0,
        "QK_max": 0.0,
        "audits_count": 0
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
                print(f"⏳ Limitation de débit (Page 1). Attente de {wait_time + 1}s...", flush=True)
                time.sleep(wait_time + 1.0)
            else:
                raise e

    time.sleep(4.5)

    # =========================================================================
    # STEP B: Extraction de l'Index Référentiel Maître (Page 2)
    # =========================================================================
    print("⚡ [2/3] Création du registre de correspondance (Page 2)...", flush=True)
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
                    # Traitement sécurisé du score QK (remplacement virgule par point)
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
                print("⏳ Temporisation sur l'analyse maîtresse (Page 2)...", flush=True)
                time.sleep(6.0)
            else:
                print(f"⚠️ Impossible de créer le registre Page 2 : {e}. Mode de secours activé.", flush=True)
                break

    time.sleep(4.5)

    # =========================================================================
    # STEP C: Extraction itérative des Faisceaux page par page (Pages 3+)
    # =========================================================================
    print("⚡ [3/3] Extraction itérative des Faisceaux...", flush=True)
    all_harnesses = []

    for i in range(1, len(pages_text)):
        page_content = pages_text[i]
        page_content_lower = page_content.lower()
        
        if "ergebnisübersicht" in page_content_lower or "jahresübersicht" in page_content_lower:
            continue

        is_valid_audit_page = (
            "fahrzeug" in page_content_lower or
            "sachnummer" in page_content_lower or
            "sach-nr" in page_content_lower or
            "auditor" in page_content_lower or
            "tabelle" in page_content_lower
        )
        
        if not is_valid_audit_page:
            continue

        extracted_defects = parse_defects_with_python(page_content)
        
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
            print(f"📄 Analyse en cours de la Page {i+1}/{len(pages_text)}...", flush=True)
            try:
                raw_page_data = call_groq_cloud(prompt_single_page)
                harness_obj = json.loads(clean_json_response(raw_page_data))
                
                drawing_no = str(harness_obj.get("drawing_number", "")).strip()
                
                # Système d'appariement robuste clé-valeur avec l'index maître
                matched_master = None
                for key, val in harness_registry.items():
                    if key in drawing_no or drawing_no in key:
                        matched_master = val
                        break
                
                if matched_master:
                    harness_obj["audit_type"] = matched_master["audit_type"]
                    harness_obj["QK_score"] = matched_master["QK_score"]
                else:
                    # Redressement de type sécurisé si absent de l'index maître
                    try:
                        qk_raw = str(harness_obj.get("QK_score", "0.0")).replace(",", ".").strip()
                        harness_obj["QK_score"] = float(qk_raw)
                    except (ValueError, TypeError):
                        harness_obj["QK_score"] = 0.0
                
                # Conversion sécurisée des entiers de comptage pour éviter les crashs à l'injection
                for field in ["count_wires", "count_contacts", "count_components"]:
                    try:
                        harness_obj[field] = int(str(harness_obj.get(field, "0")).strip())
                    except ValueError:
                        harness_obj[field] = 0

                harness_obj["raw_defects_list"] = extracted_defects
                harness_obj["defect_count"] = len(extracted_defects)
                harness_obj["defect_points"] = sum(int(d["points"]) for d in extracted_defects)
                
                all_harnesses.append(harness_obj)
                success = True  
                time.sleep(4.5)
                
            except Exception as e:
                if "Rate limit reached" in str(e):
                    match_wait = re.search(r"try again in ([0-9.]+)(s|ms)", str(e))
                    wait_time = float(match_wait.group(1)) if match_wait else 5.0
                    time.sleep(wait_time + 1.5)
                else:
                    print(f"⚠️ Erreur de traitement ignorée page {i+1} : {e}", flush=True)
                    success = True  
                    time.sleep(3.0)

    # Sécurisation des métriques globales calculées
    if all_harnesses:
        try:
            summary_data["QK_min"] = float(str(summary_data.get("QK_min", 0.0)).replace(",", "."))
            summary_data["QK_avg"] = float(str(summary_data.get("QK_avg", 0.0)).replace(",", "."))
            summary_data["QK_max"] = float(str(summary_data.get("QK_max", 0.0)).replace(",", "."))
        except ValueError:
            scores = [h['QK_score'] for h in all_harnesses]
            summary_data["QK_min"] = min(scores) if scores else 0.0
            summary_data["QK_avg"] = sum(scores)/len(scores) if scores else 0.0
            summary_data["QK_max"] = max(scores) if scores else 0.0

        if summary_data.get("audits_count") == 0:
            summary_data["audits_count"] = len(all_harnesses)

    if "user_email" not in summary_data:
        summary_data["user_email"] = None

    return summary_data, all_harnesses