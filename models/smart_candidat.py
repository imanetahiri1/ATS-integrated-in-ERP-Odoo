from email.mime import text
import logging
import re
from odoo import models, fields, api
from odoo.exceptions import ValidationError

# PHASE B : Import queue_job pour jobs asynchrones
try:
    from odoo.addons.queue_job.job import job
    QUEUE_JOB_AVAILABLE = True
except ImportError:
    QUEUE_JOB_AVAILABLE = False
    # Fallback decorator si queue_job non installé
    def job(func):
        return func

_logger = logging.getLogger(__name__)


def strip_html(html):
    """Supprime les balises HTML."""
    if not html:
        return ''
    return re.sub(r'<[^>]+>', ' ', html).strip()

def _extraire_identite_locale(text):
    """Extrait nom, email, téléphone depuis le texte brut du CV."""
    email = ""
    phone = ""
    nom = ""

    # Email
    email_match = re.search(r'[\w.+\-]+@[\w.\-]+\.[a-zA-Z]{2,}', text)
    if email_match:
        email = email_match.group()

    # Téléphone marocain
    phone_match = re.search(r'(\+212|0)([ \-]?\d){9}', text)
    if phone_match:
        phone = phone_match.group().replace(' ', '').replace('-', '')

    # Mots à ignorer
    MOTS_IGNORES = {
        'contact', 'cv', 'curriculum', 'vitae', 'resume', 'résumé',
        'profil', 'profile', 'information', 'informations', 'personnelles',
        'coordonnees', 'coordonnées', 'présentation', 'presentation',
        'nom', 'prénom', 'adresse', 'téléphone', 'email', 'objet',
        'candidature', 'spontanée', 'lettre', 'motivation',
        'experience', 'expérience', 'formation', 'compétences',
        'competences', 'langues', 'languages', 'objectif', 'objective',
        'références', 'references', 'centres', 'intérêt', 'interet',
        'qualités', 'qualites', 'education', 'educations',
        'technicien', 'ingénieur', 'ingenieur', 'assistant', 'assistante',
        'développeur', 'developpeur', 'gestionnaire', 'manager',
        'aide', 'déclarant', 'declarant', 'douane', 'comptable',
        'cariste', 'magasinier', 'coursier', 'préparateur',
        'spécialisé', 'specialise', 'spécialise',
    }

    def compacter_lettres(line):
        """Compacte les lettres espacées : 'A B D E L' → 'ABDEL'"""
        isolated = re.findall(r'\b[A-ZÉÈÀÂÙÎÔÛa-zéèàâùîôû]\b', line)
        if len(isolated) >= 3:
            return line.replace(' ', '')
        if re.match(r'^([A-ZÉÈÀÂÙÎÔÛa-zéèàâùîôû] ){2,}', line):
            return re.sub(r'(?<=\w) (?=\w(?:\s|$))', '', line).strip()
        return line

    def est_mot_ignore(line):
        line_lower = line.lower().strip()
        if line_lower in MOTS_IGNORES:
            return True
        for mot in MOTS_IGNORES:
            if mot in line_lower:
                return True
        return False

    def mettre_en_title(texte):
        """Convertit en Title Case en respectant les tirets."""
        mots = texte.split()
        result = []
        for mot in mots:
            if '-' in mot:
                result.append('-'.join(p.capitalize() for p in mot.split('-')))
            else:
                result.append(mot.capitalize())
        return ' '.join(result)

    def est_nom_valide(line):
        """Vérifie si une ligne ressemble à un nom de personne."""
        if len(line) < 4 or len(line) > 50:
            return False
        if '@' in line:
            return False
        if re.search(r'\d', line):
            return False
        if est_mot_ignore(line):
            return False
        mots = line.split()
        if len(mots) < 2 or len(mots) > 5:
            return False
        for mot in mots:
            mot_clean = mot.replace('-', '')
            if not mot_clean:
                continue
            if not mot_clean[0].isupper():
                return False
        return True

    lines = text.split('\n')
    lines_clean = [l.strip() for l in lines if l.strip()]

    # PASS 1 : Nom sur une seule ligne (15 premières lignes)
    for line in lines_clean[:15]:
        line_compactee = compacter_lettres(line)
        line_title = mettre_en_title(line_compactee)
        if est_nom_valide(line_title):
            nom = line_title
            break

    # PASS 2 : Nom sur 2 lignes consécutives
    if not nom:
        for i in range(min(10, len(lines_clean) - 1)):
            l1 = compacter_lettres(lines_clean[i].strip())
            l2 = compacter_lettres(lines_clean[i + 1].strip())
            if re.search(r'\d|@', l1) or re.search(r'\d|@', l2):
                continue
            if est_mot_ignore(l1) or est_mot_ignore(l2):
                continue
            if (len(l1.split()) <= 2 and len(l2.split()) <= 2
                    and len(l1) >= 2 and len(l2) >= 2
                    and l1.replace('-','').replace(' ','').isalpha()
                    and l2.replace('-','').replace(' ','').isalpha()):
                combined = f"{l1} {l2}"
                combined_title = mettre_en_title(combined)
                if est_nom_valide(combined_title):
                    nom = combined_title
                    break

    # PASS 3 : Fallback
    if not nom:
        for line in lines_clean[:10]:
            if (len(line) > 3 and len(line) < 50
                    and '@' not in line
                    and not re.search(r'\d{3,}', line)
                    and not est_mot_ignore(line)):
                nom = line
                break

    return nom, email, phone

class SmartCandidat(models.Model):
    _name = "smart.candidat"
    _description = "Candidat Smart Recruitment AI"
    _order = "ai_score desc, id desc"
    
    # Informations de base
    name = fields.Char(string="Nom complet", required=True, default="Nouveau")
    email = fields.Char(string="Email")
    phone = fields.Char(string="Téléphone")
    localisation = fields.Char(string="Ville / Localisation")
    
    # Champs alignés RTP
    region = fields.Char(string="Région")
    birth_date = fields.Date(string="Date de naissance")
    gender = fields.Selection([
        ('M', 'Homme'),
        ('F', 'Femme'),
        ('autre', 'Autre'),
    ], string="Genre")
    current_title = fields.Char(string="Poste actuel / Dernier poste")
    sector = fields.Char(string="Secteur d'activité")
    salary_expectation = fields.Char(string="Prétentions salariales")
    availability = fields.Selection([
        ('immediat', 'Immédiat'),
        ('moins_1_mois', 'Préavis < 1 mois'),
        ('1_3_mois', 'Préavis 1-3 mois'),
        ('plus_3_mois', 'Préavis > 3 mois'),
    ], string="Disponibilité")
    parsed_data = fields.Text(
        string="Données parsées RTP (JSON)",
        readonly=True
    )
    rtp_candidate_id = fields.Char(
        string="ID Candidat RTP",
        readonly=True
    )
    date_disponibilite = fields.Date(string="Disponible à partir du")
    niveau_formation = fields.Selection([
        ('bac', 'Bac'),
        ('bac2', 'Bac+2'),
        ('bac3', 'Bac+3'),
        ('bac5', 'Bac+5'),
        ('doctorat', 'Doctorat'),
        ('other', 'Autre'),
    ], string="Niveau de formation")
    formation_detail = fields.Char(string="Diplôme / Formation")
    langues = fields.Char(string="Langues")
    resume_profil = fields.Text(string="Résumé du profil")

    # Source
    source = fields.Selection([
        ('linkedin', 'LinkedIn'),
        ('marocannonce', 'MarocAnnonce'),
        ('website', 'Site web'),
        ('email', 'Email'),
        ('sharepoint', 'SharePoint'),
        ('import_masse', 'Import massif'),
        ('other', 'Autre'),
    ], string="Source", default='other')

    # CV
    cv_file = fields.Binary(string="CV (PDF / DOCX / Image)", attachment=True)
    cv_filename = fields.Char(string="Nom du fichier CV")
    cv_text = fields.Text(string="Texte extrait du CV", readonly=True)
    parse_errors = fields.Text(string="Erreurs de parsing", readonly=True)

    # Lien offre
    job_id = fields.Many2one('smart.offre', string="Offre d'emploi", ondelete='set null')
    
    # Lien vers applicant
    applicant_id = fields.Many2one(
        'hr.applicant',
        string="Candidature Odoo",
        ondelete='set null',
        help="Lien vers la candidature dans le module RH natif (Kanban)"
    )

    # Étape Kanban pour le drag & drop
    stage_id = fields.Many2one('hr.recruitment.stage', string="Étape Kanban")
    
    # Analyse IA
    competences_cv = fields.Text(string="Compétences détectées")
    experience_years = fields.Float(string="Années d'expérience", default=0.0)
    experience_annees = fields.Integer(string="Années", default=0)
    experience_mois = fields.Integer(string="Mois", default=0)
    experience_display = fields.Char(
        string="Expérience",
        compute='_compute_experience_display',
        store=False
    )

    @api.depends('experience_annees', 'experience_mois')
    def _compute_experience_display(self):
        for rec in self:
            rec.experience_display = f"{rec.experience_annees} an(s) / {rec.experience_mois} mois"

    # Scoring
    ai_score = fields.Float(string="Score Final (/100)", default=0.0, digits=(5, 2))
    ai_rank = fields.Integer(string="Rang", default=0)
    score_python = fields.Float(string="Score Python (/80)", default=0.0, digits=(5, 2))
    score_gemini = fields.Float(string="Score Gemini (/20)", default=0.0, digits=(5, 2))
    score_competences = fields.Float(string="Score compétences (/20)", default=0.0)
    score_experience = fields.Float(string="Score expérience (/30)", default=0.0)
    score_formation = fields.Float(string="Score formation (/20)", default=0.0)
    score_geo = fields.Float(string="Score proximité géo (/10)", default=0.0)
    competences_matchees = fields.Text(string="Compétences matchées")
    competences_manquantes = fields.Text(string="Compétences manquantes")
    points_forts = fields.Text(string="Points forts")
    points_faibles = fields.Text(string="Points faibles")
    recommandation_ia = fields.Selection([
        ('SHORTLIST', 'Shortlist'),
        ('ENTRETIEN', 'Entretien'),
        ('REJETER', 'Rejeter'),
    ], string="Recommandation IA")
    matching_details = fields.Text(string="Détails du matching (JSON brut)")
    is_scored = fields.Boolean(string="Scoré", default=False)
    scoring_info = fields.Text(
        string="Info Scoring",
        readonly=True,
        help="Explication du type de scoring utilisé"   
    )
    
    # Statut
    shortlisted = fields.Boolean(string="Shortlisté", default=False)
    state = fields.Selection([
        ('new', 'Nouveau'),
        ('extracting', 'Extraction en cours...'),
        ('extracted', 'Extrait (prêt pour scoring)'),
        ('scoring', 'Scoring en cours...'),
        ('scored', 'Scoré'),
        ('analyzed', 'Analysé'),
        ('shortlisted', 'Shortlisté'),
        ('rejected', 'Rejeté'),
    ], string="Statut", default='new')
    source_ajout = fields.Selection([
        ('auto', 'Ajouté automatiquement (SharePoint)'),
        ('import_masse', 'Importé en masse'),
        ('manuel', 'Ajouté manuellement (PC)'),
    ], string='Source ajout', default='manuel', readonly=True)
    score_display = fields.Char(
        string="Score",
        compute='_compute_score_display',
        store=False
    )
    
    # Champs computed pour détecter le type de fichier CV
    is_cv_pdf = fields.Boolean(
        string="CV est PDF",
        compute="_compute_cv_file_type",
        store=False
    )

    is_cv_image = fields.Boolean(
        string="CV est Image",
        compute="_compute_cv_file_type",
        store=False
    )

    is_cv_docx = fields.Boolean(
        string="CV est Word",
        compute="_compute_cv_file_type",
        store=False
    )

    @api.depends('cv_filename')
    def _compute_cv_file_type(self):
        """Détecte le type de fichier CV pour l'affichage conditionnel."""
        for rec in self:
            filename_lower = (rec.cv_filename or '').lower()
            
            rec.is_cv_pdf = filename_lower.endswith('.pdf')
            rec.is_cv_image = filename_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp'))
            rec.is_cv_docx = filename_lower.endswith(('.docx', '.doc'))

    @api.depends('ai_score')
    def _compute_score_display(self):
        for rec in self:
            rec.score_display = f"{rec.ai_score:.1f} / 100"

    def _get_api_keys(self):
        """Récupère la clé API Gemini unique."""
        key = self.env['ir.config_parameter'].sudo().get_param(
            'smart_recruitment.gemini_api_key'
        )
        if key and key.strip():
            return [key.strip()]
        return []
    
    # ==========================================
    # VALIDATIONS DES DONNÉES
    # ==========================================
    
    @api.constrains('email')
    def _check_email(self):
        """Valider le format de l'email."""
        for rec in self:
            if rec.email and not re.match(r'^[\w.+\-]+@[\w.\-]+\.[a-zA-Z]{2,}$', rec.email):
                raise ValidationError(
                    f"Format d'email invalide : {rec.email}\n"
                    "Exemple valide : candidat@example.com"
                )
    
    @api.constrains('phone')
    def _check_phone(self):
        """Valider le numéro de téléphone marocain."""
        for rec in self:
            if rec.phone:
                # Nettoyer le numéro (enlever espaces et tirets)
                clean = rec.phone.replace(' ', '').replace('-', '')
                
                # Format marocain : +212XXXXXXXXX ou 0XXXXXXXXX
                if not re.match(r'^(\+212|0)[5-7]\d{8}$', clean):
                    raise ValidationError(
                        f"Numéro de téléphone invalide : {rec.phone}\n"
                        "Formats acceptés :\n"
                        "• +212612345678 (mobile)\n"
                        "• 0612345678 (mobile)\n"
                        "• 0512345678 (fixe)"
                    )
    
    @api.constrains('cv_file', 'cv_filename')
    def _check_cv_file(self):
        """Valider le fichier CV (taille et extension)."""
        for rec in self:
            if rec.cv_file and rec.cv_filename:
                # Vérifier la taille (max 10 MB)
                file_size_mb = len(rec.cv_file) / (1024 * 1024)
                if file_size_mb > 10:
                    raise ValidationError(
                        f"Le fichier CV est trop volumineux : {file_size_mb:.1f} MB\n"
                        "Taille maximale autorisée : 10 MB"
                    )
                
                # Vérifier l'extension
                ext = rec.cv_filename.lower().split('.')[-1] if '.' in rec.cv_filename else ''
                allowed_extensions = ['pdf', 'docx', 'doc', 'jpg', 'jpeg', 'png', 'gif', 'bmp']
                
                if ext not in allowed_extensions:
                    raise ValidationError(
                        f"Format de fichier non supporté : .{ext}\n"
                        f"Formats acceptés : {', '.join(allowed_extensions)}"
                    )
    
    @api.constrains('birth_date')
    def _check_birth_date(self):
        """Valider la date de naissance."""
        for rec in self:
            if rec.birth_date:
                today = fields.Date.today()
                age = (today - rec.birth_date).days / 365.25
                
                if rec.birth_date > today:
                    raise ValidationError(
                        "La date de naissance ne peut pas être dans le futur"
                    )
                
                if age < 16:
                    raise ValidationError(
                        f"L'âge doit être d'au moins 16 ans (actuellement {age:.0f} ans)"
                    )
                
                if age > 100:
                    raise ValidationError(
                        f"L'âge ne peut pas dépasser 100 ans (actuellement {age:.0f} ans)"
                    )
    
    @api.constrains('experience_years', 'experience_annees')
    def _check_experience(self):
        """Valider les années d'expérience."""
        for rec in self:
            if rec.experience_years and rec.experience_years < 0:
                raise ValidationError(
                    "Les années d'expérience ne peuvent pas être négatives"
                )
            
            if rec.experience_annees and rec.experience_annees < 0:
                raise ValidationError(
                    "Les années d'expérience ne peuvent pas être négatives"
                )
            
            # Vérifier cohérence avec l'âge
            if rec.birth_date and rec.experience_years:
                today = fields.Date.today()
                age = (today - rec.birth_date).days / 365.25
                
                if rec.experience_years > (age - 16):
                    raise ValidationError(
                        f"L'expérience ({rec.experience_years} ans) est incohérente avec l'âge ({age:.0f} ans)\n"
                        "On ne peut pas avoir plus d'expérience que (âge - 16 ans)"
                    )
    
    @api.constrains('ai_score', 'score_python', 'score_gemini')
    def _check_scores(self):
        """Valider que les scores sont dans les limites."""
        for rec in self:
            if rec.ai_score and (rec.ai_score < 0 or rec.ai_score > 100):
                raise ValidationError(
                    f"Le score final doit être entre 0 et 100 (actuellement {rec.ai_score})"
                )
            
            if rec.score_python and (rec.score_python < 0 or rec.score_python > 100):
                raise ValidationError(
                    f"Le score Python doit être entre 0 et 100 (actuellement {rec.score_python})"
                )
            
            if rec.score_gemini and (rec.score_gemini < 0 or rec.score_gemini > 100):
                raise ValidationError(
                    f"Le score Gemini doit être entre 0 et 100 (actuellement {rec.score_gemini})"
                )
    
    def recevoir_depuis_rtp(self, data):
        """
        Reçoit un candidat depuis RHS Talent Platform via API Push.
        """
        import json

        email = data.get('email', '')
        rtp_id = data.get('rtp_candidate_id') or data.get('id', '')

        existant = self.env['smart.candidat'].search([
            '|',
            ('email', '=', email),
            ('rtp_candidate_id', '=', str(rtp_id)),
        ], limit=1)

        if existant:
            _logger.info("Candidat RTP déjà présent, ignoré : %s", email)
            return {'status': 'skipped', 'id': existant.id}

        mission_ref = data.get('job_offers') or data.get('mission_ref') or data.get('offre_id')
        offre = False
        if mission_ref:
            offre = self.env['smart.offre'].search([
                ('reference_externe', '=', str(mission_ref))
            ], limit=1)

        skills = data.get('skills', [])
        if isinstance(skills, list):
            competences_str = ', '.join(skills)
        else:
            competences_str = str(skills)

        languages = data.get('languages', [])
        if isinstance(languages, list):
            langues_str = ', '.join([
                f"{l.get('lang', '')} ({l.get('level', '')})"
                if isinstance(l, dict) else str(l)
                for l in languages
            ])
        else:
            langues_str = str(languages)

        education_map = {
            'bac': 'bac', 'bac2': 'bac2', 'bac3': 'bac3',
            'bac4': 'bac5',
            'bac5': 'bac5', 'doctorat': 'doctorat',
        }
        education_level = education_map.get(
            data.get('education_level', ''), 'other'
        )

        availability = data.get('availability', False)

        first = data.get('first_name', '')
        last = data.get('last_name', '')
        nom = f"{first} {last}".strip() or email or 'Nouveau'

        vals = {
            'name': nom,
            'email': email or False,
            'phone': data.get('phone') or False,
            'localisation': data.get('city') or False,
            'region': data.get('region') or False,
            'niveau_formation': education_level,
            'experience_years': float(data.get('total_experience_years') or 0),
            'experience_annees': int(float(data.get('total_experience_years') or 0)),
            'experience_mois': round(
                (float(data.get('total_experience_years') or 0) % 1) * 12
            ),
            'competences_cv': competences_str or False,
            'langues': langues_str or False,
            'current_title': data.get('current_title') or False,
            'sector': data.get('sector') or False,
            'salary_expectation': data.get('salary_expectation') or False,
            'availability': availability or False,
            'cv_text': data.get('raw_text') or False,
            'source': data.get('source') or 'website',
            'source_ajout': 'auto',
            'job_id': offre.id if offre else False,
            'parsed_data': json.dumps(
                data.get('parsed_data', {}), ensure_ascii=False
            ) if data.get('parsed_data') else False,
            'rtp_candidate_id': str(rtp_id) if rtp_id else False,
            'state': 'new',
            'cv_file': data.get('cv_base64') or False,
            'cv_filename': data.get('cv_filename') or 'cv.pdf',
        }

        candidat = self.create(vals)
        _logger.info("Candidat reçu depuis RTP : %s (ID: %s)", nom, candidat.id)

        if offre and candidat.cv_text:
            try:
                candidat.calculer_score_python_seulement()
                _logger.info("Scoring Python automatique lancé pour : %s", nom)
            except Exception as e:
                _logger.warning("Scoring Python échoué pour %s: %s", nom, str(e))

        return {'status': 'created', 'id': candidat.id}

    def calculer_score_python_seulement(self):
        """
        PHASE 1 : Scoring Python uniquement, SANS Gemini.
        Fonctionne TOUJOURS, même sans clé API Gemini.
        Si poids_gemini = 0 ou pas de clé API, normalise le score sur 100.
        """
        # FAILLE 1.2 : extraction auto si cv_text vide
        if not self.job_id:
            return
        if not self.cv_text and self.cv_file:
            try:
                from ..services.cv_parser import extract_text_from_cv
                text, errors = extract_text_from_cv(self.cv_file, self.cv_filename or 'cv.pdf')
                if text:
                    self.cv_text = text
                    self.parse_errors = errors or False
            except Exception as e:
                _logger.warning("Extraction texte échouée: %s", str(e))
        if not self.cv_text:
            return
        
        try:
            from ..services.gemini_service import calculer_score_python
            
            # FAILLE 1.3 : bloc dupliqué supprimé
            
            # Extraction identité locale
            nom_local, email_local, phone_local = _extraire_identite_locale(self.cv_text)
            
            # Extraire les infos basiques du CV
            infos_cv = {
                'competences': [c.strip() for c in (self.competences_cv or '').split(',') if c.strip()],
                'experience_years': self.experience_years or 0.0,
                'experience_annees': self.experience_annees or 0,
                'experience_mois': self.experience_mois or 0,
                'niveau_formation': self.niveau_formation or 'other',
                'localisation': self.localisation or '',
                'resume': self.resume_profil or '',
            }
            
            offre = self.job_id
            
            # Calcul score Python uniquement (/80)
            scoring = calculer_score_python(
                infos_cv=infos_cv,
                offre_competences=offre.competences_requises or "",
                offre_experience_min=offre.experience_min or 0,
                offre_criteres=offre.criteres_obligatoires or "",
                offre_localisation=offre.localisation or "",
                offre_niveau_formation=offre.niveau_formation or "any",
                offre_competences_bonus=offre.competences_bonus or "",
                cv_text_full=self.cv_text,
            )
            
            # Récupération pondérations
            poids_comp = offre.poids_competences or 20.0
            poids_exp = offre.poids_experience or 30.0
            poids_form = offre.poids_formation or 20.0
            poids_geo = offre.poids_geo or 10.0
            # FAILLE 1.4 : poids_gemini corrigé
            poids_gemini = offre.poids_gemini if offre.poids_gemini is not False else 0.0
            
            # Scores bruts Python
            score_comp_brut = scoring['score_competences']
            score_exp_brut = scoring['score_experience']
            score_form_brut = scoring['score_formation']
            score_geo_brut = scoring['score_geo']
            
            # Normalisation avec pondérations
            score_comp_pondere = (score_comp_brut / 20.0) * poids_comp
            score_exp_pondere = (score_exp_brut / 30.0) * poids_exp
            score_form_pondere = (score_form_brut / 20.0) * poids_form
            score_geo_pondere = (score_geo_brut / 10.0) * poids_geo
            
            score_python_pondere = (
                score_comp_pondere + 
                score_exp_pondere + 
                score_form_pondere + 
                score_geo_pondere
            )
            
            # FAILLE 1.5 : NORMALISATION SUR 100 si Gemini désactivé OU pas de clé API
            api_keys = self._get_api_keys()
            if poids_gemini == 0 or not api_keys:
                # Normaliser le score Python sur 100
                total_poids_python = poids_comp + poids_exp + poids_form + poids_geo
                if total_poids_python > 0:
                    score_final = (score_python_pondere / total_poids_python) * 100.0
                else:
                    score_final = 0.0
                _logger.info(
                    "Candidat %s: Gemini indisponible - Score Python normalisé: %.1f/100",
                    self.name, score_final
                )
            else:
                # Score temporaire (sera complété par Gemini)
                score_final = score_python_pondere
            
            # Mise à jour du candidat
            vals = {
                'score_python': score_python_pondere,
                'score_competences': score_comp_brut,
                'score_experience': score_exp_brut,
                'score_formation': score_form_brut,
                'score_geo': score_geo_brut,
                'ai_score': score_final,
                'score_gemini': 0,
                'competences_matchees': ', '.join(scoring.get('competences_matchees', [])),
                'competences_manquantes': ', '.join(scoring.get('competences_manquantes', [])),
                # FAILLE 1.6 : is_scored corrigé
                'is_scored': (poids_gemini == 0 or not api_keys),
                'name': nom_local or self.cv_filename or 'Nouveau',
                'email': email_local or self.email or False,
                'phone': phone_local or self.phone or False,
                # FAILLE 1.7 : scoring_info corrigé
                'scoring_info': "✅ Scoring Python uniquement - Gemini indisponible" if (poids_gemini == 0 or not api_keys) else "⏳ Scoring Python - En attente de Gemini",
            }
            
            # Si knockout, rejeter directement
            if scoring.get('knockout'):
                vals.update({
                    'state': 'rejected',
                    'shortlisted': False,
                    'points_faibles': scoring.get('knockout_raison', ''),
                })
                self.write(vals)
                _logger.info(
                    "Candidat %s rejeté (knockout Python) : %s",
                    self.name, scoring.get('knockout_raison')
                )
                return
            
            # DÉPLACEMENT AUTOMATIQUE SELON SCORE
            seuil_shortlist = offre.seuil_shortlist or 70.0
            seuil_rejet = offre.seuil_rejet or 50.0
            
            if score_final >= seuil_shortlist:
                vals.update({
                    'state': 'shortlisted',
                    'shortlisted': True
                })
                msg_gemini = " - Prêt pour Gemini" if (poids_gemini > 0 and api_keys) else " - Score final"
                _logger.info(
                    "Candidat %s shortlisté (score: %.1f >= %.1f)%s",
                    self.name, score_final, seuil_shortlist, msg_gemini
                )
                
            elif score_final < seuil_rejet:
                vals.update({
                    'state': 'rejected',
                    'shortlisted': False
                })
                _logger.info(
                    "Candidat %s rejeté (score: %.1f < %.1f)",
                    self.name, score_final, seuil_rejet
                )
                
            else:
                vals['state'] = 'analyzed'
                _logger.info(
                    "Candidat %s en attente (score: %.1f entre %.1f et %.1f)",
                    self.name, score_final, seuil_rejet, seuil_shortlist
                )
            
            self.write(vals)
            
            # DÉPLACEMENT AUTOMATIQUE DANS LE KANBAN ODOO
            try:
                self._move_to_kanban_stage()
            except Exception as e:
                _logger.warning(
                    "Déplacement Kanban échoué pour %s: %s",
                    self.name, str(e)
                )
            
        except Exception as e:
            _logger.error(
                "Erreur scoring Python pour candidat %s: %s",
                self.name, str(e)
            )
    
    def action_extraire_cv(self):
        """
        PHASE A - EXTRACTION RAPIDE.
        """
        for rec in self:
            if not rec.cv_file:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Attention',
                        'message': "Veuillez d'abord uploader un CV.",
                        'type': 'warning',
                    }
                }
            
            rec.write({'state': 'extracting'})
            self.env.cr.commit()
            
            try:
                from ..services.cv_parser import extract_text_from_cv
                from ..services.gemini_service import extraire_infos_cv
                
                text, errors = extract_text_from_cv(rec.cv_file, rec.cv_filename or 'cv.pdf')
                if not text:
                    rec.write({'state': 'new', 'parse_errors': errors or "Extraction échouée"})
                    self.env.cr.commit()
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Extraction échouée',
                            'message': errors or "Impossible de lire ce fichier.",
                            'type': 'warning',
                        }
                    }
                
                nom_local, email_local, phone_local = _extraire_identite_locale(text)
                
                api_keys = rec._get_api_keys()
                
                if api_keys:
                    try:
                        infos = extraire_infos_cv(text, api_keys, rec.id)
                    except Exception as e:
                        _logger.warning("Extraction Gemini échouée: %s", str(e))
                        infos = {
                            'competences': [], 'experience_years': 0.0,
                            'experience_annees': 0, 'experience_mois': 0,
                            'niveau_formation': 'other', 'formation': '',
                            'localisation': '', 'langues': [], 'resume': ''
                        }
                else:
                    infos = {
                        'competences': [], 'experience_years': 0.0,
                        'experience_annees': 0, 'experience_mois': 0,
                        'niveau_formation': 'other', 'formation': '',
                        'localisation': '', 'langues': [], 'resume': ''
                    }
                
                vals = {
                    'cv_text': text,
                    'parse_errors': errors or False,
                    'name': nom_local or rec.cv_filename or 'Nouveau',
                    'email': email_local or rec.email or False,
                    'phone': phone_local or rec.phone or False,
                    'competences_cv': ', '.join(infos.get('competences', [])) if infos.get('competences') else '',
                    'experience_years': infos.get('experience_years', 0.0),
                    'experience_annees': infos.get('experience_annees', 0),
                    'experience_mois': infos.get('experience_mois', 0),
                    'formation_detail': infos.get('formation') or False,
                    'niveau_formation': infos.get('niveau_formation') or False,
                    'langues': ', '.join(infos.get('langues', [])) if infos.get('langues') else False,
                    'resume_profil': infos.get('resume') or False,
                    'localisation': infos.get('localisation') or rec.localisation or False,
                    'state': 'extracted',
                }
                
                rec.write(vals)
                self.env.cr.commit()
                
                if rec.job_id:
                    try:
                        rec.calculer_score_python_seulement()
                        self.env.cr.commit()
                        _logger.info("✅ Extraction + Scoring Python pour %s", rec.name)
                    except Exception as e:
                        _logger.warning("Scoring Python échoué après extraction: %s", str(e))
                        self.env.cr.rollback()
                        self.env.cr.commit()
                
                nb_comp = len(infos.get('competences', []))
                exp = vals.get('experience_years', 0)
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Extraction terminée',
                        'message': f"{nb_comp} compétences | {exp} ans exp.\nPrêt pour scoring Gemini !",
                        'type': 'success',
                        'sticky': False,
                    }
                }
                
            except Exception as e:
                _logger.error("Erreur extraction CV [%s]: %s", rec.name, str(e))
                rec.write({'state': 'new'})
                self.env.cr.rollback()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Erreur',
                        'message': f"Erreur: {str(e)[:100]}",
                        'type': 'danger',
                    }
                }
        
    def action_analyser_cv(self):
        """
        PHASE 2 : Analyse CV complète + scoring Gemini (/20).
        """
        for rec in self:
            if not rec.cv_file:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Attention',
                        'message': "Veuillez d'abord uploader un CV.",
                        'type': 'warning',
                    }
                }
            
            offre = rec.job_id
            
            poids_gemini = offre.poids_gemini if offre.poids_gemini is not False else 0.0
            
            if poids_gemini == 0:
                _logger.info(
                    "Gemini désactivé (poids=0) pour candidat %s - Scoring Python uniquement",
                    rec.name
                )
                rec.calculer_score_python_seulement()
                rec.write({'scoring_info': "✅ Scoring Python uniquement - Gemini désactivé (poids=0)"})
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Analyse terminée',
                        'message': f"Score Python: {rec.ai_score:.1f}/100 (Gemini désactivé)",
                        'type': 'success',
                        'sticky': False,
                    }
                }
            
            api_keys = rec._get_api_keys()
            if not api_keys:
                _logger.warning(
                    "Clé API Gemini manquante pour candidat %s - Fallback sur scoring Python",
                    rec.name
                )
                rec.calculer_score_python_seulement()
                rec.write({'scoring_info': "⚠️ Scoring Python uniquement - Clé API Gemini manquante"})
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Clé API manquante',
                        'message': (
                            f'Score Python: {rec.ai_score:.1f}/100\n'
                            'Configurez la clé Gemini pour le scoring complet.'
                        ),
                        'type': 'warning',
                        'sticky': True,
                    }
                }

            try:
                from ..services.cv_parser import extract_text_from_cv
                from ..services.gemini_service import analyser_et_scorer_cv

                text, errors = extract_text_from_cv(rec.cv_file, rec.cv_filename or 'cv.pdf')
                if not text:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Extraction échouée',
                            'message': errors or "Impossible de lire ce fichier.",
                            'type': 'warning',
                        }
                    }
                
                nom_local, email_local, phone_local = _extraire_identite_locale(text)

                result = analyser_et_scorer_cv(
                    cv_text=text,
                    api_key=api_keys,
                    offre_titre=offre.name if offre else "",
                    offre_competences=offre.competences_requises or "" if offre else "",
                    offre_experience_min=offre.experience_min or 0 if offre else 0,
                    offre_criteres=offre.criteres_obligatoires or "" if offre else "",
                    offre_description=strip_html(offre.description) if offre else "",
                    offre_profil=strip_html(offre.profil_recherche) if offre else "",
                    offre_localisation=offre.localisation or "" if offre else "",
                    offre_niveau_formation=offre.niveau_formation or "any" if offre else "any",
                    offre_competences_bonus=offre.competences_bonus or "",  
                    candidat_id=rec.id,
                )
                
                score_comp_brut = result.get('score_competences', 0.0)
                score_exp_brut = result.get('score_experience', 0.0)
                score_form_brut = result.get('score_formation', 0.0)
                score_geo_brut = result.get('score_geo', 0.0)
                score_gemini_brut = result.get('score_gemini', 0.0)

                if offre:
                    poids_comp = offre.poids_competences or 20.0
                    poids_exp = offre.poids_experience or 30.0
                    poids_form = offre.poids_formation or 20.0
                    poids_geo = offre.poids_geo or 10.0
                    # FAILLE 1.8 : poids_gemini_val corrigé
                    poids_gemini_val = offre.poids_gemini if offre.poids_gemini is not False else 0.0
                else:
                    poids_comp = 20.0
                    poids_exp = 30.0
                    poids_form = 20.0
                    poids_geo = 10.0
                    poids_gemini_val = 0.0
                
                score_comp_pondere = (score_comp_brut / 20.0) * poids_comp
                score_exp_pondere = (score_exp_brut / 30.0) * poids_exp
                score_form_pondere = (score_form_brut / 20.0) * poids_form
                score_geo_pondere = (score_geo_brut / 10.0) * poids_geo
                score_gemini_pondere = (score_gemini_brut / 20.0) * poids_gemini_val
                
                score_python_pondere = (
                    score_comp_pondere + 
                    score_exp_pondere + 
                    score_form_pondere + 
                    score_geo_pondere
                )
                
                score_final = score_python_pondere + score_gemini_pondere
                
                _logger.info(
                    f"Scoring candidat {rec.name}: "
                    f"Comp={score_comp_pondere:.1f} + Exp={score_exp_pondere:.1f} + "
                    f"Form={score_form_pondere:.1f} + Geo={score_geo_pondere:.1f} + "
                    f"Gemini={score_gemini_pondere:.1f} = {score_final:.1f}/100"
                )

                competences = result.get('competences') or []
                langues = result.get('langues') or []
                recommandation = result.get('recommandation', 'ENTRETIEN')

                vals = {
                    'competences_cv': ', '.join(competences) if competences else '',
                    'experience_years': result.get('experience_years') or 0.0,
                    'experience_annees': result.get('experience_annees') or 0,
                    'experience_mois': result.get('experience_mois') or 0,
                    'formation_detail': result.get('formation') or False,
                    'niveau_formation': result.get('niveau_formation') or False,
                    'langues': ', '.join(langues) if langues else False,
                    'resume_profil': result.get('resume') or False,
                    'localisation': result.get('localisation') or False,
                    'score_python': score_python_pondere,
                    'score_gemini': score_gemini_pondere,
                    'ai_score': score_final,
                    'score_competences': score_comp_brut,
                    'score_experience': score_exp_brut,
                    'score_formation': score_form_brut,
                    'score_geo': score_geo_brut,
                    'competences_matchees': ', '.join(result.get('competences_matchees') or []),
                    'competences_manquantes': ', '.join(result.get('competences_manquantes') or []),
                    'points_forts': result.get('points_forts') or False,
                    'points_faibles': result.get('points_faibles') or False,
                    'recommandation_ia': recommandation if recommandation in ('SHORTLIST', 'ENTRETIEN', 'REJETER') else 'ENTRETIEN',
                    'matching_details': str(result),
                    'is_scored': True,
                    'state': 'analyzed',
                    'cv_text': text or '',
                    'parse_errors': errors or False,
                    'name': nom_local or rec.cv_filename or 'Nouveau',
                    'email': email_local or False,
                    'phone': phone_local or False,
                    'scoring_info': f"✅ Scoring complet (Python: {score_python_pondere:.1f} + Gemini: {score_gemini_pondere:.1f})",
                }

                rec.write(vals)

                if offre:
                    seuil_shortlist = offre.seuil_shortlist or 70.0
                    seuil_rejet = offre.seuil_rejet or 50.0
                    
                    if score_final >= seuil_shortlist:
                        rec.write({'state': 'shortlisted', 'shortlisted': True})
                    elif score_final < seuil_rejet:
                        rec.write({'state': 'rejected', 'shortlisted': False})
                    else:
                        rec.write({'state': 'analyzed'})

                if offre:
                    try:
                        offre._recompute_ranks()
                    except Exception as e:
                        _logger.warning("Recompute ranks ignoré: %s", str(e))

                try:
                    rec._move_to_kanban_stage()
                except Exception as e:
                    _logger.warning("Déplacement Kanban échoué pour %s: %s", rec.name, str(e))

                nb_comp = len(competences)
                exp = vals.get('experience_years', 0)
                msg = f"{nb_comp} compétences | {exp} ans exp."
                if offre:
                    if score_final >= seuil_shortlist:
                        statut = "SHORTLISTÉ"
                    elif score_final < seuil_rejet:
                        statut = "REJETÉ"
                    else:
                        statut = "EN ATTENTE"
                    msg += f" | Score : {score_final:.1f}/100 | {statut}"

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Analyse terminée',
                        'message': msg,
                        'type': 'success',
                        'sticky': False,
                    }
                }

            except Exception as e:
                _logger.error("Erreur analyse CV [%s]: %s", rec.name, str(e))
                rec.write({'scoring_info': f"❌ Erreur API Gemini: {str(e)}\n✅ Fallback sur scoring Python uniquement"})
                rec.calculer_score_python_seulement()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Erreur Gemini - Fallback Python',
                        'message': f"Score Python: {rec.ai_score:.1f}/100\nErreur: {str(e)[:100]}",
                        'type': 'warning',
                    }
                }

    def action_scorer_gemini(self):
        """
        PHASE A - SCORING GEMINI SÉPARÉ.
        """
        for rec in self:
            if rec.state not in ('extracted', 'analyzed', 'scored'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Attention',
                        'message': "Extrayez d'abord le CV avant le scoring Gemini.",
                        'type': 'warning',
                    }
                }
            
            offre = rec.job_id
            if not offre:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Attention',
                        'message': "Aucune offre liée - scoring Gemini impossible.",
                        'type': 'warning',
                    }
                }
            
            # FAILLE 1.9 : poids_gemini corrigé
            poids_gemini = offre.poids_gemini if offre.poids_gemini is not False else 0.0
            if poids_gemini == 0:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Gemini désactivé',
                        'message': f"Poids Gemini = 0 pour cette offre.\nScore actuel: {rec.ai_score:.1f}/100",
                        'type': 'info',
                    }
                }
            
            api_keys = rec._get_api_keys()
            if not api_keys:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Clé API manquante',
                        'message': "Configurez la clé Gemini dans Configuration.",
                        'type': 'warning',
                    }
                }
            
            rec.write({'state': 'scoring'})
            self.env.cr.commit()
            
            try:
                from ..services.gemini_service import evaluer_cv_qualite
                
                infos_cv = {
                    'competences': [c.strip() for c in (rec.competences_cv or '').split(',') if c.strip()],
                    'experience_years': rec.experience_years or 0.0,
                    'experience_annees': rec.experience_annees or 0,
                    'experience_mois': rec.experience_mois or 0,
                    'formation': rec.formation_detail or '',
                    'niveau_formation': rec.niveau_formation or 'other',
                    'localisation': rec.localisation or '',
                    'resume': rec.resume_profil or '',
                }
                
                evaluation = evaluer_cv_qualite(
                    cv_text=rec.cv_text,
                    infos_cv=infos_cv,
                    api_key=api_keys,
                    candidat_id=rec.id,
                    offre_titre=offre.name,
                    offre_description=strip_html(offre.description) if offre.description else "",
                    offre_profil=strip_html(offre.profil_recherche) if offre.profil_recherche else "",
                )
                
                score_gemini_brut = evaluation.get('score_gemini', 0.0)
                score_gemini_pondere = (score_gemini_brut / 20.0) * poids_gemini
                score_final = rec.score_python + score_gemini_pondere
                
                vals = {
                    'score_gemini': score_gemini_pondere,
                    'ai_score': score_final,
                    'points_forts': evaluation.get('points_forts') or False,
                    'points_faibles': evaluation.get('points_faibles') or False,
                    'is_scored': True,
                    'state': 'scored',
                    'scoring_info': f"✅ Scoring complet (Python: {rec.score_python:.1f} + Gemini: {score_gemini_pondere:.1f})",
                }
                
                rec.write(vals)
                self.env.cr.commit()
                
                seuil_shortlist = offre.seuil_shortlist or 70.0
                seuil_rejet = offre.seuil_rejet or 50.0
                
                if score_final >= seuil_shortlist:
                    rec.write({'state': 'shortlisted', 'shortlisted': True})
                    statut = "SHORTLISTÉ"
                elif score_final < seuil_rejet:
                    rec.write({'state': 'rejected', 'shortlisted': False})
                    statut = "REJETÉ"
                else:
                    rec.write({'state': 'analyzed'})
                    statut = "EN ATTENTE"
                
                self.env.cr.commit()
                
                try:
                    rec._move_to_kanban_stage()
                    self.env.cr.commit()
                except Exception as e:
                    _logger.warning("Déplacement Kanban échoué: %s", str(e))
                
                try:
                    offre._recompute_ranks()
                except Exception as e:
                    _logger.warning("Recompute ranks échoué: %s", str(e))
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Scoring Gemini terminé',
                        'message': f"Score final: {score_final:.1f}/100 | {statut}",
                        'type': 'success',
                        'sticky': False,
                    }
                }
                
            except Exception as e:
                _logger.error("Erreur scoring Gemini [%s]: %s", rec.name, str(e))
                rec.write({
                    'state': 'extracted',
                    'scoring_info': f"❌ Erreur Gemini: {str(e)[:100]}"
                })
                self.env.cr.rollback()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Erreur Gemini',
                        'message': f"Erreur: {str(e)[:100]}",
                        'type': 'danger',
                    }
                }

    # ═══════════════════════════════════════════════════════════════
    # PHASE B - JOBS ASYNCHRONES
    # ═══════════════════════════════════════════════════════════════
    
    @job
    def _job_extraire_cv(self):
        return self.action_extraire_cv()
    
    @job
    def _job_scorer_gemini(self):
        return self.action_scorer_gemini()
    
    def action_extraire_cv_async(self):
        if not QUEUE_JOB_AVAILABLE:
            return self.action_extraire_cv()
        
        for rec in self:
            if not rec.cv_file:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Attention',
                        'message': "Veuillez d'abord uploader un CV.",
                        'type': 'warning',
                    }
                }
            
            rec.with_delay(
                channel='root.recruitment_extraction',
                priority=5,
                description=f"Extraction CV: {rec.name}"
            )._job_extraire_cv()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Extraction lancée',
                'message': "L'extraction se fait en arrière-plan.",
                'type': 'info',
                'sticky': False,
            }
        }
    
    def action_scorer_gemini_async(self):
        if not QUEUE_JOB_AVAILABLE:
            return self.action_scorer_gemini()
        
        for rec in self:
            if rec.state not in ('extracted', 'analyzed', 'scored'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Attention',
                        'message': "Extrayez d'abord le CV avant le scoring Gemini.",
                        'type': 'warning',
                    }
                }
            
            rec.with_delay(
                channel='root.recruitment_scoring',
                priority=3,
                description=f"Scoring Gemini: {rec.name}"
            )._job_scorer_gemini()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Scoring Gemini lancé',
                'message': "Le scoring se fait en arrière-plan.",
                'type': 'info',
                'sticky': False,
            }
        }

    def _move_to_kanban_stage(self):
        """
        Déplace automatiquement la candidature dans le Kanban Odoo selon le state.
        """
        STAGE_MAPPING = {
            'new':        'CVs présélectionnés',
            'extracting': 'CVs présélectionnés',
            'extracted':  'CVs présélectionnés',
            'scoring':    'CVs en instance',
            'scored':     'CVs en instance',
            'analyzed':   'CVs en instance',
            'shortlisted':'CVs shortlistés',
            'rejected':   'CVs présélectionnés',
        }
        
        stage_name = STAGE_MAPPING.get(self.state)
        _logger.info(
            "KANBAN DEBUG: candidat=%s, state=%s, stage_name=%s, applicant_id=%s, email=%s",
            self.name, self.state, stage_name, self.applicant_id.id if self.applicant_id else 'NONE', self.email or 'NONE'
        )
        if not stage_name:
            _logger.warning(
                "État inconnu pour candidat %s: %s - Pas de déplacement Kanban",
                self.name, self.state
            )
            return
        
        stage = self.env['hr.recruitment.stage'].sudo().search(
            [('name', '=', stage_name)], limit=1
        )
        if not stage:
            _logger.warning(
                "Étape Kanban introuvable: %s - Vérifiez la configuration RH",
                stage_name
            )
            return
        
        if self.applicant_id:
            applicant = self.applicant_id
        elif self.email:
            applicant = self.env['hr.applicant'].sudo().search(
                [('email_from', '=', self.email)], limit=1
            )
        else:
            applicant = False
        
        if not applicant:
            try:
                applicant_vals = {
                    'partner_name': self.name,
                    'email_from': self.email or False,
                    'partner_phone': self.phone or False,
                    'job_id': self.job_id.job_odoo_id.id if (self.job_id and self.job_id.job_odoo_id) else False,
                    'stage_id': stage.id,
                    'description': f"Candidat importé automatiquement\nScore IA: {self.ai_score:.1f}/100",
                }
                applicant = self.env['hr.applicant'].sudo().create(applicant_vals)
                self.applicant_id = applicant.id
                self.stage_id = stage.id
                _logger.info(
                    "✅ Candidature créée pour %s → Kanban: %s (Score: %.1f)",
                    self.name, stage_name, self.ai_score
                )
            except Exception as e:
                _logger.error(
                    "❌ Impossible de créer la candidature pour %s: %s",
                    self.name, str(e)
                )
                return
        else:
            try:
                applicant.sudo().write({'stage_id': stage.id})
                self.stage_id = stage.id
                _logger.info(
                    "✅ Candidature %s déplacée → %s (Score: %.1f)",
                    self.name, stage_name, self.ai_score
                )
            except Exception as e:
                _logger.error(
                    "❌ Impossible de déplacer %s vers %s: %s",
                    self.name, stage_name, str(e)
                )

    def action_scorer_cv(self):
        return self.action_analyser_cv()

    def action_shortlist(self):
        self.write({'shortlisted': True, 'state': 'shortlisted'})
    
    def action_unshortlist(self):
        self.write({'shortlisted': False, 'state': 'analyzed'})
    
    def action_reject(self):
        self.write({'shortlisted': False, 'state': 'rejected'})

    @api.onchange('cv_file', 'cv_filename')
    def _onchange_cv_file(self):
        if not self.cv_file:
            return
        
        if not self.cv_filename:
            if self._context.get('default_cv_filename'):
                self.cv_filename = self._context.get('default_cv_filename')
            else:
                self.cv_filename = f"CV_{self.id or 'nouveau'}.pdf"
        
        if self.cv_text:
            return
        
        try:
            from ..services.cv_parser import extract_text_from_cv
            text, errors = extract_text_from_cv(self.cv_file, self.cv_filename)
            self.cv_text = text or ""
            self.parse_errors = errors or False
        except Exception as e:
            _logger.warning("Onchange CV extraction: %s", str(e))

    @api.model
    def create(self, vals):
        candidat = super(SmartCandidat, self).create(vals)
        
        if candidat.cv_file and candidat.job_id:
            try:
                candidat.calculer_score_python_seulement()
            except Exception as e:
                _logger.warning(
                    "Impossible de scorer Python automatiquement le candidat %s: %s",
                    candidat.name, str(e)
                )
        
        return candidat