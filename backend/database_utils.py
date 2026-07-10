import psycopg2
from psycopg2 import extras
import re  # <-- RAJOUTÉ : Pour utiliser les Expressions Régulières

def get_db_connection():
    """Gère la connexion à PostgreSQL sur le port actif (5432 ou 5433)."""
    try:
        return psycopg2.connect(user="postgres", password="2002", host="127.0.0.1", port="5432", database="quality_db")
    except psycopg2.OperationalError:
        return psycopg2.connect(user="postgres", password="2002", host="127.0.0.1", port="5433", database="quality_db")

def save_audit_data(summary_data, harness_rows):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Insertion dans la table parente (monthly_summaries) avec les nouveaux champs anglais et QK
        summary_query = """
        INSERT INTO monthly_summaries (supplier, site, country, month, year, QK_min, QK_avg, QK_max, audits_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING summary_id;
        """
        cursor.execute(summary_query, (
            summary_data['supplier'],
            summary_data['plant'],         # 'site' corrigé en 'plant'
            summary_data['country'],
            summary_data['report_month'],  # 'month' corrigé en 'report_month'
            summary_data['report_year'],   # 'year' corrigé en 'report_year'
            summary_data['QK_min'],        # 'qk_min' corrigé en 'QK_min'
            summary_data['QK_avg'],        # 'qk_avg' corrigé en 'QK_avg'
            summary_data['QK_max'],        # 'qk_max' corrigé en 'QK_max'
            summary_data['audits_count']
        ))
        summary_id = cursor.fetchone()[0]

        # 2. Préparation des requêtes pour les tables enfants
        harness_query = """
        INSERT INTO harness_audits (
            summary_id, vehicle_type, drawing_number, part_description, 
            QK_score, defect_count, defect_points, auditor_name,
            calculation_factor, count_wires, count_contacts, count_components, audit_type
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING audit_id;
        """
        
        # Requête pour l'insertion séquentielle brute dans 'audit_defects_raw'
        raw_defect_query = """
        INSERT INTO audit_defects_raw (audit_id, defect_code, penalty_points)
        VALUES (%s, %s, %s);
        """

        # Dictionnaire Python pour calculer les occurrences totales sur TOUT le fichier PDF
        global_defect_counts = {}

        # Traitement ligne par ligne des faisceaux
        for row in harness_rows:
            cursor.execute(harness_query, (
                summary_id,
                row['vehicle_type'],
                row['drawing_number'],
                row['part_description'],
                row['QK_score'],            # 'qk_score' corrigé en 'QK_score'
                row['defect_count'],
                row['defect_points'],
                row['auditor_name'],
                row['calculation_factor'],
                row['count_wires'],
                row['count_contacts'],
                row['count_components'],
                row['audit_type']
            ))
            
            audit_id = cursor.fetchone()[0]
            
            # 3. Insertion brute unitaire dans la table 'audit_defects_raw'
            if 'raw_defects_list' in row and row['raw_defects_list']:
                for defect in row['raw_defects_list']:
                    code = defect.get('code')
                    points = defect.get('points', 0)
                    
                    if code:
                        # --- DEBUT DE LA MODIFICATION ---
                        # On applique la règle : si le code contient "2D", il DOIT commencer par "2D" suivi d'un espace.
                        # S'il y a "2D" mais qu'il est noyé au milieu d'un mot ou d'une phrase de création, on l'ignore.
                        if "2D" in code:
                            # On nettoie le texte pour enlever d'éventuels espaces parasites en début de chaîne
                            code_nettoye = code.strip()
                            
                            # Si le code ne commence pas par "2D" suivi d'un espace, on passe au défaut suivant (ignore)
                            if not re.match(r'^2D\s+', code_nettoye):
                                continue  # Saute cette ligne et passe au prochain élément du dictionnaire
                        # --- FIN DE LA MODIFICATION ---

                        # Insertion brute de la ligne validée
                        cursor.execute(raw_defect_query, (audit_id, code, points))
                        
                        # Calcul mathématique de l'occurrence globale exécuté par Python
                        global_defect_counts[code] = global_defect_counts.get(code, 0) + 1

        # 4. Insertion des cumuls d'occurrences calculés dans la table globale 'pdf_total_occurrences'
        pdf_occurrence_query = """
        INSERT INTO pdf_total_occurrences (summary_id, defect_code, total_count)
        VALUES (%s, %s, %s);
        """
        for defect_code, total_count in global_defect_counts.items():
            cursor.execute(pdf_occurrence_query, (summary_id, defect_code, total_count))

        # Validation définitive de la transaction SQL
        conn.commit()
        print(f"Succès ! Synthèse mensuelle sauvegardée (ID: {summary_id}) avec {len(harness_rows)} audits de câblage.")
        print(f"Calcul global : {len(global_defect_counts)} codes défauts distincts agrégés pour Power BI.")

    except Exception as e:
        if conn:
            conn.rollback()
        print("Database Error:", e)
        raise e
    finally:
        if conn:
            cursor.close()
            conn.close()