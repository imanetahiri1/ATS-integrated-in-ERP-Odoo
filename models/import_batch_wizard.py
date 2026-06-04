# -*- coding: utf-8 -*-
from odoo import models, fields, api
import base64
import logging

_logger = logging.getLogger(__name__)

# FAILLE 9 : import de _extraire_identite_locale
from ..models.smart_candidat import _extraire_identite_locale


class ImportBatchCVWizard(models.TransientModel):
    _name = 'smart.import.batch.cv.wizard'
    _description = 'Wizard pour importer plusieurs CVs en batch'

    offre_id = fields.Many2one(
        'smart.offre',
        string='Offre d\'emploi',
        required=True,
        readonly=True
    )
    
    cv_files = fields.Many2many(
        'ir.attachment',
        string='Fichiers CVs',
        help='Sélectionnez plusieurs fichiers CVs (PDF, DOCX, images)',
        required=True
    )
    
    auto_score = fields.Boolean(
        string='Lancer le scoring automatiquement',
        default=True,
        help='Si coché, lance l\'analyse Python + Gemini après import'
    )
    
    use_2_pass_scoring = fields.Boolean(
        string='Utiliser le scoring 2-passes (optimisé)',
        default=True,
        help='Si coché, utilise l\'optimisation 2-passes (Python tous + Gemini top 20%)'
    )

    def action_import_cvs(self):
        """
        Importe tous les CVs et lance optionnellement le scoring.
        """
        self.ensure_one()
        
        if not self.cv_files:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Aucun fichier',
                    'message': 'Veuillez selectionner au moins un CV.',
                    'type': 'warning',
                }
            }
        
        candidats_crees = self.env['smart.candidat']
        erreurs = []
        
        # Import de chaque CV
        for attachment in self.cv_files:
            candidat = False
            try:
                # Extraire le nom du fichier (sans extension)
                nom_candidat = attachment.name.rsplit('.', 1)[0]
                
                # Créer le candidat
                candidat = self.env['smart.candidat'].create({
                    'name': nom_candidat,
                    'job_id': self.offre_id.id,
                    'cv_file': attachment.datas,
                    'cv_filename': attachment.name,
                    'source': 'import_masse',
                    'source_ajout': 'import_masse',
                })
                
                candidats_crees |= candidat
                
                # FAILLE 9 : Extraire le texte + identité immédiatement après création
                try:
                    from ..services.cv_parser import extract_text_from_cv
                    text, errors = extract_text_from_cv(attachment.datas, attachment.name)
                    if text:
                        nom_local, email_local, phone_local = _extraire_identite_locale(text)
                        candidat.write({
                            'cv_text': text,
                            'parse_errors': errors or False,
                            'name': nom_local or candidat.name,
                            'email': email_local or False,
                            'phone': phone_local or False,
                        })
                except Exception as e:
                    _logger.warning("Extraction texte échouée pour %s: %s", attachment.name, str(e))
                
            except Exception as e:
                erreurs.append(f"{attachment.name}: {str(e)}")
                _logger.error(f"Erreur import CV {attachment.name}: {str(e)}")
        
        # Scoring automatique si demandé
        if self.auto_score and candidats_crees:
            try:
                if self.use_2_pass_scoring:
                    self._score_candidats_2_passes(candidats_crees)
                else:
                    for candidat in candidats_crees:
                        try:
                            candidat.action_analyser_cv()
                        except Exception as e:
                            erreurs.append(f"Scoring {candidat.name}: {str(e)}")
                            _logger.error(f"Erreur scoring {candidat.name}: {str(e)}")
            except Exception as e:
                erreurs.append(f"Erreur scoring global: {str(e)}")
                _logger.error(f"Erreur scoring global: {str(e)}")
        
        # Message de résultat
        nb_succes = len(candidats_crees)
        nb_erreurs = len(erreurs)
        
        message = f"{nb_succes} CV(s) importe(s) avec succes"
        if self.auto_score:
            message += " et analyse(s)"
        if nb_erreurs > 0:
            message += f"\n{nb_erreurs} erreur(s) : " + ", ".join(erreurs[:3])
            if nb_erreurs > 3:
                message += f"... et {nb_erreurs - 3} autres"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Import termine',
                'message': message,
                'type': 'success' if nb_erreurs == 0 else 'warning',
                'sticky': True,
            }
        }

    def _score_candidats_2_passes(self, candidats):
        """
        Score les candidats avec la méthode 2-passes optimisée.
        """
        # Pass 1 : Python uniquement
        # FAILLE 10 : suppression du filtre if candidat.cv_text
        for candidat in candidats:
            candidat.calculer_score_python_seulement()
        
        # Pass 2 : Top 20% avec Gemini
        candidats_tries = candidats.sorted(
            key=lambda c: c.score_python,
            reverse=True
        )
        nb_top = max(int(len(candidats) * 0.20), 2)
        candidats_top = candidats_tries[:nb_top]
        
        for candidat in candidats_top:
            candidat.action_analyser_cv()