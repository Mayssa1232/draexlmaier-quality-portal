import streamlit as st
import pandas as pd
import sys
import os
import plotly.express as px
import streamlit_authenticator as stauth
import psycopg2
from psycopg2.extras import RealDictCursor

# Alias for compatibility with your existing workspace code
strl = st

# 1. PAGE CONFIGURATION (MUST BE ABSOLUTELY FIRST)
st.set_page_config(page_title="DRÄXLMAIER Quality Portal", layout="wide")

# --- PATH & IMPORT ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from run_pipeline import extract_dynamic_pdf_data, get_db_connection

# --- INJECT CUSTOM DARK DESIGN CSS IMMEDIATELY ---
# This styling applies to the login/registration interface at startup
# --- INJECT CUSTOM DARK DESIGN CSS IMMEDIATELY ---
# This styling applies to the login/registration interface at startup with the car background
# --- INJECT CUSTOM DARK DESIGN CSS IMMEDIATELY ---
# This styling applies to the login/registration interface at startup with the car background
# --- INJECT CUSTOM DARK DESIGN CSS IMMEDIATELY ---
# --- INJECT CUSTOM DARK DESIGN CSS IMMEDIATELY ---
# This styling applies to the login/registration interface at startup with the car background
initial_design_css = """
<style>
    /* Main Background with Car Image & Text Color */
    html, body, .stApp {
        background: linear-gradient(135deg, rgba(13, 14, 18, 0.88) 0%, rgba(22, 25, 32, 0.94) 100%),
                    url('https://images.unsplash.com/photo-1617788138017-80ad40651399?q=80&w=1920') no-repeat center center fixed !important;
        background-size: cover !important;
        color: #ffffff;
    }
    
    /* ─── NETTOYAGE COMPATIBLE DE LA DOUBLE LIGNE ─── */
    
    /* Cible l'indicateur rouge mobile par défaut de Streamlit pour le masquer complètement */
    [data-testid="stBaseButton-inline"], 
    [data-baseweb="tab-highlight"] {
        background-color: transparent !important;
        display: none !important;
    }

    /* Style des onglets d'authentification */
    .stTabs [data-baseweb="tab"] {
        color: #a3a8b4 !important;
        font-weight: 600 !important;
        border-bottom: 3px solid transparent !important; /* Réserve l'espace au repos */
        padding: 10px 20px !important;
    }
    
    /* LIGNE VERTE UNIQUE ET RETOUR DU TEXTE sur l'onglet sélectionné */
    .stTabs [aria-selected="true"] {
        color: #00ffd0 !important;
        border-bottom: 3px solid #00ffd0 !important; /* Notre ligne verte unique */
    }
    
    /* Style for Forms & Cards */
    div[data-testid="stForm"] {
        background-color: rgba(22, 27, 34, 0.85);
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 25px;
        backdrop-filter: blur(10px);
    }
    
    /* Inputs Styling */
    .stTextInput input {
        background-color: #0d1117 !important;
        color: #ffffff !important;
        border: 1px solid #30363d !important;
    }
    .stTextInput input:focus {
        border-color: #00ffd0 !important;
        box-shadow: 0 0 0 1px #00ffd0 !important;
    }
    
    /* Form Submit Buttons Styling */
    div[data-testid="stForm"] button {
        width: 100% !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        background-color: #21262d !important;
        color: #c9d1d9 !important;
        border: 1px solid #30363d !important;
        transition: 0.2s ease !important;
    }
    div[data-testid="stForm"] button:hover {
        background-color: #00ffd0 !important;
        color: #0e1117 !important;
        border-color: #00ffd0 !important;
    }
</style>
"""
st.markdown(initial_design_css, unsafe_allow_html=True)

# --- DYNAMIC USER LOAD FROM NEON DATABASE ---
def load_users_from_db():
    credentials = {"usernames": {}}
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT username, name, password_hash, email FROM users;")
        rows = cur.fetchall()
        for row in rows:
            credentials["usernames"][row["username"]] = {
                "name": row["name"],
                "password": row["password_hash"],
                "email": row["email"]
            }
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"Database connection error: {e}")
    return credentials

# Load all valid accounts
credentials = load_users_from_db()

# --- SECURE JWT INITIALIZATION ---
authenticator = stauth.Authenticate(
    credentials,
    'quality_portal_cookie',
    'une_cle_de_signature_tres_longue_et_securisee_draexlmaier_2026', # Compliant >32 bytes key
    cookie_expiry_days=30
)

# --- WELCOME GATE INTERFACE (LOGIN / REGISTRATION) ---
if not st.session_state.get("authentication_status"):
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center; color: #00ffd0;'>D-DRÄXLMAIER</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>Quality Audit Portal</h3>", unsafe_allow_html=True)
        
        auth_tab1, auth_tab2 = st.tabs(["🔑 Sign In", "📝 Create Account"])
        
        with auth_tab1:
            authenticator.login()
            if st.session_state.get("authentication_status") == False:
                st.error("Invalid username or password.")
            elif st.session_state.get("authentication_status") == None:
                st.info("Please log in to access the platform.")
                
        with auth_tab2:
            st.subheader("Register New Auditor Account")
            with st.form("registration_form", clear_on_submit=True):
                new_username = st.text_input("Username").strip().lower()
                new_name = st.text_input("Full Name")
                new_email = st.text_input("Professional Email Address").strip()
                new_password = st.text_input("Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                
                submit_reg = st.form_submit_button("Sign Up")
                
                if submit_reg:
                    if not new_username or not new_name or not new_email or not new_password:
                        st.error("All fields are required.")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match.")
                    elif "@" not in new_email:
                        st.error("Please enter a valid email address.")
                    else:
                        # Secure hashing compatible with stauth 0.3+
                        hashed_password = stauth.Hasher.hash(new_password)
                        
                        try:
                            conn = get_db_connection()
                            cur = conn.cursor()
                            cur.execute("SELECT username FROM users WHERE username = %s OR email = %s", (new_username, new_email))
                            if cur.fetchone():
                                st.error("This username or email is already taken.")
                            else:
                                cur.execute(
                                    "INSERT INTO users (username, name, password_hash, email) VALUES (%s, %s, %s, %s)",
                                    (new_username, new_name, hashed_password, new_email)
                                )
                                conn.commit()
                                st.success("Account created successfully! You can now log in.")
                                st.rerun()
                            cur.close()
                            conn.close()
                        except Exception as e:
                            st.error(f"Registration failed: {e}")

# =========================================================================
# --- SECURE WORKSPACE AREA (ALL EMBEDDED UNDER CONNECTED STATE) ---
# =========================================================================
if st.session_state.get("authentication_status"):
    name = st.session_state["name"]
    username = st.session_state["username"]
    
    # Sidebar logout configuration
    authenticator.logout('Log Out', 'sidebar')
    st.sidebar.title(f"Welcome, {name}")
    
    # Session state variable for relational filtering
    user_email_session = credentials['usernames'][username]['email']
    st.session_state['user_email'] = user_email_session

    # --- ADVANCED PRODUCTION GRAPHICS & BACKGROUND DESIGN ---
    # --- ADVANCED PRODUCTION GRAPHICS & BACKGROUND DESIGN ---
    production_design_css = """
    <style>
        html, body, .stApp {
            background: linear-gradient(135deg, rgba(13, 14, 18, 0.92) 0%, rgba(22, 25, 32, 0.96) 100%),
                        url('https://images.unsplash.com/photo-1617788138017-80ad40651399?q=80&w=1920') no-repeat center center fixed !important;
            background-size: cover !important;
            color: #ffffff;
        }
       
        .stSidebar { 
            background: rgba(13, 14, 18, 0.8) !important; 
            border-right: 1px solid #334155; 
        }

        /* Style for Workspace Tabs - RED line inside the platform */
        .stTabs button {
            color: #a3a8b4 !important;
            font-weight: 600 !important;
            background-color: transparent !important;
            border: none !important;
        }
        .stTabs button[aria-selected="true"] {
            color: #ff4b4b !important;
            border-bottom: 2px solid #ff4b4b !important; /* Red line replacing the green one */
        }

        /* Custom Action Buttons */
        .stButton>button {
            width: 100%;
            border-radius: 6px;
            font-weight: 600;
            background-color: rgba(30, 41, 59, 0.8) !important;
            color: #ffffff !important;
            border: 1px solid #475569 !important;
        }
        .stButton>button:hover, .stButton>button:active {
            background-color: rgba(47, 55, 105, 0.9) !important;
            border-color: #ff4b4b !important; /* Red highlight on hover inside */
        }

        /* File Uploader Custom Dark styling */
        .stFileUploader label p { color: #ffffff !important; }
        [data-testid="stFileUploaderDropzone"] {
            background-color: rgba(30, 41, 59, 0.5) !important;
            border: 2px dashed #475569 !important;
            border-radius: 8px !important;
        }
        [data-testid="stFileUploaderDropzone"] span,
        [data-testid="stFileUploaderDropzone"] small {
            color: #cbd5e1 !important;
        }
        [data-testid="stFileUploaderDropzone"] button {
            background-color: rgba(15, 23, 42, 0.9) !important;
            color: #ffffff !important;
            border: 1px solid #475569 !important;
        }
        [data-testid="stFileUploaderDropzone"] button:hover {
            background-color: rgba(30, 41, 59, 1) !important;
        }
    </style>
    """
    strl.markdown(production_design_css, unsafe_allow_html=True)

    # --- MULTI-TABLE INJECTION FUNCTION ---
    def save_to_database(summary, details, defects_list, occurrences_list):
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # 1. Monthly Summaries Table
            cur.execute("""
                INSERT INTO public.monthly_summaries
                (supplier, plant, country, report_month, report_year, QK_min, QK_avg, QK_max, audits_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING summary_id;
            """, (summary['supplier'], summary['plant'], summary['country'],
                  str(summary['report_month']), str(summary['report_year']),
                  summary['QK_min'], summary['QK_avg'], summary['QK_max'], summary['audits_count']))
            summary_id = cur.fetchone()[0]

            # 2. Harness Audits Table
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

            # 3. Audit Defects Raw Table
            for d in defects_list:
                cur.execute("INSERT INTO public.audit_defects_raw (audit_id, defect_code, penalty_points) VALUES (%s, %s, %s);",
                            (audit_id_map[d['drawing_number']], d['defect_code'], d['penalty_points']))

            # 4. PDF Total Occurrences Table
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
            # --- WIPE DATABASE FUNCTION (PRESERVING USERS) ---
    def clear_production_database():
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # Cascading truncate or delete on audit and summary tables
            cur.execute("TRUNCATE TABLE public.audit_defects_raw RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE TABLE public.pdf_total_occurrences RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE TABLE public.harness_audits RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE TABLE public.monthly_summaries RESTART IDENTITY CASCADE;")
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

    # --- SIDEBAR COMPONENTS ---
    with strl.sidebar:
        if os.path.exists("logo.png"): 
            strl.image("logo.png", use_column_width=True)
        strl.markdown("<h2 style='text-align: center;'>D-DRÄXLMAIER</h2>", unsafe_allow_html=True)
        strl.markdown("<p style='text-align: center; color: #94a3b8;'>Automotive System Quality</p>", unsafe_allow_html=True)
# --- SIDEBAR COMPONENTS ---
    with strl.sidebar:
        if os.path.exists("logo.png"): 
        strl.image("logo.png", use_column_width=True)
        strl.markdown("<h2 style='text-align: center;'>D-DRÄXLMAIER</h2>", unsafe_allow_html=True)
        strl.markdown("<p style='text-align: center; color: #94a3b8;'>Automotive System Quality</p>", unsafe_allow_html=True)
        
        strl.markdown("---")
        strl.markdown("<h4 style='color: #ff4b4b;'>⚠️ Danger Zone</h4>", unsafe_allow_html=True)
        
        # Confirmation Checkbox to avoid accidental clicks
        confirm_wipe = strl.checkbox("I understand this will erase all quality logs")
        
        if strl.button(" Wipe Database Data", disabled=not confirm_wipe):
            try:
                clear_production_database()
                strl.success(" Database successfully cleared!")
                # Immediate rerun to refresh tables and dashboard live
                strl.rerun()
            except Exception as e:
                strl.error(f"Failed to clear database: {str(e)}")
    # --- WORKSPACE TABS ---
    tab1, tab2, tab3 = strl.tabs(["DATA INTAKE PORTAL", "QUALITY ANALYTICS REGISTER", "VIEW DASHBOARD"])

    # --- DATA INTAKE ---
    with tab1:
        strl.header("Data Intake Portal")
        uploaded_file = strl.file_uploader("Upload Compliance PDF", type=["pdf"])
        
        if uploaded_file and strl.button(" Inject into  Database"):
            try:
                summary, details = extract_dynamic_pdf_data(uploaded_file.read())
                
                defects = []
                occurrences = []
                for h in details:
                    for d in h.get("raw_defects_list", []):
                        defects.append({
                            "drawing_number": h["drawing_number"],
                            "defect_code": d["code"],
                            "penalty_points": d["points"]
                        })
                        occ_found = next((o for o in occurrences if o["defect_code"] == d["code"]), None)
                        if occ_found: 
                            occ_found["total_count"] += 1
                        else: 
                            occurrences.append({"defect_code": d["code"], "total_count": 1})

                strl.write("Injection in progress...")
                save_to_database(summary, details, defects, occurrences)
                strl.success("✅ Data successfully injected into all tables!")
                
            except Exception as e:
                strl.error(f"Injection Failed: {str(e)}")
                strl.exception(e)

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
                if not df1.empty:
                    strl.dataframe(df1.drop(columns=['summary_id'], errors='ignore'), use_container_width=True)

            with subtab2:
                query2 = """
                    SELECT s.plant, h.* FROM public.harness_audits h
                    JOIN public.monthly_summaries s ON h.summary_id = s.summary_id
                """
                df2 = pd.read_sql(query2, conn)
                if not df2.empty:
                    strl.dataframe(df2.drop(columns=['summary_id', 'audit_id'], errors='ignore'), use_container_width=True)

            with subtab3:
                query3 = """
                    SELECT s.plant, d.* FROM public.audit_defects_raw d
                    JOIN public.harness_audits h ON d.audit_id = h.audit_id
                    JOIN public.monthly_summaries s ON h.summary_id = s.summary_id
                """
                df3 = pd.read_sql(query3, conn)
                if not df3.empty:
                    strl.dataframe(df3.drop(columns=['audit_id'], errors='ignore'), use_container_width=True)

            with subtab4:
                query4 = """
                    SELECT s.plant, o.* FROM public.pdf_total_occurrences o
                    JOIN public.monthly_summaries s ON o.summary_id = s.summary_id
                """
                df4 = pd.read_sql(query4, conn)
                if not df4.empty:
                    strl.dataframe(df4.drop(columns=['summary_id'], errors='ignore'), use_container_width=True)

            conn.close()
        except Exception as e:
            strl.error(f"Error loading registers: {str(e)}")

    # --- DASHBOARD ---
    with tab3:
        strl.header("Performance Dashboard")
        try:
            conn = get_db_connection()
            df_dash = pd.read_sql("SELECT plant, qk_avg FROM public.monthly_summaries", conn)
            conn.close()
            
            if not df_dash.empty:
                fig = px.bar(df_dash, x='plant', y='qk_avg', title="QK Average per Plant", color='qk_avg')
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', 
                    plot_bgcolor='rgba(0,0,0,0)',
                    font_color="#ffffff",
                    title_font_color="#ffffff"
                )
                strl.plotly_chart(fig, use_container_width=True)
            else:
                strl.info("Dashboard awaiting production data...")
        except Exception as e:
            strl.error(f"Dashboard Load Error: {str(e)}")