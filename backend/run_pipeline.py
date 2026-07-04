import fitz  # PyMuPDF
import json
import psycopg2
import requests
import re
import time 

def get_db_connection():
    """Gère la connexion à PostgreSQL sur le port actif (5432 ou 5433)."""
    try:
        return psycopg2.connect(user="postgres", password="2002", host="127.0.0.1", port="5432", database="quality_db")
    except psycopg2.OperationalError:
        return psycopg2.connect(user="postgres", password="2002", host="127.0.0.1", port="5433", database="quality_db")

def call_groq_cloud(prompt):
    """Envoie une requête HTTP synchrone à l'API Groq Cloud."""
    GROQ_API_KEY = "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" 
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

import re

def parse_defects_with_python(page_text):
    """
    Analyse le texte d'une page pour extraire les codes défauts exacts,
    gérant les variations de format (ex: 1.1A, 3.1.1L, 10.2B, etc.).
    """
    defects_list = []
    
    # Explication de la nouvelle Regex :
    # \b           : Limite de mot
    # \d+          : Un ou plusieurs chiffres (ex: 1 ou 3 ou 12)
    # (?:\.\d+)+   : Un point suivi de chiffres, répétable (ex: .1 ou .1.1)
    # [A-Z]        : Une lettre majuscule à la fin (ex: A, L, N)
    # \b           : Limite de mot
    defect_pattern = re.compile(r'\b(\d+(?:\.\d+)+[A-Z])\b')
    
    lines = page_text.split('\n')
    for idx, line in enumerate(lines):
        match = defect_pattern.search(line)
        if match:
            code = match.group(1)
            points = 0
            
            # Recherche du score dans les 3 lignes suivantes
            for offset in range(1, 4):
                if idx + offset < len(lines):
                    next_line = lines[idx + offset].strip()
                    if next_line.isdigit() and next_line in ['10', '50', '75', '100']:
                        points = int(next_line)
                        break  # Score trouvé, on arrête la recherche pour ce code
                        
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
    1. PLANT NAME LOCATION: Look at the main results table section (usually under 'Fertigungsstätten' or listing numbered sites like '1. A- ...' or '1. ...'). Extract the exact full plant name found there (e.g., 'SDPC Pitesti (Rumänien)' or 'DET Jemmal'). DO NOT hallucinate or default to any plant name not explicitly written in the text.
    2. QK METRICS LOCATION: Immediately next to, below, or aligned with that extracted plant name, there is a sequence of numbers representing the Quality Classes (QK values for current month and previous month) along with audit counts.
       - Carefully map the values for the CURRENT month ('Aktueller Monat' / 'aktuell') to: 'QK_min', 'QK_avg' (or 'QK Ø'), and 'QK_max'.
    3. DATE CONVERSION: Convert the German month name found under or near 'Monat / Jahr' (e.g., 'Juni 2026' or 'Mai 2026') to its exact two-digit numeric equivalent (e.g., 'Juni' -> '06', 'Mai' -> '05').

    Return a comprehensive valid JSON object matching this structure exactly:
    {{
       "supplier": "Exact company/firm name string found (e.g., 'Dräxlmaier Group')",
       "plant": "Exact plant site name string extracted dynamically from the table line (e.g., 'SDPC Pitesti (Rumänien)')",
       "country": "Extract the country name if present in the plant string or location section (e.g., 'Rumänien')",
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
                print(f"⏳ Limitation de débit (Page 1). Attente forcée de {wait_time + 1}s...", flush=True)
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

    Look closely at the last two columns of the summary table section to capture the correct Audit-Art ("Z" or "P").
    - These two columns correspond to the audit classifications: "Produktaudit zerstörend" (Destructive / Z) and "Produktaudit partiell" (Partial / P).
    - "Z" stands for Zerstörend (Destructive) - Checkmark or alignment in the second-to-last column.
    - "P" stands for Partiell (Partial) - Checkmark or alignment in the very last column.

    Return a JSON object with a "harnesses" array matching this format exactly:
    {{
        "harnesses": [
            {{
                "drawing_number": "The exact Sachnummer/drawing number string (e.g., '9008648')",
                "audit_type": "Z",
                "QK_score": 1.7
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
            harness_registry = {
                str(h["drawing_number"]).strip(): {
                    "audit_type": h.get("audit_type", "P"),
                    "QK_score": float(h.get("QK_score", 0.0))
                } for h in master_data.get("harnesses", [])
            }
            break
        except Exception as e:
            if "Rate limit reached" in str(e):
                print("⏳ Temporisation sur l'analyse maîtresse (Page 2)...", flush=True)
                time.sleep(6.0)
            else:
                print(f"⚠️ Impossible de créer le registre Page 2 : {e}. Utilisation du mode dynamique de secours.", flush=True)
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
        
        if "ergebnisübersicht" in page_content_lower:
            continue

        is_valid_audit_page = (
            "fahrzeug" in page_content_lower or 
            "sachnummer" in page_content_lower or 
            "sach-nr" in page_content_lower or 
            "auditor" in page_content_lower
        )
        
        if not is_valid_audit_page:
            print(f"⏩ Page {i+1}/{len(pages_text)} ignorée (Page structurelle ou annexe non pertinente).", flush=True)
            continue

        extracted_defects = parse_defects_with_python(page_content)
        
        prompt_single_page = f"""
        Analyze this unstructured layout text from ONE single page of an automotive wire harness product audit report.
        Extract the item header information. Do NOT attempt to extract the raw defects table list.

        Return a single JSON object matching this format exactly:
        {{
            "vehicle_type": "Vehicle or platform name string (e.g., 'AU 416_2B')", 
            "drawing_number": "Drawing / part number string (Sachnummer)", 
            "part_description": "Assembly specification description string (e.g., 'LL Cockpit')",
            "QK_score": 0.0, 
            "auditor_name": "Auditor full name string (e.g., 'Horrich Kawther')", 
            "calculation_factor": 1.0, 
            "count_wires": 0, 
            "count_contacts": 0, 
            "count_components": 0, 
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
                
                # -------------------------------------------------------------
                # RECTIFICATION ET MAPPING DE SÉCURITÉ DEPUIS L'INDEX MAÎTRE
                # -------------------------------------------------------------
                drawing_no = str(harness_obj.get("drawing_number", "")).strip()
                
                if drawing_no in harness_registry:
                    harness_obj["audit_type"] = harness_registry[drawing_no]["audit_type"]
                    harness_obj["QK_score"] = harness_registry[drawing_no]["QK_score"]
                else:
                    # Garde-fou anti-overflow (si l'IA a confondu le score avec des points comme 300)
                    try:
                        val_qk = float(harness_obj.get("QK_score", 0.0))
                        if val_qk > 10.0:
                            harness_obj["QK_score"] = 0.0
                    except (ValueError, TypeError):
                        harness_obj["QK_score"] = 0.0
                
                harness_obj["raw_defects_list"] = extracted_defects
                harness_obj["defect_count"] = len(extracted_defects)
                harness_obj["defect_points"] = sum(int(d["points"]) for d in extracted_defects)
                
                all_harnesses.append(harness_obj)
                success = True  
                time.sleep(4.5)
                
            except Exception as e:
                if "Rate limit reached" in str(e):
                    match_wait = re.search(r"try again in ([0-9.]+)(s|ms)", str(e))
                    if match_wait:
                        wait_value = float(match_wait.group(1))
                        wait_time = wait_value if match_wait.group(2) == "s" else (wait_value / 1000.0)
                    else:
                        wait_time = 5.0
                        
                    print(f"⏳ Code 429 détecté. Pause intelligente de {wait_time + 1.5}s avant de réessayer la page {i+1}...", flush=True)
                    time.sleep(wait_time + 1.5)
                else:
                    print(f"⚠️ Erreur de traitement inconnue sur la page {i+1} : {e}", flush=True)
                    success = True  
                    time.sleep(3.0)

    # Calcul algorithmique final des métriques globales
    if all_harnesses and (summary_data.get("QK_avg") == 0.0 or summary_data.get("audits_count") == 0):
        scores = [float(h['QK_score']) for h in all_harnesses if h.get('QK_score') is not None]
        if scores:
            summary_data["QK_min"] = round(min(scores), 2)
            summary_data["QK_avg"] = round(sum(scores) / len(scores), 2)
            summary_data["QK_max"] = round(max(scores), 2)
            summary_data["audits_count"] = len(all_harnesses)

    return summary_data, all_harnesses