import streamlit as strl
import pandas as pd
import sys
import os
import plotly.express as px

# --- PATH & IMPORT ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from run_pipeline import extract_dynamic_pdf_data, get_db_connection

strl.set_page_config(page_title="DRÄXLMAIER Quality Portal", layout="wide")

# --- CSS & DESIGN (ARRIÈRE-PLAN VOITURE) ---
design_css = """
<style>
    html, body, .stApp { 
        background: linear-gradient(135deg, rgba(13, 14, 18, 0.92) 0%, rgba(22, 25, 32, 0.96) 100%), 
                    url('https://images.unsplash.com/photo-1617788138017-80ad40651399?q=80&w=1920') no-repeat center center fixed !important; 
        background-size: cover !important; 
        color: #ffffff; 
    }
    .stSidebar { background: rgba(13, 14, 18, 0.8) !important; border-right: 1px solid #334155; }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: 600; }
</style>
"""
strl.markdown(design_css, unsafe_allow_html=True)

# --- FONCTION D'INJECTION MULTI-TABLES (5 COUCHES) ---
def save_to_database(summary, details, defects_list, occurrences_list):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 1. Monthly Summaries
        cur.execute("""
            INSERT INTO public.monthly_summaries 
            (supplier, plant, country, report_month, report_year, QK_min, QK_avg, QK_max, audits_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING summary_id;
        """, (summary['supplier'], summary['plant'], summary['country'], 
              str(summary['report_month']), str(summary['report_year']), 
              summary['QK_min'], summary['QK_avg'], summary['QK_max'], summary['audits_count']))
        summary_id = cur.fetchone()[0]

        # 2. Harness Audits
        audit_id_map = {}
        for r in details:
            cur.execute("""
                INSERT INTO public.harness_audits 
                (summary_id, vehicle_type, drawing_number, part_description, QK_score, defect_count, defect_points, auditor_name, calculation_factor, count_wires, count_contacts, count_components, audit_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING audit_id;
            """, (summary_id, r['vehicle_type'], r['drawing_number'], r['part_description'], r['QK_score'], 
                  r['defect_count'], r['defect_points'], r['auditor_name'], r['calculation_factor'], 
                  r['count_wires'], r['count_contacts'], r['count_components'], r['audit_type']))
            audit_id_map[r['drawing_number']] = cur.fetchone()[0]

        # 3. Audit Defects Raw
        for d in defects_list:
            cur.execute("INSERT INTO public.audit_defects_raw (audit_id, defect_code, penalty_points) VALUES (%s, %s, %s);",
                        (audit_id_map[d['drawing_number']], d['defect_code'], d['penalty_points']))

        # 4. PDF Total Occurrences
        for o in occurrences_list:
            cur.execute("INSERT INTO public.pdf_total_occurrences (summary_id, defect_code, total_count) VALUES (%s, %s, %s);",
                        (summary_id, o['defect_code'], o['total_count']))

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

# --- SIDEBAR ---
with strl.sidebar:
    if os.path.exists("logo.png"): strl.image("logo.png", use_column_width=True)
    strl.markdown("<h2 style='text-align: center;'>D-DRÄXLMAIER</h2>", unsafe_allow_html=True)
    strl.markdown("<p style='text-align: center; color: #94a3b8;'>Automotive System Quality</p>", unsafe_allow_html=True)

# --- TABS ---
tab1, tab2, tab3 = strl.tabs(["DATA INTAKE PORTAL", "QUALITY ANALYTICS REGISTER", "VIEW DASHBOARD"])


# --- DATA INTAKE (DEBUG VERSION) ---
with tab1:
    strl.header("Data Intake Portal")
    uploaded_file = strl.file_uploader("Upload Compliance PDF", type=["pdf"])
    
    if uploaded_file and strl.button("🚀 Inject into Production Database"):
        try:
            # 1. Extraction (ensure this returns the 2 required elements)
            summary, details = extract_dynamic_pdf_data(uploaded_file.read())
            
            # 2. Local construction of lists for the 5 tables
            defects = []
            occurrences = []
            for h in details:
                for d in h.get("raw_defects_list", []):
                    defects.append({
                        "drawing_number": h["drawing_number"],
                        "defect_code": d["code"],
                        "penalty_points": d["points"]
                    })
                    # Aggregation for occurrences
                    occ_found = next((o for o in occurrences if o["defect_code"] == d["code"]), None)
                    if occ_found: occ_found["total_count"] += 1
                    else: occurrences.append({"defect_code": d["code"], "total_count": 1})

            # 3. Secure Injection
            strl.write("Injection in progress...")
            save_to_database(summary, details, defects, occurrences)
            
            # 4. Success message
            strl.success("✅ Data successfully injected into all 5 tables!")
            
        except Exception as e:
            # Displays the exact error in a red box
            strl.error(f"Injection Failed: {str(e)}")
            strl.exception(e) # Displays the complete technical stack trace


# --- ANALYTICS REGISTER ---
with tab2:
    strl.header("Quality Analytics Register")
    subtab1, subtab2, subtab3, subtab4 = strl.tabs([
        "Monthly Summaries", "Harness Audits", "Audit Defects", "Occurrences"
    ])

    try:
        conn = get_db_connection()

        with subtab1:
            df1 = pd.read_sql("SELECT * FROM public.monthly_summaries", conn)
            # On affiche tout sauf summary_id si vous préférez
            strl.dataframe(df1.drop(columns=['summary_id']), use_container_width=True)

        with subtab2:
            # JOIN pour récupérer le nom de la plante dans le tableau des audits
            query2 = """
                SELECT s.plant, h.* FROM public.harness_audits h
                JOIN public.monthly_summaries s ON h.summary_id = s.summary_id
            """
            df2 = pd.read_sql(query2, conn).drop(columns=['summary_id', 'audit_id'])
            strl.dataframe(df2, use_container_width=True)

        with subtab3:
            # JOIN pour récupérer le nom de la plante dans le tableau des défauts
            query3 = """
                SELECT s.plant, d.* FROM public.audit_defects_raw d
                JOIN public.harness_audits h ON d.audit_id = h.audit_id
                JOIN public.monthly_summaries s ON h.summary_id = s.summary_id
            """
            df3 = pd.read_sql(query3, conn).drop(columns=['audit_id'])
            strl.dataframe(df3, use_container_width=True)

        with subtab4:
            # JOIN pour récupérer le nom de la plante dans le tableau des occurrences
            query4 = """
                SELECT s.plant, o.* FROM public.pdf_total_occurrences o
                JOIN public.monthly_summaries s ON o.summary_id = s.summary_id
            """
            df4 = pd.read_sql(query4, conn).drop(columns=['summary_id'])
            strl.dataframe(df4, use_container_width=True)

        conn.close()
    except Exception as e:
        strl.error(f"Erreur : {str(e)}")
# --- DASHBOARD ---
# --- DASHBOARD (CORRECTED) ---
with tab3:
    strl.header("Performance Dashboard")
    try:
        conn = get_db_connection()
        # Querying the exact lowercase column names
        df_dash = pd.read_sql("SELECT plant, qk_avg FROM public.monthly_summaries", conn)
        conn.close()
        
        if not df_dash.empty:
            
            # FIX: ensure 'y' matches the column name 'qk_avg' exactly
            fig = px.bar(df_dash, x='plant', y='qk_avg', title="QK Average per Plant", color='qk_avg')
            strl.plotly_chart(fig, use_container_width=True)
        else:
            strl.info("Dashboard awaiting data...")
    except Exception as e:
        strl.error(f"Dashboard Load Error: {str(e)}")