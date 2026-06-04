# -*- coding: utf-8 -*-
import urllib.request
import urllib.error
import json
import logging
import time
import re

_logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# AJOUT : IMPORT ELASTICSEARCH
# ═══════════════════════════════════════════════════════════════
try:
    from .elasticsearch_service import match_competences_in_cv, is_elasticsearch_available
    ES_ENABLED = True
    _logger.info("✅ Module Elasticsearch chargé")
except ImportError:
    ES_ENABLED = False
    _logger.warning("⚠️ Elasticsearch non disponible - Fallback sur matching simple")

GEMINI_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
]
MAX_CV_CHARS = 15000

# ─────────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────────

def call_gemini(prompt, api_keys):
    """api_keys peut être une string ou une liste de clés."""
    if isinstance(api_keys, str):
        api_keys = [api_keys]

    base_url = "https://generativelanguage.googleapis.com/v1beta/models/"
    data = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}]
    }).encode('utf-8')

    for api_key in api_keys:
        for model in GEMINI_MODELS:
            url = f"{base_url}{model}:generateContent?key={api_key}"
            delais = [5, 15, 30]
            for tentative in range(4):
                try:
                    req = urllib.request.Request(url, data=data,
                        headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=60) as response:
                        result = json.loads(response.read().decode('utf-8'))
                        candidates = result.get('candidates', [])
                        if not candidates:
                            _logger.warning("Gemini réponse vide — modèle: %s", model)
                            break
                        parts = candidates[0].get('content', {}).get('parts', [])
                        if not parts:
                            _logger.warning("Gemini parts vide — modèle: %s", model)
                            break
                        return parts[0].get('text', '')
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        attente = delais[min(tentative, 2)]
                        _logger.warning("Quota dépassé — attente %ss...", attente)
                        time.sleep(attente)
                        continue
                    elif e.code in (503, 502, 500):
                        attente = delais[min(tentative, len(delais)-1)]
                        _logger.warning("Gemini indisponible (%s) — retry dans %ss...", e.code, attente)
                        time.sleep(attente)
                        continue
                    elif e.code == 404:
                        _logger.warning("Modèle %s indisponible, fallback...", model)
                        break
                    else:
                        raise e
                except Exception as e:
                    _logger.error("Erreur appel Gemini: %s", str(e))
                    break

    raise Exception("Toutes les clés API sont épuisées. Réessaie dans 1 minute.")


def _clean_json_response(response):
    """Nettoie la réponse Gemini pour extraire le JSON pur."""
    response = response.strip()
    if "```" in response:
        parts = response.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                response = part
                break
    if not response.startswith("{"):
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            response = match.group()
    return response.strip()


def strip_html(html):
    """Supprime les balises HTML."""
    if not html:
        return ''
    return re.sub(r'<[^>]+>', ' ', html).strip()


def _anonymiser(cv_text, anon_token):
    """Remplace emails et téléphones par le token anonyme."""
    cv_text = re.sub(
        r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
        anon_token, cv_text
    )
    cv_text = re.sub(
        r'(\+212|0)([ \-]?\d){9}',
        anon_token, cv_text
    )
    return cv_text


# ─────────────────────────────────────────────────
# COUCHE 2 — SCORING PYTHON /80
# ─────────────────────────────────────────────────

REGIONS_MAROC = {
    'casablanca':  ['casablanca', 'mohammedia', 'bouskoura', 'ain sebaa'],
    'rabat':       ['rabat', 'salé', 'sale', 'temara', 'kenitra', 'skhirat'],
    'marrakech':   ['marrakech', 'marrakesh'],
    'fes':         ['fès', 'fes', 'meknes', 'meknès'],
    'tanger':      ['tanger', 'tetouan', 'tétouan', 'al hoceima'],
    'agadir':      ['agadir', 'tiznit', 'taroudant'],
    'oujda':       ['oujda', 'nador'],
    'beni mellal': ['beni mellal', 'béni mellal', 'khouribga'],
}

NIVEAUX_FORMATION = {
    'bac': 1, 'bac2': 2, 'bac3': 3, 'bac5': 4, 'doctorat': 5, 'any': 0, 'other': 0
}


def calculer_score_python(infos_cv, offre_competences="", offre_experience_min=0,
                           offre_criteres="", offre_localisation="",
                           offre_niveau_formation="any", offre_competences_bonus="",
                           cv_text_full=""):
    """
    Couche 1 (knockout) + Couche 2 (scoring /80).
    Utilise Elasticsearch pour le matching de compétences si disponible.
    """
    comp_cv = [c.lower() for c in (infos_cv.get('competences') or [])]
    cv_text_lower = ' '.join(comp_cv) + ' ' + (infos_cv.get('resume') or '').lower()
    
    # ── COUCHE 1 : Knockout ──────────────────────────────────────
    if offre_criteres and offre_criteres.strip():
        criteres_list = [c.strip().lower() for c in offre_criteres.split(',') if c.strip()]

        def normaliser(texte):
            """Normalise le texte pour comparaison flexible."""
            texte = texte.lower()
            texte = texte.replace('bac+', 'bac')
            texte = texte.replace('+', '')
            texte = texte.replace('-', ' ')
            texte = re.sub(r'\s+', ' ', texte)
            return texte.strip()

        cv_text_full_lower = (cv_text_full or '').lower()
        cv_normalise = normaliser(
            cv_text_lower + ' ' + cv_text_full_lower + ' ' +
            ' '.join(infos_cv.get('competences') or [])
        )

        for critere in criteres_list:
            critere_normalise = normaliser(critere)
            if critere_normalise not in cv_normalise:
                _logger.info("Knockout — critère absent : %s", critere)
                return {
                    'score_python': 0, 'score_competences': 0,
                    'score_experience': 0, 'score_formation': 0, 'score_geo': 0,
                    'competences_matchees': [], 'competences_manquantes': criteres_list,
                    'knockout': True,
                    'knockout_raison': f"Critère obligatoire absent : {critere}",
                }
    
    # ═══════════════════════════════════════════════════════════════
    # COUCHE 2A : Compétences /20 (AVEC ELASTICSEARCH)
    # ═══════════════════════════════════════════════════════════════
    comp_requises = [c.strip() for c in offre_competences.split(',') if c.strip()] \
                    if offre_competences else []

    if comp_requises:
        # UTILISER ELASTICSEARCH SI DISPONIBLE
        if ES_ENABLED and is_elasticsearch_available():
            try:
                match_result = match_competences_in_cv(
                    comp_requises, 
                    cv_text_full or cv_text_lower
                )
                matchees = match_result['matchees']
                manquantes = match_result['manquantes']
                _logger.debug(
                    "✅ Matching ES : %d/%d compétences trouvées",
                    len(matchees), len(comp_requises)
                )
            except Exception as e:
                _logger.warning("⚠️ ES match échoué, fallback simple: %s", str(e))
                # Fallback sur méthode simple
                matchees = [c for c in comp_requises if c.lower() in cv_text_lower]
                manquantes = [c for c in comp_requises if c.lower() not in cv_text_lower]
        else:
            # Méthode simple si ES indisponible
            _logger.debug("ℹ️ Matching simple (ES indisponible)")
            matchees = [c for c in comp_requises if c.lower() in cv_text_lower]
            manquantes = [c for c in comp_requises if c.lower() not in cv_text_lower]
        
        score_comp = round((len(matchees) / len(comp_requises)) * 20)
    else:
        matchees = []
        manquantes = []
        score_comp = 10
    
    # ── BONUS : Compétences bonus ────────────────────────────────
    if offre_competences_bonus and offre_competences_bonus.strip():
        comp_bonus = [c.strip() for c in offre_competences_bonus.split(',') if c.strip()]
        
        # Utiliser ES pour les bonus aussi
        if ES_ENABLED and is_elasticsearch_available():
            try:
                bonus_result = match_competences_in_cv(
                    comp_bonus, 
                    cv_text_full or cv_text_lower
                )
                bonus_matchees = bonus_result['matchees']
            except:
                bonus_matchees = [c for c in comp_bonus if c.lower() in cv_text_lower]
        else:
            bonus_matchees = [c for c in comp_bonus if c.lower() in cv_text_lower]
        
        score_comp = min(score_comp + len(bonus_matchees), 20)

    # ── COUCHE 2B : Expérience /30 ──────────────────────────────
    exp_candidat = float(infos_cv.get('experience_years') or 0)
    exp_min = float(offre_experience_min or 0)

    if exp_min == 0:
        score_exp = 30
    elif exp_candidat >= exp_min:
        ratio = min(exp_candidat / exp_min, 1.5)
        score_exp = round(20 + (ratio - 1) * 20)
        score_exp = min(score_exp, 30)
    else:
        ratio = exp_candidat / exp_min if exp_min > 0 else 0
        score_exp = round(ratio * 15)

    # ── COUCHE 2C : Formation /20 ───────────────────────────────
    niveau_requis = NIVEAUX_FORMATION.get(offre_niveau_formation, 0)
    niveau_candidat = NIVEAUX_FORMATION.get(
        infos_cv.get('niveau_formation', 'other'), 0
    )

    if niveau_requis == 0:
        score_formation = 20
    elif niveau_candidat >= niveau_requis:
        score_formation = 20
    elif niveau_candidat == niveau_requis - 1:
        score_formation = 15
    else:
        score_formation = 5

    # ── COUCHE 2D : Géolocalisation /10 ─────────────────────────
    loc_offre_lower = (offre_localisation or '').strip().lower()
    loc_cv_lower = (infos_cv.get('localisation') or '').strip().lower()

    if not loc_offre_lower:
        score_geo = 10
    elif loc_cv_lower in loc_offre_lower or loc_offre_lower in loc_cv_lower:
        score_geo = 10
    else:
        region_offre = None
        region_cv = None
        for r, villes in REGIONS_MAROC.items():
            if any(v in loc_offre_lower for v in villes):
                region_offre = r
            if any(v in loc_cv_lower for v in villes):
                region_cv = r
        
        if region_offre and region_offre == region_cv:
            score_geo = 8
        elif region_cv:
            score_geo = 4
        else:
            score_geo = 0

    # ── Score Python total /80 ───────────────────────────────────
    score_python = score_comp + score_exp + score_formation + score_geo

    return {
        'score_python': score_python,
        'score_competences': score_comp,
        'score_experience': score_exp,
        'score_formation': score_formation,
        'score_geo': score_geo,
        'competences_matchees': matchees,
        'competences_manquantes': manquantes,
        'knockout': False,
        'knockout_raison': '',
    }


# ═══════════════════════════════════════════════════════════════
# PHASE A - NOUVELLES FONCTIONS SÉPARÉES
# ═══════════════════════════════════════════════════════════════

def extraire_infos_cv(cv_text, api_key, candidat_id=None):
    """
    PHASE A - EXTRACTION SEULEMENT (2 secondes).
    
    Extrait uniquement les informations du CV sans évaluation qualitative.
    Utilisé pour le workflow rapide d'extraction.
    
    Retourne:
        dict avec: nom, email, competences, experience, formation, etc.
    """
    anon_token = f"[CANDIDAT_{candidat_id or 'X'}]"
    cv_truncated = _anonymiser(cv_text[:MAX_CV_CHARS], anon_token)

    prompt = f"""Tu es un expert RH. Extrais les informations de ce CV de maniere exhaustive :

CONSIGNES :
- Pour localisation : extrais la ville du candidat
- Extrais TOUTES les competences techniques ET soft skills
- Sois precis sur l'experience (annees + mois)

CV A ANALYSER :
---
{cv_truncated}
---

Structure JSON a retourner :
{{
  "nom": "{anon_token}",
  "email": "{anon_token}",
  "telephone": "{anon_token}",
  "localisation": "ex: Casablanca",
  "competences": ["competence1", "competence2"],
  "experience_years": 2.5,
  "experience_annees": 2,
  "experience_mois": 5,
  "formation": "ex: Licence en Gestion",
  "niveau_formation": "bac3",
  "langues": ["Francais", "Anglais", "Arabe"],
  "secteurs": ["Finance", "Comptabilite"],
  "resume": "Resume professionnel en 2-3 phrases."
}}

Retourne uniquement le JSON :"""

    response = call_gemini(prompt, api_key)
    response = _clean_json_response(response)

    try:
        result = json.loads(response)
    except json.JSONDecodeError as e:
        _logger.error("Gemini JSON invalide : %s | Reponse : %s", str(e), response)
        return _default_infos()

    # Validation infos
    if not isinstance(result.get('competences'), list):
        result['competences'] = []
    if not isinstance(result.get('langues'), list):
        result['langues'] = []
    if not isinstance(result.get('secteurs'), list):
        result['secteurs'] = []
    try:
        result['experience_years'] = float(result.get('experience_years') or 0)
    except (ValueError, TypeError):
        result['experience_years'] = 0.0
    try:
        result['experience_annees'] = int(result.get('experience_annees') or 0)
    except (ValueError, TypeError):
        result['experience_annees'] = 0
    try:
        result['experience_mois'] = int(result.get('experience_mois') or 0)
    except (ValueError, TypeError):
        result['experience_mois'] = 0

    return result


def evaluer_cv_qualite(cv_text, infos_cv, api_key, candidat_id=None,
                       offre_titre="", offre_description="", offre_profil=""):
    """
    PHASE A - SCORING GEMINI SEULEMENT (15 secondes).
    
    Évalue la qualité du candidat par rapport à l'offre.
    Utilisé APRÈS l'extraction pour compléter le scoring.
    
    Args:
        cv_text: Texte du CV
        infos_cv: Infos déjà extraites (de extraire_infos_cv)
        offre_titre, offre_description, offre_profil: Contexte de l'offre
    
    Retourne:
        dict avec: score_gemini, points_forts, points_faibles, resume_qualitatif
    """
    anon_token = f"[CANDIDAT_{candidat_id or 'X'}]"
    cv_truncated = _anonymiser(cv_text[:MAX_CV_CHARS], anon_token)
    
    # Résumé des infos déjà extraites
    competences_str = ', '.join(infos_cv.get('competences', [])[:10])
    exp_str = f"{infos_cv.get('experience_annees', 0)} ans {infos_cv.get('experience_mois', 0)} mois"
    
    prompt = f"""Tu es un expert RH. Evalue ce candidat pour cette offre.

CANDIDAT (infos extraites) :
- Competences : {competences_str}
- Experience : {exp_str}
- Formation : {infos_cv.get('formation', 'Non specifie')}
- Localisation : {infos_cv.get('localisation', 'Non specifie')}

OFFRE :
- Titre : {offre_titre}
- Description : {offre_description or "Non fournie"}
- Profil recherche : {offre_profil or "Non fourni"}

CV COMPLET :
---
{cv_truncated}
---

CONSIGNES :
- Evalue la pertinence du CV par rapport a l'offre sur 20 points (score_gemini)
- Mets en avant 2-3 points forts du candidat pour ce poste
- Indique 1-2 points faibles ou gaps evidentes
- Resume en 2-3 phrases pourquoi ce candidat conviendrait ou non

Structure JSON a retourner :
{{
  "score_gemini": 15,
  "points_forts": "Solide experience en...",
  "points_faibles": "Manque de...",
  "resume_qualitatif": "Candidat interessant car..."
}}

Retourne uniquement le JSON :"""

    response = call_gemini(prompt, api_key)
    response = _clean_json_response(response)

    try:
        result = json.loads(response)
    except json.JSONDecodeError as e:
        _logger.error("Gemini JSON invalide : %s | Reponse : %s", str(e), response)
        return {
            'score_gemini': 0,
            'points_forts': '',
            'points_faibles': 'Erreur évaluation Gemini',
            'resume_qualitatif': ''
        }

    # Validation score_gemini
    try:
        result['score_gemini'] = max(0, min(20, int(float(result.get('score_gemini') or 0))))
    except (ValueError, TypeError):
        result['score_gemini'] = 0

    return result


# ─────────────────────────────────────────────────
# FONCTION LEGACY (Compatibilité)
# ─────────────────────────────────────────────────

def extraire_et_evaluer_cv(cv_text, api_key, candidat_id=None,
                            offre_titre="", offre_description="",
                            offre_profil="", has_offre=False):
    """
    LEGACY - Maintenue pour compatibilité.
    Utilise les nouvelles fonctions en interne.
    """
    # Extraction
    infos = extraire_infos_cv(cv_text, api_key, candidat_id)
    
    # Évaluation si offre
    if has_offre:
        evaluation = evaluer_cv_qualite(
            cv_text, infos, api_key, candidat_id,
            offre_titre, offre_description, offre_profil
        )
        return {**infos, **evaluation}
    else:
        return {
            **infos,
            'score_gemini': 0,
            'points_forts': '',
            'points_faibles': '',
            'resume_qualitatif': ''
        }


# ─────────────────────────────────────────────────
# ORCHESTRATEUR PRINCIPAL (Legacy compatible)
# ─────────────────────────────────────────────────

def analyser_et_scorer_cv(cv_text, api_key,
                           offre_titre="", offre_competences="",
                           offre_experience_min=0, offre_criteres="",
                           offre_description="", offre_profil="",
                           offre_localisation="", offre_niveau_formation="any",
                           offre_competences_bonus="", 
                           candidat_id=None):
    """
    Orchestrateur LEGACY — 1 seul appel Gemini + Python pour le scoring.
    Maintenu pour compatibilité avec ancien code.
    
    1. Gemini : extraction infos + evaluation qualitative /20
    2. Python : calcul score /80 (deterministe)
    Total = score_python + score_gemini = /100
    """
    has_offre = bool(offre_titre)

    # ── Appel Gemini unique ──────────────────────────────────────
    gemini_result = extraire_et_evaluer_cv(
        cv_text=cv_text,
        api_key=api_key,
        candidat_id=candidat_id,
        offre_titre=offre_titre,
        offre_description=offre_description,
        offre_profil=offre_profil,
        has_offre=has_offre,
    )

    # ── Scoring Python /80 ───────────────────────────────────────
    if has_offre:
        scoring = calculer_score_python(
            infos_cv=gemini_result,
            offre_competences=offre_competences,
            offre_experience_min=offre_experience_min,
            offre_criteres=offre_criteres,
            offre_localisation=offre_localisation,
            offre_niveau_formation=offre_niveau_formation,
            offre_competences_bonus=offre_competences_bonus,
            cv_text_full=cv_text, 
        )
    else:
        scoring = {
            'score_python': 0, 'score_competences': 0,
            'score_experience': 0, 'score_formation': 0, 'score_geo': 0,
            'competences_matchees': [], 'competences_manquantes': [],
            'knockout': False, 'knockout_raison': '',
        }

    # ── Knockout ─────────────────────────────────────────────────
    if scoring.get('knockout'):
        return {
            **gemini_result,
            'score_python': 0, 'score_gemini': 0, 'score_total': 0,
            'score_competences': 0, 'score_experience': 0,
            'score_formation': 0, 'score_geo': 0,
            'competences_matchees': scoring.get('competences_matchees', []),
            'competences_manquantes': scoring.get('competences_manquantes', []),
            'points_forts': '',
            'points_faibles': scoring.get('knockout_raison', ''),
            'recommandation': 'REJETER',
        }

    # ── Score final ──────────────────────────────────────────────
    score_gemini = gemini_result.get('score_gemini', 0)
    score_total = scoring['score_python'] + score_gemini

    recommandation = (
        'SHORTLIST' if score_total >= 70 else
        'ENTRETIEN' if score_total >= 45 else
        'REJETER'
    )

    return {
        **gemini_result,
        'score_python': scoring['score_python'],
        'score_gemini': score_gemini,
        'score_total': score_total,
        'score_competences': scoring['score_competences'],
        'score_experience': scoring['score_experience'],
        'score_formation': scoring['score_formation'],
        'score_geo': scoring['score_geo'],
        'competences_matchees': scoring['competences_matchees'],
        'competences_manquantes': scoring['competences_manquantes'],
        'points_forts': gemini_result.get('points_forts', ''),
        'points_faibles': gemini_result.get('points_faibles', ''),
        'resume_qualitatif': gemini_result.get('resume_qualitatif', ''),
        'recommandation': recommandation,
    }


# ─────────────────────────────────────────────────
# VALEURS PAR DÉFAUT
# ─────────────────────────────────────────────────

def _default_infos():
    return {
        "nom": "", "email": "", "telephone": "", "localisation": "",
        "competences": [], "experience_years": 0.0,
        "experience_annees": 0, "experience_mois": 0,
        "formation": "", "niveau_formation": "other",
        "langues": [], "secteurs": [], "resume": "",
    }


def _default_result():
    return {
        **_default_infos(),
        "score_python": 0.0, "score_gemini": 0.0, "score_total": 0.0,
        "score_competences": 0.0, "score_experience": 0.0,
        "score_formation": 0.0, "score_geo": 0.0,
        "competences_matchees": [], "competences_manquantes": [],
        "points_forts": "", "points_faibles": "", "recommandation": "ENTRETIEN",
    }


# ─────────────────────────────────────────────────
# COMPATIBILITÉ
# ─────────────────────────────────────────────────

def analyser_cv_avec_gemini(cv_text, api_key):
    return analyser_et_scorer_cv(cv_text, api_key)


def scorer_cv_avec_gemini(cv_text, offre_titre, offre_competences,
                           offre_experience_min, offre_criteres, api_key,
                           offre_description="", offre_profil=""):
    return analyser_et_scorer_cv(
        cv_text, api_key,
        offre_titre=offre_titre,
        offre_competences=offre_competences,
        offre_experience_min=offre_experience_min,
        offre_criteres=offre_criteres,
        offre_description=offre_description,
        offre_profil=offre_profil,
    )